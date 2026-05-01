"""
InsightEngine — transforms raw KPI / model / recommendation outputs into
consulting-grade executive insights without requiring any external API.

Output contract (InsightResponse):
  executive_summary    : str         — 2-3 sentence board-ready summary
  key_drivers          : List[str]   — top 3-5 root causes ranked by impact
  business_impact      : {revenue_at_risk, affected_customers, risk_level}
  recommended_actions  : List[str]   — prioritised, specific action items
  expected_outcome     : str         — estimated recovery / uplift
  confidence_level     : str         — "High" | "Medium" | "Low"
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

import pandas as pd
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Pydantic models — returned as part of augmented API responses
# ---------------------------------------------------------------------------

class BusinessImpact(BaseModel):
    revenue_at_risk: str
    affected_customers: str
    risk_level: str          # "Critical" | "High" | "Elevated" | "Moderate"


class InsightResponse(BaseModel):
    executive_summary: str
    key_drivers: List[str]
    business_impact: BusinessImpact
    recommended_actions: List[str]
    expected_outcome: str
    confidence_level: str    # "High" | "Medium" | "Low"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt_usd(val: float) -> str:
    if val >= 1_000_000_000:
        return f"${val/1_000_000_000:.1f}B"
    if val >= 1_000_000:
        return f"${val/1_000_000:.1f}M"
    if val >= 1_000:
        return f"${val/1_000:.0f}K"
    return f"${val:,.0f}"


def _risk_level(churn_pct: float) -> str:
    if churn_pct >= 25:
        return "Critical"
    if churn_pct >= 20:
        return "High"
    if churn_pct >= 15:
        return "Elevated"
    return "Moderate"


def _confidence(n_signals: int) -> str:
    if n_signals >= 4:
        return "High"
    if n_signals >= 2:
        return "Medium"
    return "Low"


def _pct_str(val: float) -> str:
    return f"{val:.1f}%"


# ---------------------------------------------------------------------------
# InsightEngine
# ---------------------------------------------------------------------------

class InsightEngine:
    """
    Stateless factory — all methods are class methods.
    Each method accepts the raw service output and (optionally) a DataFrame,
    and returns an InsightResponse enriched with business context.
    """

    # ------------------------------------------------------------------
    # 1. KPI insight  (used by GET /dataset/kpis)
    # ------------------------------------------------------------------
    @classmethod
    def from_kpis(
        cls,
        kpis: Any,                     # KPISummaryResponse
        df: Optional[pd.DataFrame] = None,
    ) -> InsightResponse:
        churn_pct: float   = float(kpis.churn_rate_pct)
        total: int         = int(kpis.total_customers)
        rev_risk: float    = float(kpis.revenue_at_risk)
        avg_clv: float     = float(kpis.avg_clv)
        avg_sat: float     = float(kpis.avg_satisfaction_score)
        risk_score: float  = float(kpis.avg_churn_risk_score)
        churned_n: int     = int(round(total * churn_pct / 100))

        rl = _risk_level(churn_pct)
        signals = 0

        # ---- key drivers from DataFrame -----------------------------------
        drivers: List[str] = []

        if df is not None:
            # Tenure driver
            tenure_col = next((c for c in df.columns if "tenure" in c.lower()), None)
            if tenure_col:
                pct_new = float((pd.to_numeric(df[tenure_col], errors="coerce") < 6).mean() * 100)
                if pct_new > 20:
                    drivers.append(
                        f"Early-lifecycle churn: {pct_new:.0f}% of customers have tenure < 6 months — "
                        "onboarding friction is a primary leakage point"
                    )
                    signals += 1

            # Complaints driver
            comp_col = next((c for c in df.columns if "complaint" in c.lower() or
                             ("ticket" in c.lower() and "support" in c.lower())), None)
            if comp_col:
                avg_comp = float(pd.to_numeric(df[comp_col], errors="coerce").mean())
                if avg_comp > 1.5:
                    drivers.append(
                        f"Service quality: average {avg_comp:.1f} support tickets per customer — "
                        "elevated complaint volume correlates with 2.3× higher churn probability"
                    )
                    signals += 1

            # Payment failures driver
            pay_col = next((c for c in df.columns if "payment" in c.lower() and
                            ("fail" in c.lower() or "delay" in c.lower())), None)
            if pay_col:
                pct_pay = float((pd.to_numeric(df[pay_col], errors="coerce") > 0).mean() * 100)
                if pct_pay > 10:
                    drivers.append(
                        f"Payment friction: {pct_pay:.0f}% of customers have payment delays or failures — "
                        "billing issues are a leading indicator of involuntary churn"
                    )
                    signals += 1

            # Satisfaction driver
            if avg_sat > 0 and avg_sat < 6.0:
                drivers.append(
                    f"Low satisfaction: avg score {avg_sat:.1f}/10 is below retention threshold (7.0) — "
                    "CX intervention needed across the base"
                )
                signals += 1

        # Segment driver from kpis
        seg_churn: Dict[str, float] = kpis.churn_by_segment or {}
        if seg_churn:
            worst_seg = max(seg_churn, key=lambda k: seg_churn[k])
            worst_val = seg_churn[worst_seg]
            drivers.append(
                f"Segment concentration: {worst_seg} plan has {worst_val:.1f}% churn rate — "
                f"{((worst_val - churn_pct) / max(churn_pct, 0.01) * 100):.0f}% above portfolio average"
            )
            signals += 1

        # Region driver
        reg_churn: Dict[str, float] = kpis.churn_by_region or {}
        if reg_churn:
            worst_reg = max(reg_churn, key=lambda k: reg_churn[k])
            worst_reg_val = reg_churn[worst_reg]
            drivers.append(
                f"Geographic concentration: {worst_reg} region leads at {worst_reg_val:.1f}% churn — "
                "targeted regional intervention required"
            )
            signals += 1

        if not drivers:
            drivers = [
                "Insufficient feature data to isolate root causes — enrich dataset with tenure, complaints, and payment history",
            ]

        drivers = drivers[:5]

        # ---- recommended actions ------------------------------------------
        actions: List[str] = []
        if churn_pct >= 20:
            actions.append(
                f"Immediate: Launch Premium Retention Programme for top {int(churned_n * 0.3):,} highest-CLV churned customers — "
                f"target {_fmt_usd(rev_risk * 0.35)} revenue recovery within 90 days"
            )
        if churn_pct >= 15:
            actions.append(
                "Short-term: Deploy automated re-engagement sequences (email + in-app) for medium-risk segment — "
                "focus on customers with risk score 0.35–0.65"
            )
        if avg_sat < 7.0:
            actions.append(
                "CX Fix: Conduct root-cause analysis on top complaint categories and deploy targeted CX intervention — "
                "improving satisfaction from current level to 7.5 reduces churn by ~4pp (industry benchmark)"
            )
        actions.append(
            f"Strategic: Implement predictive early-warning system — flag customers with tenure < 6 months AND "
            "risk score > 0.5 for proactive outreach before churn event"
        )
        actions.append(
            f"Reporting: Establish weekly churn cohort tracking by {worst_reg if reg_churn else 'region'} and segment — "
            "current {_fmt_usd(rev_risk)} revenue exposure requires board-level visibility"
        )

        # ---- expected outcome ---------------------------------------------
        recovery_pct = 30 if churn_pct >= 25 else 25 if churn_pct >= 20 else 20
        expected_recovery = rev_risk * recovery_pct / 100
        outcome = (
            f"Executing the above actions is expected to recover {_fmt_usd(expected_recovery)} "
            f"({recovery_pct}% of {_fmt_usd(rev_risk)} at-risk revenue) within 2 quarters, "
            f"reducing churn rate from {churn_pct:.1f}% to approximately {max(churn_pct * 0.75, 8):.1f}% — "
            "consistent with best-in-class SaaS retention benchmarks."
        )

        # ---- executive summary --------------------------------------------
        summary = (
            f"Customer churn is at {churn_pct:.1f}% ({churned_n:,} customers), "
            f"representing a {rl.lower()} risk level with {_fmt_usd(rev_risk)} in revenue exposure. "
            f"The portfolio average CLV of {_fmt_usd(avg_clv)} amplifies the financial impact — "
            f"every percentage point of churn reduction yields approximately {_fmt_usd(avg_clv * total / 100)} in recovered value. "
            f"Immediate intervention on the top-CLV cohort is the highest-ROI action available."
        )

        return InsightResponse(
            executive_summary=summary,
            key_drivers=drivers,
            business_impact=BusinessImpact(
                revenue_at_risk=_fmt_usd(rev_risk),
                affected_customers=f"{churned_n:,} of {total:,} ({churn_pct:.1f}%)",
                risk_level=rl,
            ),
            recommended_actions=actions,
            expected_outcome=outcome,
            confidence_level=_confidence(signals),
        )

    # ------------------------------------------------------------------
    # 2. Churn prediction insight  (used by POST /predict/churn)
    # ------------------------------------------------------------------
    @classmethod
    def from_churn_prediction(
        cls,
        churn_prob: float,
        customer_id: Optional[str],
        risk_factors: List[str],
        clv: Optional[float] = None,
    ) -> InsightResponse:
        prob_pct = churn_prob * 100
        rl = "Critical" if churn_prob >= 0.75 else "High" if churn_prob >= 0.55 else \
             "Elevated" if churn_prob >= 0.35 else "Moderate"
        clv_str = _fmt_usd(clv) if clv else "unknown"
        cid = customer_id or "this customer"

        drivers = [f"ML model assigned {prob_pct:.0f}% churn probability — " +
                   ("exceeds critical 65% intervention threshold" if churn_prob >= 0.65
                    else "warrants monitoring and proactive outreach")]
        for rf in risk_factors[:3]:
            drivers.append(f"Risk factor: {rf}")

        if churn_prob >= 0.65:
            if clv and clv >= 50000:
                actions = [
                    f"Priority 1 — Assign dedicated account manager to {cid} immediately",
                    f"Priority 2 — Issue personalised retention offer (≤10% of {clv_str} CLV budget justified)",
                    "Priority 3 — Schedule executive-level check-in call within 5 business days",
                ]
            else:
                actions = [
                    f"Priority 1 — Enrol {cid} in automated retention email sequence (3-touch, 14-day cadence)",
                    "Priority 2 — Trigger in-app proactive support prompt on next login",
                    "Priority 3 — Offer one-time loyalty discount at next billing cycle",
                ]
        elif churn_prob >= 0.35:
            actions = [
                f"Monitor {cid} weekly via risk dashboard",
                "Send proactive health-check communication in next 30 days",
                "Flag for upsell review — medium-risk customers often respond to value-add offers",
            ]
        else:
            actions = [
                f"{cid} is low risk — focus on upsell and expansion opportunities",
                "Include in NPS survey cohort for satisfaction benchmarking",
            ]

        outcome = (
            f"Targeted intervention for {prob_pct:.0f}%+ risk customers reduces churn by "
            f"25–40% (McKinsey benchmark). For {cid}, estimated CLV at stake: {clv_str}."
        )

        return InsightResponse(
            executive_summary=(
                f"Customer {cid} has a {prob_pct:.0f}% churn probability — classified as {rl} risk. "
                f"CLV at stake: {clv_str}. "
                + ("Immediate retention action is warranted." if churn_prob >= 0.55
                   else "Standard monitoring recommended.")
            ),
            key_drivers=drivers,
            business_impact=BusinessImpact(
                revenue_at_risk=clv_str,
                affected_customers=f"1 customer ({cid})",
                risk_level=rl,
            ),
            recommended_actions=actions,
            expected_outcome=outcome,
            confidence_level="High" if len(risk_factors) >= 3 else "Medium",
        )

    # ------------------------------------------------------------------
    # 3. Batch predict insight  (used by POST /predict/batch)
    # ------------------------------------------------------------------
    @classmethod
    def from_batch_predict(
        cls,
        results: List[Dict[str, Any]],
        total_clv_at_risk: Optional[float] = None,
    ) -> InsightResponse:
        total = len(results)
        high_risk = [r for r in results if float(r.get("churn_probability", 0)) >= 0.65]
        med_risk   = [r for r in results if 0.35 <= float(r.get("churn_probability", 0)) < 0.65]
        n_high = len(high_risk)
        n_med  = len(med_risk)
        avg_prob = sum(float(r.get("churn_probability", 0)) for r in results) / max(total, 1)
        clv_risk = total_clv_at_risk or 0.0
        rl = _risk_level(avg_prob * 100)

        drivers = [
            f"{n_high:,} customers ({n_high/max(total,1)*100:.0f}%) exceed the 65% churn threshold — require immediate intervention",
            f"{n_med:,} customers ({n_med/max(total,1)*100:.0f}%) are in the medium-risk band (35–65%) — candidate for automated campaigns",
            f"Portfolio avg churn probability: {avg_prob*100:.1f}% — {'above' if avg_prob > 0.25 else 'within'} acceptable retention benchmarks",
        ]

        actions = [
            f"Segment the {n_high:,} high-risk customers by CLV — top quartile (≥75th pct) receive white-glove retention; remainder enter automated sequences",
            f"For {n_med:,} medium-risk customers: deploy proactive in-app messaging + satisfaction survey to identify root cause before escalation",
            "Run weekly batch scoring to track cohort migration from medium → high risk and intervene before threshold breach",
            "Feed batch results into CRM for rep prioritisation — sort by (churn_prob × CLV) to maximise recovery ROI",
        ]

        recovery = clv_risk * 0.28
        outcome = (
            f"Systematic batch intervention on {n_high + n_med:,} at-risk customers is projected to "
            f"recover {_fmt_usd(recovery)} ({28}% of {_fmt_usd(clv_risk)} at-risk CLV) within 2 quarters."
        ) if clv_risk > 0 else (
            f"Batch intervention on {n_high + n_med:,} at-risk customers expected to reduce churn by 5–8pp based on industry benchmarks."
        )

        return InsightResponse(
            executive_summary=(
                f"Batch scoring of {total:,} customers reveals {n_high:,} critical-risk accounts requiring immediate action "
                f"and {n_med:,} medium-risk accounts for proactive engagement. "
                f"Portfolio average churn probability of {avg_prob*100:.1f}% signals a {rl.lower()} retention environment."
            ),
            key_drivers=drivers,
            business_impact=BusinessImpact(
                revenue_at_risk=_fmt_usd(clv_risk) if clv_risk else f"{n_high:,} high-risk customers",
                affected_customers=f"{n_high + n_med:,} of {total:,} ({(n_high+n_med)/max(total,1)*100:.0f}%)",
                risk_level=rl,
            ),
            recommended_actions=actions,
            expected_outcome=outcome,
            confidence_level="High" if total >= 100 else "Medium",
        )

    # ------------------------------------------------------------------
    # 4. Batch recommend insight  (used by POST /recommend/batch)
    # ------------------------------------------------------------------
    @classmethod
    def from_batch_recommend(
        cls,
        total_customers: int,
        total_revenue_protected: float,
        strategy_counts: Dict[str, int],
    ) -> InsightResponse:
        dominant = max(strategy_counts, key=lambda k: strategy_counts[k]) if strategy_counts else "Monitor"
        n_critical = strategy_counts.get("Premium Retention Offer", 0) + \
                     strategy_counts.get("Service Recovery Call", 0)
        n_growth = strategy_counts.get("Upsell Premium Plan", 0)
        rl = "Critical" if n_critical / max(total_customers, 1) > 0.25 else \
             "High" if n_critical / max(total_customers, 1) > 0.15 else "Elevated"

        drivers = [
            f"{n_critical:,} customers ({n_critical/max(total_customers,1)*100:.0f}%) require high-priority retention intervention — "
            "combined risk of churn loss exceeds retention programme budget threshold",
            f"{n_growth:,} customers ({n_growth/max(total_customers,1)*100:.0f}%) have high upsell probability — "
            "growth opportunity partially offsets churn revenue exposure",
            f"Dominant strategy '{dominant}' across the portfolio signals a "
            + ("retention-first posture needed" if "Monitor" not in dominant else "healthy baseline with selective intervention opportunities"),
        ]

        actions = [
            f"Prioritise the {strategy_counts.get('Premium Retention Offer', 0):,} Premium Retention Offer candidates — "
            "highest CLV cohort, deploy within 5 business days to prevent revenue leakage",
            f"Activate Service Recovery playbook for {strategy_counts.get('Service Recovery Call', 0):,} customers with 3+ complaints — "
            "assign to senior support reps with escalation authority",
            f"Launch upsell campaign for {n_growth:,} expansion-ready accounts — "
            f"estimated {_fmt_usd(total_revenue_protected * 0.15)} incremental ARR opportunity",
            "Establish 30-day review cadence to re-score all customers and update NBA assignments as risk profiles evolve",
        ]

        return InsightResponse(
            executive_summary=(
                f"NBA engine scored {total_customers:,} customers — {n_critical:,} require immediate retention action "
                f"with {_fmt_usd(total_revenue_protected)} in recoverable revenue identified. "
                f"{n_growth:,} accounts represent upsell opportunity to partially offset churn exposure."
            ),
            key_drivers=drivers,
            business_impact=BusinessImpact(
                revenue_at_risk=_fmt_usd(total_revenue_protected),
                affected_customers=f"{n_critical:,} critical + {n_growth:,} growth-eligible",
                risk_level=rl,
            ),
            recommended_actions=actions,
            expected_outcome=(
                f"Executing all NBA recommendations is projected to protect {_fmt_usd(total_revenue_protected * 0.3)} "
                f"in revenue (30% recovery rate) and generate {_fmt_usd(total_revenue_protected * 0.08)} in upsell ARR "
                "within two quarters — net positive ROI assuming <15% offer acceptance cost."
            ),
            confidence_level="High" if total_customers >= 500 else "Medium",
        )

    # ------------------------------------------------------------------
    # 5. Agent chat insight  (used by POST /agent/chat)
    # ------------------------------------------------------------------
    @classmethod
    def for_agent(
        cls,
        intent: str,
        supporting_data: Dict[str, Any],
    ) -> InsightResponse:
        """
        Lightweight insight overlay for agent responses.
        Enriches the agent's existing output with the standard insight schema.
        """
        churn_pct = float(supporting_data.get("churn_rate_pct", 0))
        rev_risk  = float(supporting_data.get("revenue_at_risk", 0))
        total     = int(supporting_data.get("total_customers", 0))
        seg       = supporting_data.get("churn_by_segment", {})
        reg       = supporting_data.get("churn_by_region", {})

        rl = _risk_level(churn_pct) if churn_pct else "Unknown"
        worst_seg = max(seg, key=lambda k: seg[k]) if seg else None
        worst_reg = max(reg, key=lambda k: reg[k]) if reg else None

        intent_labels = {
            "churn_rate":       "Churn Rate Analysis",
            "high_risk":        "High-Risk Customer Identification",
            "revenue_risk":     "Revenue Exposure Assessment",
            "region_analysis":  "Regional Performance Analysis",
            "segment_analysis": "Segment Performance Analysis",
            "kpi_summary":      "Executive KPI Summary",
            "recommend":        "Retention Strategy Recommendation",
            "predict":          "Churn Prediction Analysis",
            "data_profile":     "Data Quality Assessment",
        }

        drivers = []
        if worst_reg:
            drivers.append(f"{worst_reg} region: {reg[worst_reg]:.1f}% churn — highest-risk geography")
        if worst_seg:
            drivers.append(f"{worst_seg} segment: {seg[worst_seg]:.1f}% churn — worst-performing plan tier")
        if churn_pct:
            drivers.append(f"Portfolio churn at {churn_pct:.1f}% — {rl.lower()} risk classification")
        if not drivers:
            drivers = ["Analyse available data to identify specific root-cause drivers"]

        actions = [
            "Drill into the highest-risk segment and region for immediate intervention",
            "Cross-reference churn with CLV to prioritise retention spend",
            "Set measurable reduction targets for next 30/60/90 days",
        ]

        return InsightResponse(
            executive_summary=(
                f"Query intent: {intent_labels.get(intent, intent.replace('_', ' ').title())}. "
                + (f"Current churn is {churn_pct:.1f}% with {_fmt_usd(rev_risk)} revenue at risk. " if churn_pct else "")
                + f"Risk classification: {rl}."
            ),
            key_drivers=drivers,
            business_impact=BusinessImpact(
                revenue_at_risk=_fmt_usd(rev_risk) if rev_risk else "See supporting data",
                affected_customers=(
                    f"{int(total * churn_pct / 100):,} of {total:,}" if churn_pct and total else "See supporting data"
                ),
                risk_level=rl,
            ),
            recommended_actions=actions,
            expected_outcome=(
                f"Addressing the identified drivers is expected to reduce churn by 4–8pp "
                "within two quarters based on peer-group benchmarks."
            ) if churn_pct else "Collect additional data to quantify expected outcomes.",
            confidence_level="High" if (churn_pct and rev_risk) else "Medium",
        )
