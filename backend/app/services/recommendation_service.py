"""
RecommendationService — deterministic Next Best Action (NBA) engine.

Rule priority (evaluated top-to-bottom; first match wins):

  1. HIGH churn (≥0.65) + HIGH CLV (≥75th pct)      → "Premium Retention Offer"
  2. HIGH churn (≥0.65) + many complaints (≥3)       → "Service Recovery Call"
  3. HIGH churn (≥0.65) + payment failures (≥2)      → "Payment Support Plan"
  4. LOW churn (<0.35)  + HIGH upsell prob (≥0.65)   → "Upsell Premium Plan"
  5. LOW satisfaction (≤4.0 / 10)                     → "CX Intervention"
  6. Default                                          → "Monitor"
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import pandas as pd

from app.schemas.recommendation_schema import (
    BatchRecommendRequest,
    BatchRecommendResponse,
    CustomerRecommendRequest,
    CustomerRecommendResponse,
    PriorityCustomer,
    PriorityListResponse,
    StrategyBucket,
    StrategySummaryResponse,
)
from app.services.dataset_service import DatasetService, _find_col

# ---------------------------------------------------------------------------
# Rule thresholds (adjust per business context)
# ---------------------------------------------------------------------------
HIGH_CHURN_THRESHOLD = 0.65
LOW_CHURN_THRESHOLD = 0.35
HIGH_CLV_PERCENTILE = 75          # dynamically computed from dataset
HIGH_UPSELL_THRESHOLD = 0.65
MANY_COMPLAINTS_THRESHOLD = 3
MANY_PAYMENT_FAILURES_THRESHOLD = 2
LOW_SATISFACTION_THRESHOLD = 4.0  # out of 10

# Confidence weights per rule (0–1)
_RULE_CONFIDENCE: Dict[str, float] = {
    "Premium Retention Offer": 0.90,
    "Service Recovery Call": 0.85,
    "Payment Support Plan": 0.82,
    "Upsell Premium Plan": 0.78,
    "CX Intervention": 0.75,
    "Monitor": 0.60,
}

_RULE_PRIORITY: Dict[str, str] = {
    "Premium Retention Offer": "Critical",
    "Service Recovery Call": "High",
    "Payment Support Plan": "High",
    "Upsell Premium Plan": "Medium",
    "CX Intervention": "Medium",
    "Monitor": "Low",
}

_RULE_REASONS: Dict[str, str] = {
    "Premium Retention Offer": (
        "Customer has a high churn probability combined with high lifetime value. "
        "Proactive premium retention offer can protect significant revenue."
    ),
    "Service Recovery Call": (
        "Customer is at high churn risk and has logged multiple complaints in the last 90 days. "
        "A direct service recovery call is the highest-impact intervention."
    ),
    "Payment Support Plan": (
        "Elevated churn risk driven by repeated payment failures. "
        "Flexible payment arrangement can reduce financial friction and improve retention."
    ),
    "Upsell Premium Plan": (
        "Customer has a low churn risk but a high upsell probability. "
        "Now is the right moment to propose a premium plan upgrade."
    ),
    "CX Intervention": (
        "Customer satisfaction score is below the acceptable threshold. "
        "A targeted CX intervention can prevent future churn."
    ),
    "Monitor": (
        "Customer profile does not trigger any high-priority intervention rule. "
        "Routine monitoring and next scheduled contact are sufficient."
    ),
}

# ---------------------------------------------------------------------------
# Priority-list action mapping
# ---------------------------------------------------------------------------
_PRIORITY_ACTION: Dict[str, Tuple[str, str]] = {
    "High Priority": (
        "Immediate Retention Outreach",
        "High priority score driven by elevated churn risk and/or CLV — "
        "immediate personalised outreach required within 48 hours.",
    ),
    "Medium Priority": (
        "Scheduled Retention Touch",
        "Moderate risk profile warrants proactive but non-urgent retention contact "
        "within the next 2 weeks.",
    ),
    "Low Priority": (
        "Routine Monitoring",
        "Low priority score — no immediate action required; "
        "include in standard monthly monitoring cycle.",
    ),
}


# ---------------------------------------------------------------------------
# CLV threshold (loaded lazily from dataset)
# ---------------------------------------------------------------------------
_clv_p75: float | None = None


def _get_clv_p75() -> float:
    """Return the 75th-percentile CLV from the dataset (cached)."""
    global _clv_p75
    if _clv_p75 is None:
        try:
            svc = DatasetService()
            if svc._clv_col:
                clv = pd.to_numeric(svc.df[svc._clv_col], errors="coerce").dropna()
                _clv_p75 = float(clv.quantile(HIGH_CLV_PERCENTILE / 100))
            else:
                _clv_p75 = 5000.0  # sensible fallback
        except Exception:
            _clv_p75 = 5000.0
    return _clv_p75


# ---------------------------------------------------------------------------
# Rule engine
# ---------------------------------------------------------------------------

def _apply_rules(req: CustomerRecommendRequest) -> Tuple[str, str]:
    """Return (recommendation_label, reason_text) for a customer record."""
    clv_threshold = _get_clv_p75()
    churn = req.churn_risk_score
    clv = req.estimated_clv
    upsell = req.upsell_probability
    sat = req.satisfaction_score
    complaints = req.complaints_90d
    failures = req.payment_failures_12m

    # Rule 1 — High churn + High CLV
    if churn >= HIGH_CHURN_THRESHOLD and clv >= clv_threshold:
        return "Premium Retention Offer", _RULE_REASONS["Premium Retention Offer"]

    # Rule 2 — High churn + Many complaints
    if churn >= HIGH_CHURN_THRESHOLD and complaints >= MANY_COMPLAINTS_THRESHOLD:
        return "Service Recovery Call", _RULE_REASONS["Service Recovery Call"]

    # Rule 3 — High churn + Payment failures
    if churn >= HIGH_CHURN_THRESHOLD and failures >= MANY_PAYMENT_FAILURES_THRESHOLD:
        return "Payment Support Plan", _RULE_REASONS["Payment Support Plan"]

    # Rule 4 — Low churn + High upsell
    if churn < LOW_CHURN_THRESHOLD and upsell >= HIGH_UPSELL_THRESHOLD:
        return "Upsell Premium Plan", _RULE_REASONS["Upsell Premium Plan"]

    # Rule 5 — Low satisfaction
    if sat <= LOW_SATISFACTION_THRESHOLD:
        return "CX Intervention", _RULE_REASONS["CX Intervention"]

    # Default
    return "Monitor", _RULE_REASONS["Monitor"]


def _expected_revenue_protected(req: CustomerRecommendRequest, recommendation: str) -> float:
    """
    Estimate revenue protected if the recommended action is executed.
    Uses CLV × probability the action prevents churn.
    """
    retention_success_rates: Dict[str, float] = {
        "Premium Retention Offer": 0.65,
        "Service Recovery Call": 0.55,
        "Payment Support Plan": 0.50,
        "Upsell Premium Plan": 0.20,   # revenue uplift, not retention
        "CX Intervention": 0.40,
        "Monitor": 0.05,
    }
    rate = retention_success_rates.get(recommendation, 0.05)
    return round(req.estimated_clv * req.churn_risk_score * rate, 2)


# ---------------------------------------------------------------------------
# Priority score helpers
# ---------------------------------------------------------------------------

def _safe_float(val, default: float = 0.0) -> float:
    try:
        result = float(val)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def _safe_int(val, default: int = 0) -> int:
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return default


def _normalize(series: pd.Series) -> pd.Series:
    """Min-max scale a Series to [0, 1]. Returns zeros if range is zero."""
    s = pd.to_numeric(series, errors="coerce").fillna(0.0)
    lo, hi = s.min(), s.max()
    if hi > lo:
        return ((s - lo) / (hi - lo)).clip(0.0, 1.0)
    return pd.Series(0.0, index=s.index)


def _priority_class(score: float) -> str:
    if score >= 0.65:
        return "High Priority"
    if score >= 0.40:
        return "Medium Priority"
    return "Low Priority"


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class RecommendationService:
    """Stateless Next Best Action service — all logic is rule-based."""

    def recommend_single(
        self, req: CustomerRecommendRequest
    ) -> CustomerRecommendResponse:
        recommendation, reason = _apply_rules(req)
        revenue = _expected_revenue_protected(req, recommendation)
        return CustomerRecommendResponse(
            customer_id=req.customer_id,
            recommendation=recommendation,
            reason=reason,
            expected_revenue_protected=revenue,
            priority=_RULE_PRIORITY[recommendation],
            confidence=_RULE_CONFIDENCE[recommendation],
        )

    def recommend_batch(
        self, req: BatchRecommendRequest
    ) -> BatchRecommendResponse:
        results = [self.recommend_single(c) for c in req.customers]
        total_revenue = round(sum(r.expected_revenue_protected for r in results), 2)
        return BatchRecommendResponse(
            total_customers=len(results),
            total_revenue_protected=total_revenue,
            recommendations=results,
        )

    def strategy_summary(self) -> StrategySummaryResponse:
        """
        Run NBA rules across the full dataset and aggregate by strategy.
        Requires the DatasetService to be available.
        """
        svc = DatasetService()
        df = svc.df.copy()

        col_map = {
            "churn_risk_score": svc._risk_col,
            "estimated_clv": svc._clv_col,
            "satisfaction_score": svc._sat_col,
        }

        def _get_val(row, preferred: str, fallback, default: float) -> float:
            if fallback and fallback in row.index:
                try:
                    return float(row[fallback])
                except (ValueError, TypeError):
                    pass
            if preferred in row.index:
                try:
                    return float(row[preferred])
                except (ValueError, TypeError):
                    pass
            return default

        results: List[CustomerRecommendResponse] = []
        for _, row in df.iterrows():
            req = CustomerRecommendRequest(
                customer_id=str(row.get("customer_id", "")),
                churn_risk_score=_get_val(row, "churn_risk_score", col_map["churn_risk_score"], 0.0),
                estimated_clv=_get_val(row, "estimated_clv", col_map["estimated_clv"], 0.0),
                upsell_probability=float(row.get("upsell_probability", 0.0) or 0.0),
                retention_offer_cost=float(row.get("retention_offer_cost", 0.0) or 0.0),
                complaints_90d=int(row.get("complaints_90d", 0) or 0),
                payment_failures_12m=int(row.get("payment_failures_12m", 0) or 0),
                satisfaction_score=_get_val(row, "satisfaction_score", col_map["satisfaction_score"], 5.0),
                contract_type=str(row.get("contract_type", "")) or None,
                plan_type=str(row.get("plan_type", "")) or None,
            )
            results.append(self.recommend_single(req))

        # Aggregate
        strategy_totals: Dict[str, Dict] = {}
        for r in results:
            if r.recommendation not in strategy_totals:
                strategy_totals[r.recommendation] = {"count": 0, "revenue": 0.0}
            strategy_totals[r.recommendation]["count"] += 1
            strategy_totals[r.recommendation]["revenue"] += r.expected_revenue_protected

        total = max(len(results), 1)
        buckets = [
            StrategyBucket(
                strategy=strat,
                customer_count=v["count"],
                pct_of_total=round(v["count"] / total * 100, 2),
                total_revenue_protected=round(v["revenue"], 2),
            )
            for strat, v in sorted(
                strategy_totals.items(), key=lambda x: x[1]["count"], reverse=True
            )
        ]

        return StrategySummaryResponse(
            total_customers_analysed=len(results),
            strategies=buckets,
        )

    # ------------------------------------------------------------------
    # Customer prioritisation
    # ------------------------------------------------------------------

    def priority_list(self, top_n: int = 500) -> PriorityListResponse:
        """
        Score every customer with:
            priority_score = (churn_risk_score × 0.5)
                           + (normalized_clv × 0.3)
                           + (complaints_weight × 0.2)

        normalized_clv      = min-max scaled estimated_clv → [0, 1]
        complaints_weight   = min-max scaled complaints_90d → [0, 1]
        Missing values filled with 0 before scaling.

        Returns the top `top_n` customers sorted by priority_score descending.
        """
        svc = DatasetService()
        df = svc.df.copy()

        # ── Column resolution ────────────────────────────────────────────────
        risk_col     = svc._risk_col   # churn_risk_score
        clv_col      = svc._clv_col    # estimated_clv
        complaints_col = _find_col(df, ["complaints_90d", "complaints", "support_tickets",
                                        "supporttickets"])
        cid_col      = _find_col(df, ["customer_id", "customerid", "custid", "id"])
        region_col   = _find_col(df, ["region", "city", "location"])
        segment_col  = _find_col(df, ["customer_segment", "segment", "plantype", "plan_type"])
        plan_col     = _find_col(df, ["plan_type", "plantype", "plan"])

        # ── Numeric series with safe defaults ────────────────────────────────
        risk_s       = (pd.to_numeric(df[risk_col], errors="coerce").fillna(0.0)
                        if risk_col else pd.Series(0.0, index=df.index))
        clv_s        = (pd.to_numeric(df[clv_col], errors="coerce").fillna(0.0)
                        if clv_col else pd.Series(0.0, index=df.index))
        complaints_s = (pd.to_numeric(df[complaints_col], errors="coerce").fillna(0.0)
                        if complaints_col else pd.Series(0.0, index=df.index))

        # ── Normalise to [0, 1] ──────────────────────────────────────────────
        norm_clv        = _normalize(clv_s)
        complaints_wt   = _normalize(complaints_s)

        # ── Composite priority score ─────────────────────────────────────────
        priority_score  = (risk_s * 0.5) + (norm_clv * 0.3) + (complaints_wt * 0.2)
        priority_score  = priority_score.clip(0.0, 1.0).round(4)

        # Attach computed columns temporarily
        df = df.assign(
            _priority_score=priority_score,
            _norm_clv=norm_clv.round(4),
        )

        # ── Sort desc and cap ────────────────────────────────────────────────
        df = df.sort_values("_priority_score", ascending=False).head(top_n)

        # Compute adaptive thresholds from the RETURNED slice.
        # Classify relative to this cohort so labels are always meaningful:
        #   top 20% of returned list → High, bottom 35% → Low, rest → Medium
        _slice_scores = df["_priority_score"]
        _hi_thresh  = float(_slice_scores.quantile(0.80))
        _med_thresh = float(_slice_scores.quantile(0.35))

        # ── Build output records ─────────────────────────────────────────────
        customers: List[PriorityCustomer] = []
        for idx, row in df.iterrows():
            score  = _safe_float(row["_priority_score"])
            pclass = ("High Priority" if score >= _hi_thresh else
                      "Medium Priority" if score >= _med_thresh else
                      "Low Priority")
            action, rationale = _PRIORITY_ACTION[pclass]

            # Derive customer_id from column or row index
            if cid_col and row.get(cid_col) is not None:
                cid = str(row[cid_col])
            else:
                cid = str(idx)

            customers.append(PriorityCustomer(
                customer_id=cid,
                region=str(row[region_col]) if region_col and row.get(region_col) is not None else "Unknown",
                customer_segment=str(row[segment_col]) if segment_col and row.get(segment_col) is not None else "Unknown",
                plan_type=str(row[plan_col]) if plan_col and row.get(plan_col) is not None else "Unknown",
                estimated_clv=_safe_float(row[clv_col]) if clv_col else 0.0,
                churn_risk_score=_safe_float(row[risk_col]) if risk_col else 0.0,
                complaints_90d=_safe_int(row[complaints_col]) if complaints_col else 0,
                priority_score=score,
                priority_class=pclass,
                recommended_action=action,
                rationale=rationale,
            ))

        # ── Counts by class ──────────────────────────────────────────────────
        high   = sum(1 for c in customers if c.priority_class == "High Priority")
        medium = sum(1 for c in customers if c.priority_class == "Medium Priority")
        low    = sum(1 for c in customers if c.priority_class == "Low Priority")

        return PriorityListResponse(
            total_returned=len(customers),
            high_priority_count=high,
            medium_priority_count=medium,
            low_priority_count=low,
            customers=customers,
        )
