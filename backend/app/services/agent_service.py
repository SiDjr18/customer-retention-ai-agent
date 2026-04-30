"""
AgentService — deterministic intent-routing AI assistant.

Works without any paid API key.  Uses keyword/rule-based intent classification
and routes each intent to the appropriate internal service.

Intents:
  churn_rate        — "what is the churn rate / overall churn"
  high_risk         — "show high risk customers / most likely to churn"
  revenue_risk      — "revenue at risk / financial exposure"
  region_analysis   — "region / state breakdown / geographic"
  segment_analysis  — "segment / enterprise / SMB / consumer"
  kpi_summary       — "kpis / summary / overview / dashboard"
  recommend         — "recommend / retention / strategy / action plan"
  predict           — "predict / score / model / churn probability"
  data_profile      — "profile / data quality / missing / duplicates"
  unknown           — fallback
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from app.schemas.agent_schema import (
    AgentChatRequest,
    AgentChatResponse,
    RecommendedAction,
    BusinessImpact,
)
from app.services.dataset_service import DatasetService
from app.services.recommendation_service import RecommendationService
from app.schemas.dataset import FilterRequest
from app.decision_engine.insight_engine import InsightEngine

# ---------------------------------------------------------------------------
# Intent patterns
# ---------------------------------------------------------------------------
_INTENT_PATTERNS: List[Tuple[str, List[str]]] = [
    ("churn_rate",       ["churn rate", "overall churn", "how many churn", "% churn", "churning"]),
    ("high_risk",        ["high risk", "most likely to churn", "at risk customers", "top risk", "risky customers"]),
    ("revenue_risk",     ["revenue at risk", "financial exposure", "revenue impact", "money at risk", "clv at risk"]),
    ("region_analysis",  ["region", "state", "geographic", "north", "south", "east", "west", "city tier"]),
    ("segment_analysis", ["segment", "enterprise", "smb", "consumer", "mid-market", "customer type"]),
    ("kpi_summary",      ["kpi", "summary", "overview", "dashboard", "metrics", "scorecard", "how are we doing"]),
    ("recommend",        ["recommend", "retention", "strategy", "action plan", "what should", "next best", "nba"]),
    ("predict",          ["predict", "prediction", "score", "probability", "model", "likelihood"]),
    ("data_profile",     ["profile", "data quality", "missing values", "duplicates", "column", "data issues"]),
]


def _classify_intent(message: str) -> str:
    """Return the intent label for the user message."""
    lower = message.lower()
    for intent, keywords in _INTENT_PATTERNS:
        if any(kw in lower for kw in keywords):
            return intent
    return "unknown"


def _extract_region(message: str) -> Optional[str]:
    """Try to extract a region name from the message."""
    regions = ["north", "south", "east", "west", "central", "northeast", "northwest",
               "southeast", "southwest", "midwest"]
    lower = message.lower()
    for r in regions:
        if r in lower:
            return r.title()
    return None


def _extract_segment(message: str) -> Optional[str]:
    """Try to extract a segment name from the message."""
    segments = ["enterprise", "smb", "consumer", "mid-market", "premium", "standard", "basic"]
    lower = message.lower()
    for s in segments:
        if s in lower:
            return s.title()
    return None


# ---------------------------------------------------------------------------
# Helpers for consulting-grade formatting
# ---------------------------------------------------------------------------

def _conf(score: float) -> str:
    """Convert 0–1 probability to a labelled confidence tier."""
    if score >= 0.88:
        return "High"
    if score >= 0.75:
        return "Medium"
    return "Low"


def _risk_level(churn_pct: float) -> str:
    """Map churn percentage to an executive risk label."""
    if churn_pct >= 25:
        return "Critical"
    if churn_pct >= 20:
        return "High"
    if churn_pct >= 15:
        return "Elevated"
    return "Moderate"


def _fmt_usd(value: float) -> str:
    """Format a float as a compact USD string."""
    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"${value / 1_000:.0f}K"
    return f"${value:,.0f}"


def _action(priority: str, action: str, rationale: str) -> RecommendedAction:
    return RecommendedAction(priority=priority, action=action, rationale=rationale)


# ---------------------------------------------------------------------------
# AgentService
# ---------------------------------------------------------------------------

class AgentService:
    """Rule-based intent router that orchestrates internal services."""

    def __init__(self) -> None:
        self._data_svc: Optional[DatasetService] = None
        self._reco_svc: Optional[RecommendationService] = None

    def _ds(self) -> DatasetService:
        if self._data_svc is None:
            self._data_svc = DatasetService()
        return self._data_svc

    def _rs(self) -> RecommendationService:
        if self._reco_svc is None:
            self._reco_svc = RecommendationService()
        return self._reco_svc

    # ------------------------------------------------------------------
    # Routing table
    # ------------------------------------------------------------------

    def handle(self, req: AgentChatRequest) -> AgentChatResponse:
        intent = _classify_intent(req.message)
        handlers = {
            "churn_rate":       self._handle_churn_rate,
            "high_risk":        self._handle_high_risk,
            "revenue_risk":     self._handle_revenue_risk,
            "region_analysis":  self._handle_region_analysis,
            "segment_analysis": self._handle_segment_analysis,
            "kpi_summary":      self._handle_kpi_summary,
            "recommend":        self._handle_recommend,
            "predict":          self._handle_predict,
            "data_profile":     self._handle_data_profile,
            "unknown":          self._handle_unknown,
        }
        handler = handlers.get(intent, self._handle_unknown)
        response = handler(req, intent)
        # Augment every response with the decision engine insight overlay
        try:
            response.insight = InsightEngine.for_agent(
                intent=intent,
                supporting_data=response.supporting_data or {},
            )
        except Exception:
            pass  # insight is non-blocking
        return response

    # ------------------------------------------------------------------
    # Intent handlers
    # ------------------------------------------------------------------

    def _handle_churn_rate(self, req: AgentChatRequest, intent: str) -> AgentChatResponse:
        kpis = self._ds().kpis()
        churned_count = int(kpis.total_customers * kpis.churn_rate_pct / 100)
        tools = ["dataset_service.kpis"]
        top_region = max(kpis.churn_by_region, key=kpis.churn_by_region.get, default="N/A")
        top_seg = max(kpis.churn_by_segment, key=kpis.churn_by_segment.get, default="N/A")
        return AgentChatResponse(
            intent=intent,
            executive_summary=(
                f"The overall customer churn rate stands at {kpis.churn_rate_pct:.1f}%, "
                f"representing approximately {churned_count:,} customers out of "
                f"{kpis.total_customers:,} total. "
                f"Revenue exposure from churned accounts is {_fmt_usd(kpis.revenue_at_risk)}, "
                f"with the highest churn concentration in the {top_region} region."
            ),
            key_insights=[
                f"Churn rate of {kpis.churn_rate_pct:.1f}% classifies as {_risk_level(kpis.churn_rate_pct)} risk",
                f"Approximately {churned_count:,} customers have churned or are at high risk",
                f"Revenue at risk: {_fmt_usd(kpis.revenue_at_risk)} based on churned CLV",
                f"Worst-performing region: {top_region} ({kpis.churn_by_region.get(top_region, 0):.1f}% churn)",
                f"Highest-churn segment: {top_seg} ({kpis.churn_by_segment.get(top_seg, 0):.1f}% churn)",
            ],
            business_impact=BusinessImpact(
                revenue_at_risk=_fmt_usd(kpis.revenue_at_risk),
                affected_customers=churned_count,
                risk_level=_risk_level(kpis.churn_rate_pct),
            ),
            recommended_actions=[
                _action("High",   "Launch targeted retention campaign in highest-churn region",
                        f"{top_region} shows the highest churn — immediate intervention prevents outsized revenue loss"),
                _action("High",   "Prioritise CLV-weighted outreach to churned accounts",
                        f"Recovering even 20% of {_fmt_usd(kpis.revenue_at_risk)} at risk justifies significant retention spend"),
                _action("Medium", "Set automated churn-rate threshold alert at current rate + 2pp",
                        "Early warning allows proactive response before churn compounds"),
                _action("Low",    "Present churn KPI trend in next leadership review",
                        "Executive visibility drives cross-functional accountability"),
            ],
            confidence_level=_conf(0.95),
            tools_used=tools,
            supporting_data={
                "churn_rate_pct": kpis.churn_rate_pct,
                "total_customers": kpis.total_customers,
                "churned_count": churned_count,
                "churn_by_region": kpis.churn_by_region,
                "churn_by_segment": kpis.churn_by_segment,
            },
        )

    def _handle_high_risk(self, req: AgentChatRequest, intent: str) -> AgentChatResponse:
        region = _extract_region(req.message)
        result = self._ds().filter_data(FilterRequest(region=region, limit=20))
        records_sorted = sorted(
            result.records,
            key=lambda r: float(r.get("churn_risk_score") or r.get("risk_score") or 0),
            reverse=True,
        )[:10]
        scope = f"in the {region} region" if region else "across all regions"
        top_score = records_sorted[0].get("churn_risk_score", "N/A") if records_sorted else "N/A"
        tools = ["dataset_service.filter_data"]
        return AgentChatResponse(
            intent=intent,
            executive_summary=(
                f"Identified {result.total_matches:,} customers at elevated churn risk {scope}. "
                f"The top 10 highest-risk accounts have been surfaced for immediate review, "
                f"with a peak churn risk score of {top_score}."
            ),
            key_insights=[
                f"{result.total_matches:,} customers flagged as high-risk {scope}",
                f"Peak churn risk score in cohort: {top_score}",
                f"Filters applied: {result.filters_applied or 'none (all regions)'}",
                "Top 10 accounts ranked by churn risk score available in supporting data",
                "Cross-referencing with CLV will identify the highest-value accounts to prioritise",
            ],
            business_impact=BusinessImpact(
                revenue_at_risk=None,
                affected_customers=result.total_matches,
                risk_level="High" if result.total_matches > 100 else "Elevated",
            ),
            recommended_actions=[
                _action("High",   "Initiate outreach to top 10 customers by churn risk score",
                        "Highest-risk accounts are most likely to churn within 30 days — act now"),
                _action("High",   "Cross-reference risk list with CLV to rank by business impact",
                        "High-risk + high-CLV customers represent the greatest revenue exposure"),
                _action("Medium", "Route Critical-score customers to dedicated retention team",
                        "Specialised handling improves conversion rates for at-risk accounts"),
                _action("Low",    "Schedule monthly review of high-risk cohort movement",
                        "Tracking cohort migration reveals whether interventions are working"),
            ],
            confidence_level=_conf(0.88),
            tools_used=tools,
            supporting_data={"top_high_risk_customers": records_sorted,
                             "total_in_scope": result.total_matches},
        )

    def _handle_revenue_risk(self, req: AgentChatRequest, intent: str) -> AgentChatResponse:
        kpis = self._ds().kpis()
        churned_count = int(kpis.total_customers * kpis.churn_rate_pct / 100)
        top_region = max(kpis.churn_by_region, key=kpis.churn_by_region.get, default="N/A")
        tools = ["dataset_service.kpis"]
        return AgentChatResponse(
            intent=intent,
            executive_summary=(
                f"Total revenue at risk from churned customers is {_fmt_usd(kpis.revenue_at_risk)}, "
                f"driven by a {kpis.churn_rate_pct:.1f}% churn rate across {kpis.total_customers:,} customers. "
                f"Average Customer Lifetime Value of {_fmt_usd(kpis.avg_clv)} means each prevented churn "
                f"directly protects significant long-term revenue."
            ),
            key_insights=[
                f"Revenue at risk: {_fmt_usd(kpis.revenue_at_risk)} ({kpis.churn_rate_pct:.1f}% of base churned)",
                f"Average CLV: {_fmt_usd(kpis.avg_clv)} — benchmark for retention ROI decisions",
                f"Highest churn region: {top_region} ({kpis.churn_by_region.get(top_region, 0):.1f}%)",
                f"Risk classification: {_risk_level(kpis.churn_rate_pct)} — immediate action warranted",
                f"Recovering 20% of at-risk revenue would yield {_fmt_usd(kpis.revenue_at_risk * 0.20)}",
            ],
            business_impact=BusinessImpact(
                revenue_at_risk=_fmt_usd(kpis.revenue_at_risk),
                affected_customers=churned_count,
                risk_level=_risk_level(kpis.churn_rate_pct),
            ),
            recommended_actions=[
                _action("High",   "Allocate retention budget proportional to CLV × churn probability",
                        f"Expected ROI is highest when spend is concentrated on high-CLV accounts near the decision threshold"),
                _action("High",   f"Deploy emergency retention offers in {top_region} — highest churn region",
                        "Geographic concentration of churn allows cost-efficient targeted campaigns"),
                _action("Medium", "Model break-even retention cost vs. average CLV",
                        f"Any offer under {_fmt_usd(kpis.avg_clv * 0.15)} per customer is likely ROI-positive"),
                _action("Low",    "Present revenue-at-risk metric in next leadership review",
                        "Executive visibility aligns cross-functional teams on the financial stakes"),
            ],
            confidence_level=_conf(0.90),
            tools_used=tools,
            supporting_data={
                "revenue_at_risk": kpis.revenue_at_risk,
                "avg_clv": kpis.avg_clv,
                "churn_rate_pct": kpis.churn_rate_pct,
                "churn_by_region": kpis.churn_by_region,
            },
        )

    def _handle_region_analysis(self, req: AgentChatRequest, intent: str) -> AgentChatResponse:
        kpis = self._ds().kpis()
        region = _extract_region(req.message)
        churn_by_region = kpis.churn_by_region
        worst_region = max(churn_by_region, key=churn_by_region.get, default="N/A") if churn_by_region else "N/A"
        worst_rate = churn_by_region.get(worst_region, 0.0)
        best_region = min(churn_by_region, key=churn_by_region.get, default="N/A") if churn_by_region else "N/A"
        best_rate = churn_by_region.get(best_region, 0.0)
        spread = round(worst_rate - best_rate, 1)
        tools = ["dataset_service.kpis"]
        return AgentChatResponse(
            intent=intent,
            executive_summary=(
                f"Regional analysis reveals a {spread:.1f} percentage-point spread in churn rates, "
                f"with {worst_region} leading at {worst_rate:.1f}% and {best_region} as the "
                f"best performer at {best_rate:.1f}%. "
                + (f"Requested focus region '{region}': {churn_by_region.get(region, 'N/A')}% churn." if region else "")
            ),
            key_insights=[
                f"Highest churn region: {worst_region} ({worst_rate:.1f}%)",
                f"Lowest churn region: {best_region} ({best_rate:.1f}%)",
                f"Regional churn spread: {spread:.1f}pp — indicates structural performance gaps",
                f"Regions tracked: {len(churn_by_region)}",
                "All regions (churn %): " + " | ".join(
                    f"{r} {v:.1f}%" for r, v in sorted(churn_by_region.items(), key=lambda x: -x[1])
                ),
            ],
            business_impact=BusinessImpact(
                revenue_at_risk=None,
                affected_customers=None,
                risk_level=_risk_level(worst_rate),
            ),
            recommended_actions=[
                _action("High",   f"Deploy targeted retention campaign in {worst_region} first",
                        f"At {worst_rate:.1f}% churn, {worst_region} is the highest-priority region for immediate intervention"),
                _action("Medium", f"Investigate competitive or service-quality pressures in {worst_region}",
                        "Understanding root cause drives sustainable churn reduction, not just short-term offers"),
                _action("Medium", f"Replicate successful practices from {best_region} across other regions",
                        f"{best_region} at {best_rate:.1f}% demonstrates what good looks like — capture and transfer that playbook"),
                _action("Low",    "Benchmark regional NPS scores against churn rates",
                        "Satisfaction scores often lead churn by 1–2 quarters — early warning signal"),
            ],
            confidence_level=_conf(0.87),
            tools_used=tools,
            supporting_data={"churn_by_region": churn_by_region},
        )

    def _handle_segment_analysis(self, req: AgentChatRequest, intent: str) -> AgentChatResponse:
        kpis = self._ds().kpis()
        segment = _extract_segment(req.message)
        churn_by_seg = kpis.churn_by_segment
        worst_seg = max(churn_by_seg, key=churn_by_seg.get, default="N/A") if churn_by_seg else "N/A"
        worst_seg_rate = churn_by_seg.get(worst_seg, 0.0)
        best_seg = min(churn_by_seg, key=churn_by_seg.get, default="N/A") if churn_by_seg else "N/A"
        best_seg_rate = churn_by_seg.get(best_seg, 0.0)
        tools = ["dataset_service.kpis"]
        return AgentChatResponse(
            intent=intent,
            executive_summary=(
                f"Segment analysis identifies {worst_seg} as the highest-churn cohort at "
                f"{worst_seg_rate:.1f}%, versus {best_seg} at {best_seg_rate:.1f}%. "
                + (f"Requested segment '{segment}': {churn_by_seg.get(segment, 'N/A')}% churn rate." if segment else "")
            ),
            key_insights=[
                f"Highest-churn segment: {worst_seg} ({worst_seg_rate:.1f}%)",
                f"Lowest-churn segment: {best_seg} ({best_seg_rate:.1f}%)",
                f"Segment churn spread: {round(worst_seg_rate - best_seg_rate, 1):.1f}pp across {len(churn_by_seg)} segments",
                "All segments (churn %): " + " | ".join(
                    f"{s} {v:.1f}%" for s, v in sorted(churn_by_seg.items(), key=lambda x: -x[1])
                ),
            ] + ([f"Requested segment '{segment}': {churn_by_seg.get(segment, 'N/A')}% churn"] if segment else []),
            business_impact=BusinessImpact(
                revenue_at_risk=None,
                affected_customers=None,
                risk_level=_risk_level(worst_seg_rate),
            ),
            recommended_actions=[
                _action("High",   f"Design segment-specific retention offer for {worst_seg} customers",
                        f"{worst_seg} at {worst_seg_rate:.1f}% churn requires a tailored intervention, not a generic campaign"),
                _action("High",   "Review product-market fit and pricing for high-churn segments",
                        "High churn in a segment often signals a mismatch between value proposition and customer expectations"),
                _action("Medium", "Map top churn drivers to segment-specific pain points",
                        "Segment-level root-cause analysis enables precise retention tactics"),
                _action("Low",    "Track segment churn month-over-month in the retention dashboard",
                        "Trend data reveals whether segment dynamics are worsening or responding to intervention"),
            ],
            confidence_level=_conf(0.86),
            tools_used=tools,
            supporting_data={"churn_by_segment": churn_by_seg},
        )

    def _handle_kpi_summary(self, req: AgentChatRequest, intent: str) -> AgentChatResponse:
        kpis = self._ds().kpis()
        churned_count = int(kpis.total_customers * kpis.churn_rate_pct / 100)
        tools = ["dataset_service.kpis"]
        return AgentChatResponse(
            intent=intent,
            executive_summary=(
                f"Retention scorecard: {kpis.total_customers:,} customers, "
                f"{kpis.churn_rate_pct:.1f}% churn rate ({_risk_level(kpis.churn_rate_pct)} risk), "
                f"{_fmt_usd(kpis.avg_clv)} average CLV, "
                f"and {_fmt_usd(kpis.revenue_at_risk)} total revenue at risk. "
                f"Average satisfaction score of {kpis.avg_satisfaction_score:.1f}/10 "
                f"and risk score of {kpis.avg_churn_risk_score:.2f} provide leading indicators."
            ),
            key_insights=[
                f"Total customers: {kpis.total_customers:,} | Churned: {churned_count:,}",
                f"Churn rate: {kpis.churn_rate_pct:.1f}% — classified as {_risk_level(kpis.churn_rate_pct)}",
                f"Revenue at risk: {_fmt_usd(kpis.revenue_at_risk)} from churned accounts",
                f"Average CLV: {_fmt_usd(kpis.avg_clv)} — sets retention offer ceiling",
                f"Avg satisfaction: {kpis.avg_satisfaction_score:.1f}/10 | Avg risk score: {kpis.avg_churn_risk_score:.2f}",
            ],
            business_impact=BusinessImpact(
                revenue_at_risk=_fmt_usd(kpis.revenue_at_risk),
                affected_customers=churned_count,
                risk_level=_risk_level(kpis.churn_rate_pct),
            ),
            recommended_actions=[
                _action("High",   "Prioritise retention spend on segments with above-average churn and CLV",
                        "Concentrating budget where churn rate × CLV is highest maximises revenue protection ROI"),
                _action("Medium", "Set automated threshold alerts for churn rate and revenue-at-risk",
                        "Real-time monitoring allows faster response before trends compound"),
                _action("Medium", "Drill into segments and regions showing above-average churn",
                        "KPI summary identifies where to look — segment/regional analysis reveals why"),
                _action("Low",    "Present this KPI snapshot in the weekly leadership review",
                        "Executive visibility drives cross-functional ownership of churn reduction targets"),
            ],
            confidence_level=_conf(0.95),
            tools_used=tools,
            supporting_data={
                "total_customers": kpis.total_customers,
                "churn_rate_pct": kpis.churn_rate_pct,
                "avg_clv": kpis.avg_clv,
                "revenue_at_risk": kpis.revenue_at_risk,
                "avg_churn_risk_score": kpis.avg_churn_risk_score,
                "avg_satisfaction_score": kpis.avg_satisfaction_score,
            },
        )

    def _handle_recommend(self, req: AgentChatRequest, intent: str) -> AgentChatResponse:
        segment = _extract_segment(req.message)
        region = _extract_region(req.message)
        summary = self._rs().strategy_summary()
        tools = ["recommendation_service.strategy_summary"]

        top_strategy = summary.strategies[0] if summary.strategies else None
        total_protected = sum(b.total_revenue_protected for b in summary.strategies)
        scope_desc = (f" for {segment} customers" if segment else "") + \
                     (f" in the {region} region" if region else "")

        return AgentChatResponse(
            intent=intent,
            executive_summary=(
                f"Retention strategy recommendations{scope_desc}: "
                + (
                    f"The leading action is '{top_strategy.strategy}', "
                    f"covering {top_strategy.customer_count:,} customers ({top_strategy.pct_of_total:.1f}%) "
                    f"with {_fmt_usd(top_strategy.total_revenue_protected)} estimated revenue protected. "
                    f"Total revenue protected across all strategies: {_fmt_usd(total_protected)}."
                    if top_strategy else "No strategy data available."
                )
            ),
            key_insights=[
                f"{b.strategy}: {b.customer_count:,} customers ({b.pct_of_total:.1f}%)"
                for b in summary.strategies
            ],
            business_impact=BusinessImpact(
                revenue_at_risk=None,
                affected_customers=sum(b.customer_count for b in summary.strategies),
                risk_level="High",
            ),
            recommended_actions=[
                _action("High",   "Execute Premium Retention Offers for Critical-priority customers this week",
                        "Critical accounts have the highest churn probability and CLV — delay increases revenue loss"),
                _action("High",   "Schedule Service Recovery Calls within 48 hours for complaint-heavy accounts",
                        "Unresolved complaints are a leading churn indicator — swift recovery rebuilds trust"),
                _action("Medium", "Route Upsell candidates to sales for plan upgrade conversations",
                        "Upsell increases CLV and stickiness simultaneously — highest ROI retention action"),
                _action("Low",    "Monitor 'Watch' segment monthly — no immediate action required",
                        "Low-risk accounts need periodic check-ins to prevent drift into higher-risk cohorts"),
            ],
            confidence_level=_conf(0.82),
            tools_used=tools,
            supporting_data={
                "strategy_breakdown": [b.model_dump() for b in summary.strategies],
                "total_revenue_protected": total_protected,
            },
        )

    def _handle_predict(self, req: AgentChatRequest, intent: str) -> AgentChatResponse:
        return AgentChatResponse(
            intent=intent,
            executive_summary=(
                "Churn prediction scores are generated by the ML engine via /predict/churn. "
                "Submit customer feature data — tenure, monthly charges, payment behaviour, "
                "support tickets — to receive a calibrated churn probability and risk tier. "
                "Batch scoring is available for fleet-level assessment."
            ),
            key_insights=[
                "Single prediction: POST /predict/churn with customer feature payload",
                "Batch scoring: POST /predict/batch for portfolio-level risk assessment",
                "Model metrics: GET /predict/metrics for accuracy, AUC, and feature importance",
                "Models evaluated: Logistic Regression, Random Forest, XGBoost",
            ],
            business_impact=BusinessImpact(
                revenue_at_risk=None,
                affected_customers=None,
                risk_level="Moderate",
            ),
            recommended_actions=[
                _action("High",   "Run batch prediction across full customer portfolio",
                        "Portfolio-level scoring identifies hidden at-risk accounts before churn occurs"),
                _action("Medium", "Review model metrics to validate prediction reliability",
                        "AUC > 0.80 confirms model is production-ready for business decisions"),
                _action("Low",    "Re-train model quarterly on fresh data",
                        "Customer behaviour drifts over time — regular retraining maintains predictive accuracy"),
            ],
            confidence_level=_conf(0.70),
            tools_used=["prediction_service (info only)"],
            supporting_data=None,
        )

    def _handle_data_profile(self, req: AgentChatRequest, intent: str) -> AgentChatResponse:
        profile = self._ds().profile()
        tools = ["dataset_service.profile"]
        high_null_cols = [c.name for c in profile.missing_values_report if c.null_pct > 10]
        data_quality = "Good" if not high_null_cols and profile.duplicate_rows == 0 else \
                       "Fair" if len(high_null_cols) <= 2 else "Poor"
        return AgentChatResponse(
            intent=intent,
            executive_summary=(
                f"Dataset quality assessment: {profile.total_rows:,} rows × "
                f"{profile.total_columns} columns, {profile.duplicate_rows} duplicate rows, "
                f"{len(profile.missing_values_report)} columns with missing values. "
                f"Overall data quality is rated {data_quality}."
            ),
            key_insights=[
                f"Shape: {profile.total_rows:,} rows × {profile.total_columns} columns",
                f"Duplicate rows: {profile.duplicate_rows} ({profile.duplicate_rows / max(profile.total_rows,1)*100:.2f}%)",
                f"Columns with any nulls: {len(profile.missing_values_report)}",
                f"High-null columns (>10%): {', '.join(high_null_cols) if high_null_cols else 'None'}",
                f"Data quality rating: {data_quality}",
            ],
            business_impact=BusinessImpact(
                revenue_at_risk=None,
                affected_customers=None,
                risk_level="Moderate" if data_quality == "Good" else "Elevated",
            ),
            recommended_actions=[
                _action("High",   "Impute or drop columns with >30% missing values before modelling",
                        "High-null features introduce bias and degrade model accuracy — address before next training run"),
                _action("High",   "Remove duplicate rows to prevent training data leakage",
                        f"{profile.duplicate_rows} duplicates can cause overfitting and inflated accuracy metrics"),
                _action("Medium", "Investigate root cause of high-null columns in data pipeline",
                        "Missing data often signals upstream collection failures — fix the source, not just the symptom"),
                _action("Low",    "Schedule automated data quality checks on each new data load",
                        "Proactive monitoring prevents silent data degradation from reaching production models"),
            ],
            confidence_level=_conf(0.92),
            tools_used=tools,
            supporting_data={
                "shape": {"rows": profile.total_rows, "columns": profile.total_columns},
                "duplicates": profile.duplicate_rows,
                "high_null_columns": high_null_cols,
                "data_quality": data_quality,
            },
        )

    def _handle_unknown(self, req: AgentChatRequest, intent: str) -> AgentChatResponse:
        return AgentChatResponse(
            intent="unknown",
            executive_summary=(
                "The query could not be matched to a known intent. "
                "This assistant covers churn analysis, revenue risk, regional and segment breakdowns, "
                "retention strategy, churn prediction, and data quality. "
                "Please rephrase using one of the example queries below."
            ),
            key_insights=[
                "Intent not recognised — no data was fetched",
                "Supported topics: churn rate, revenue risk, high-risk customers, region analysis",
                "Supported topics: segment analysis, KPI summary, retention recommendations, predictions",
            ],
            business_impact=BusinessImpact(
                revenue_at_risk=None,
                affected_customers=None,
                risk_level="Moderate",
            ),
            recommended_actions=[
                _action("High",   "Try: 'What is the overall churn rate?'",
                        "Returns churn rate, affected customer count, and revenue at risk"),
                _action("Medium", "Try: 'Show top high-risk customers in the South region'",
                        "Returns ranked list of customers by churn risk score with filters applied"),
                _action("Medium", "Try: 'Recommend a retention strategy for premium customers'",
                        "Returns strategy breakdown and prioritised action plan"),
                _action("Low",    "Try: 'Which region has the highest revenue at risk?'",
                        "Returns regional churn breakdown ranked by business impact"),
            ],
            confidence_level="Low",
            tools_used=[],
            supporting_data=None,
        )
