"""
Scenario Simulation Service
POST /scenario/simulate

Rule-based what-if engine. No external APIs or new dependencies.
Reuses DatasetService for data access.

──────────────────────────────────────────────────────────────────
EXAMPLE REQUEST & EXPECTED RESPONSE
──────────────────────────────────────────────────────────────────
POST /scenario/simulate
{
  "target_segment": "All",
  "risk_threshold": 0.6,
  "retention_budget": 500000,
  "offer_discount_pct": 10,
  "expected_success_rate": 0.18
}

ROI FORMULA (corrected):
  estimated_roi = expected_revenue_saved / retention_budget
  e.g. ₹30,171,241 / ₹500,000 = 60.34×

EXPECTED RESPONSE (approximate with this dataset):
{
  "scenario_summary": "Simulating a 10% retention offer for 1,332 at-risk
    customers in all segments (input risk threshold: 0.60; auto-adjusted to
    0.33 — no customers found at input threshold). With a ₹5.0 Lakh budget,
    1,332 customers can be reached, and ~239 are expected to be retained —
    recovering ₹3.02 Cr in revenue at 60.34× ROI.",
  "baseline": {
    "affected_customers": 1332,
    "current_revenue_at_risk": 168151015.0,
    "avg_monthly_fee": 3003.68,
    "avg_churn_risk_score": 0.4003
  },
  "simulation": {
    "avg_offer_cost": 300.37,
    "customers_reachable": 1332,
    "expected_customers_saved": 239,
    "expected_revenue_saved": 30171241.0,
    "total_spend": 400092.84,
    "estimated_roi": 60.34,
    "roi_label": "Excellent"
  }
}
──────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field
import pandas as pd

# ─────────────────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────────────────

class SimulationRequest(BaseModel):
    target_segment:        str   = Field("All",     description="'All' or a value matched against region/segment/plan_type")
    risk_threshold:        float = Field(0.6,       ge=0.0, le=1.0, description="Min churn_risk_score to include")
    retention_budget:      float = Field(500_000,   gt=0,   description="Total spend available for retention offers (₹)")
    offer_discount_pct:    float = Field(10.0,      ge=0.0, le=100.0, description="Discount offered (% of monthly fee)")
    expected_success_rate: float = Field(0.18,      ge=0.0, le=1.0,   description="Fraction of reached customers who stay")


class BaselineMetrics(BaseModel):
    # NOTE: field named affected_customers throughout (no alias switching)
    affected_customers:      int     # customers with churn_risk_score >= threshold
    current_revenue_at_risk: float
    avg_monthly_fee:         float
    avg_churn_risk_score:    float


class SimulationMetrics(BaseModel):
    avg_offer_cost:           float
    customers_reachable:      int
    expected_customers_saved: int
    expected_revenue_saved:   float
    total_spend:              float
    # ROI = expected_revenue_saved / retention_budget  (budget-relative, not spend-relative)
    estimated_roi:            float
    roi_label:                str


class SimulationResponse(BaseModel):
    scenario_summary:  str
    baseline:          BaselineMetrics
    simulation:        SimulationMetrics
    recommendation:    str
    confidence_level:  str


# ─────────────────────────────────────────────────────────────────────────────
# Column aliases
# ─────────────────────────────────────────────────────────────────────────────

_RISK_ALIASES    = ["churn_risk_score", "risk_score", "churn_score"]
_CLV_ALIASES     = ["estimated_clv", "clv", "customer_lifetime_value", "ltv"]
_FEE_ALIASES     = ["monthlycharges", "monthly_charges", "monthly_fee",
                    "monthly_revenue", "monthlyrevenue"]
_SEGMENT_ALIASES = ["customer_segment", "segment", "plantype", "plan_type"]
_REGION_ALIASES  = ["region", "city", "location"]
_PLAN_ALIASES    = ["plan_type", "plantype", "plan"]


def _find(df: pd.DataFrame, aliases: list[str]) -> Optional[str]:
    lmap = {c.lower(): c for c in df.columns}
    for a in aliases:
        if a.lower() in lmap:
            return lmap[a.lower()]
    return None


def _safe_float(val, default: float = 0.0) -> float:
    try:
        v = float(val)
        return v if pd.notna(v) else default
    except Exception:
        return default


def _fmt_inr(v: float) -> str:
    """Format a numeric value in INR: Cr / Lakh / plain ₹."""
    if v >= 10_000_000: return f"₹{v / 10_000_000:.1f} Cr"
    if v >= 100_000:    return f"₹{v / 100_000:.1f} Lakh"
    return f"₹{v:,.0f}"


# ─────────────────────────────────────────────────────────────────────────────
# Service
# ─────────────────────────────────────────────────────────────────────────────

class ScenarioService:
    """
    Stateless what-if simulator. Instantiated per-request so it always uses
    the current dataset without caching stale data.
    """

    def simulate(self, req: SimulationRequest) -> SimulationResponse:
        from app.services.dataset_service import DatasetService
        svc  = DatasetService()
        df   = svc.df.copy()

        # ── Column resolution ────────────────────────────────────────────────
        risk_col = _find(df, _RISK_ALIASES)
        clv_col  = _find(df, _CLV_ALIASES)
        fee_col  = _find(df, _FEE_ALIASES)
        seg_cols = [c for c in [
                        _find(df, _REGION_ALIASES),
                        _find(df, _SEGMENT_ALIASES),
                        _find(df, _PLAN_ALIASES),
                    ] if c is not None]

        # ── Numeric series ───────────────────────────────────────────────────
        risk_s = (pd.to_numeric(df[risk_col], errors="coerce").fillna(0.0)
                  if risk_col else pd.Series(0.0, index=df.index))
        clv_s  = (pd.to_numeric(df[clv_col],  errors="coerce").fillna(0.0)
                  if clv_col  else pd.Series(0.0, index=df.index))
        fee_s  = (pd.to_numeric(df[fee_col],  errors="coerce").fillna(0.0)
                  if fee_col  else pd.Series(0.0, index=df.index))

        # ── Auto-threshold fallback ──────────────────────────────────────────
        # Always preserve the user's input for display. Only adjust internally.
        effective_threshold = req.risk_threshold
        threshold_adjusted  = False
        if (risk_s >= effective_threshold).sum() == 0 and len(risk_s) > 0:
            effective_threshold = float(risk_s.quantile(0.75))
            threshold_adjusted  = True

        # ── Segment filter ───────────────────────────────────────────────────
        seg_mask = pd.Series(True, index=df.index)
        if req.target_segment.strip().lower() not in ("all", ""):
            val      = req.target_segment.strip().lower()
            col_mask = pd.Series(False, index=df.index)
            for col in seg_cols:
                col_mask |= df[col].astype(str).str.lower().str.contains(val, na=False)
            seg_mask = col_mask

        # ── At-risk cohort ───────────────────────────────────────────────────
        at_risk_mask = (risk_s >= effective_threshold) & seg_mask
        cohort_risk  = risk_s[at_risk_mask]
        cohort_clv   = clv_s[at_risk_mask]
        cohort_fee   = fee_s[at_risk_mask]
        n_at_risk    = int(at_risk_mask.sum())

        # ── Guard: empty cohort ──────────────────────────────────────────────
        if n_at_risk == 0:
            return SimulationResponse(
                scenario_summary=(
                    f"No customers matched segment '{req.target_segment}' "
                    f"with risk >= {req.risk_threshold:.2f}. "
                    "Try lowering the risk threshold or selecting 'All'."
                ),
                baseline=BaselineMetrics(
                    affected_customers=0,
                    current_revenue_at_risk=0.0,
                    avg_monthly_fee=0.0,
                    avg_churn_risk_score=0.0,
                ),
                simulation=SimulationMetrics(
                    avg_offer_cost=0.0,
                    customers_reachable=0,
                    expected_customers_saved=0,
                    expected_revenue_saved=0.0,
                    total_spend=0.0,
                    estimated_roi=0.0,
                    roi_label="N/A",
                ),
                recommendation="Adjust filters and retry.",
                confidence_level="Low",
            )

        # ── Baseline ─────────────────────────────────────────────────────────
        revenue_at_risk = _safe_float(cohort_clv.sum())
        avg_monthly_fee = _safe_float(cohort_fee.mean()) if len(cohort_fee) else 0.0
        avg_risk_score  = _safe_float(cohort_risk.mean())

        # ── Simulation ───────────────────────────────────────────────────────
        avg_offer_cost = avg_monthly_fee * req.offer_discount_pct / 100.0
        if avg_offer_cost <= 0:
            avg_offer_cost = 500.0   # fallback: ₹500 flat offer cost

        customers_reachable      = min(int(req.retention_budget / avg_offer_cost), n_at_risk)
        expected_customers_saved = int(customers_reachable * req.expected_success_rate)

        clv_per_customer       = revenue_at_risk / max(n_at_risk, 1)
        expected_revenue_saved = clv_per_customer * expected_customers_saved
        total_spend            = customers_reachable * avg_offer_cost

        # ROI = expected_revenue_saved / retention_budget  (budget-relative)
        estimated_roi = round(expected_revenue_saved / max(req.retention_budget, 1.0), 2)

        roi_label = (
            "Excellent" if estimated_roi >= 50
            else "Strong"   if estimated_roi >= 20
            else "Good"     if estimated_roi >= 5
            else "Marginal" if estimated_roi >= 1
            else "Negative"
        )

        # ── Narrative ────────────────────────────────────────────────────────
        seg_label = req.target_segment if req.target_segment.strip().lower() not in ("all", "") else "all segments"

        # Show the user's original input threshold; append adjustment note if applicable
        threshold_display = f"{req.risk_threshold:.2f}"
        threshold_note = (
            f"; auto-adjusted to {effective_threshold:.2f} — no customers found at input threshold"
            if threshold_adjusted else ""
        )

        scenario_summary = (
            f"Simulating a {req.offer_discount_pct:.0f}% retention offer for {n_at_risk:,} at-risk customers "
            f"in {seg_label} (input risk threshold: {threshold_display}{threshold_note}). "
            f"With a {_fmt_inr(req.retention_budget)} budget, {customers_reachable:,} customers can be reached, "
            f"and ~{expected_customers_saved:,} are expected to be retained — "
            f"recovering {_fmt_inr(expected_revenue_saved)} in revenue at {estimated_roi:.2f}× ROI."
        )

        recommendation = _build_recommendation(
            roi=estimated_roi,
            revenue_saved=expected_revenue_saved,
            budget=req.retention_budget,
            discount_pct=req.offer_discount_pct,
            coverage_pct=customers_reachable / max(n_at_risk, 1) * 100,
        )

        confidence_level = (
            "High"   if len(cohort_clv) >= 200 and fee_col is not None
            else "Medium" if len(cohort_clv) >= 50
            else "Low"
        )

        return SimulationResponse(
            scenario_summary=scenario_summary,
            baseline=BaselineMetrics(
                affected_customers=n_at_risk,
                current_revenue_at_risk=round(revenue_at_risk, 2),
                avg_monthly_fee=round(avg_monthly_fee, 2),
                avg_churn_risk_score=round(avg_risk_score, 4),
            ),
            simulation=SimulationMetrics(
                avg_offer_cost=round(avg_offer_cost, 2),
                customers_reachable=customers_reachable,
                expected_customers_saved=expected_customers_saved,
                expected_revenue_saved=round(expected_revenue_saved, 2),
                total_spend=round(total_spend, 2),
                estimated_roi=estimated_roi,
                roi_label=roi_label,
            ),
            recommendation=recommendation,
            confidence_level=confidence_level,
        )


def _build_recommendation(
    roi: float,
    revenue_saved: float,
    budget: float,
    discount_pct: float,
    coverage_pct: float,
) -> str:
    if roi >= 20:
        rec = (
            f"Proceed immediately — {_fmt_inr(budget)} budget is projected to recover "
            f"{_fmt_inr(revenue_saved)} ({roi:.1f}× ROI). "
        )
    elif roi >= 5:
        rec = f"Strong case for investment — {_fmt_inr(revenue_saved)} recovered at {roi:.1f}× ROI. "
    elif roi >= 1:
        rec = (
            f"Marginal return at {roi:.1f}× ROI. Consider increasing the success rate "
            f"via personalisation before committing the full budget. "
        )
    else:
        rec = (
            "Negative ROI at current parameters. Increase success rate, reduce offer discount, "
            "or increase budget targeting. "
        )

    if coverage_pct < 50:
        rec += (
            f"Only {coverage_pct:.0f}% of at-risk customers can be reached — "
            f"prioritise the highest-CLV cohort first."
        )
    elif coverage_pct < 80:
        rec += f"Coverage is {coverage_pct:.0f}% — adequate for an initial campaign."
    else:
        rec += f"Full cohort coverage ({coverage_pct:.0f}%) achievable within budget."

    return rec
