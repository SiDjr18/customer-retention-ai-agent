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

from app.schemas.agent_schema import AgentChatRequest, AgentChatResponse
from app.services.dataset_service import DatasetService
from app.services.recommendation_service import RecommendationService
from app.schemas.dataset import FilterRequest

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
# Response builders
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
        return handler(req, intent)

    # ------------------------------------------------------------------
    # Intent handlers
    # ------------------------------------------------------------------

    def _handle_churn_rate(self, req: AgentChatRequest, intent: str) -> AgentChatResponse:
        kpis = self._ds().kpis()
        tools = ["dataset_service.kpis"]
        return AgentChatResponse(
            intent=intent,
            executive_summary=(
                f"The overall customer churn rate is {kpis.churn_rate_pct:.1f}%. "
                f"Out of {kpis.total_customers:,} customers, "
                f"approximately {int(kpis.total_customers * kpis.churn_rate_pct / 100):,} "
                f"are classified as churned."
            ),
            key_findings=[
                f"Churn rate: {kpis.churn_rate_pct:.1f}%",
                f"Total customers: {kpis.total_customers:,}",
                f"Revenue at risk: ${kpis.revenue_at_risk:,.0f}",
                f"Avg churn risk score: {kpis.avg_churn_risk_score:.2f}",
            ],
            recommended_actions=[
                "Focus retention spend on the highest CLV churned segment.",
                "Investigate root causes in highest-churn regions.",
                "Set a target churn rate reduction goal for next quarter.",
            ],
            supporting_data={
                "churn_rate_pct": kpis.churn_rate_pct,
                "total_customers": kpis.total_customers,
                "churn_by_region": kpis.churn_by_region,
                "churn_by_segment": kpis.churn_by_segment,
            },
            confidence_level=0.95,
            tools_used=tools,
        )

    def _handle_high_risk(self, req: AgentChatRequest, intent: str) -> AgentChatResponse:
        region = _extract_region(req.message)
        filter_req = FilterRequest(
            region=region,
            limit=20,
        )
        result = self._ds().filter_data(filter_req)
        # Sort by churn_risk_score if present
        records = result.records
        records_sorted = sorted(
            records,
            key=lambda r: float(r.get("churn_risk_score") or r.get("risk_score") or 0),
            reverse=True,
        )[:10]
        scope = f"in the {region} region" if region else "across all regions"
        tools = ["dataset_service.filter_data"]
        return AgentChatResponse(
            intent=intent,
            executive_summary=(
                f"There are {result.total_matches:,} customers {scope} matching the current filters. "
                f"The top 10 highest-risk customers are shown in the supporting data."
            ),
            key_findings=[
                f"Total customers in scope: {result.total_matches:,}",
                f"Filters applied: {result.filters_applied or 'none'}",
                f"Top risk score in group: {records_sorted[0].get('churn_risk_score', 'N/A') if records_sorted else 'N/A'}",
            ],
            recommended_actions=[
                "Prioritise outreach to the top 10 customers by churn risk score.",
                "Cross-reference with CLV to focus on high-value at-risk accounts.",
                "Route Critical-priority customers to the dedicated retention team.",
            ],
            supporting_data={"top_high_risk_customers": records_sorted},
            confidence_level=0.88,
            tools_used=tools,
        )

    def _handle_revenue_risk(self, req: AgentChatRequest, intent: str) -> AgentChatResponse:
        kpis = self._ds().kpis()
        tools = ["dataset_service.kpis"]
        return AgentChatResponse(
            intent=intent,
            executive_summary=(
                f"Total revenue at risk from churned customers is "
                f"${kpis.revenue_at_risk:,.0f}. "
                f"Average Customer Lifetime Value is ${kpis.avg_clv:,.0f}."
            ),
            key_findings=[
                f"Revenue at risk: ${kpis.revenue_at_risk:,.2f}",
                f"Average CLV: ${kpis.avg_clv:,.2f}",
                f"Churn rate: {kpis.churn_rate_pct:.1f}%",
                f"Top churn region: {max(kpis.churn_by_region, key=kpis.churn_by_region.get, default='N/A')}",
            ],
            recommended_actions=[
                "Allocate retention budget proportional to CLV × churn probability.",
                "Model ROI of retention offers vs. revenue at risk.",
                "Present revenue-at-risk metric in the next leadership review.",
            ],
            supporting_data={
                "revenue_at_risk": kpis.revenue_at_risk,
                "avg_clv": kpis.avg_clv,
                "churn_by_region": kpis.churn_by_region,
            },
            confidence_level=0.90,
            tools_used=tools,
        )

    def _handle_region_analysis(self, req: AgentChatRequest, intent: str) -> AgentChatResponse:
        kpis = self._ds().kpis()
        region = _extract_region(req.message)
        tools = ["dataset_service.kpis"]

        churn_by_region = kpis.churn_by_region
        if churn_by_region:
            worst_region = max(churn_by_region, key=churn_by_region.get)
            worst_rate = churn_by_region[worst_region]
        else:
            worst_region, worst_rate = "N/A", 0.0

        return AgentChatResponse(
            intent=intent,
            executive_summary=(
                f"Regional churn analysis shows that **{worst_region}** has the highest churn rate "
                f"at {worst_rate:.1f}%. "
                + (f"Focus region: {region}." if region else "")
            ),
            key_findings=[
                f"Highest churn region: {worst_region} ({worst_rate:.1f}%)",
                f"Total regions tracked: {len(churn_by_region)}",
            ] + [f"{r}: {v:.1f}%" for r, v in sorted(churn_by_region.items(), key=lambda x: -x[1])],
            recommended_actions=[
                f"Deploy targeted retention campaign in {worst_region} first.",
                "Investigate service quality or competitive pressure in high-churn regions.",
                "Benchmark regional NPS scores against churn rates.",
            ],
            supporting_data={"churn_by_region": churn_by_region},
            confidence_level=0.87,
            tools_used=tools,
        )

    def _handle_segment_analysis(self, req: AgentChatRequest, intent: str) -> AgentChatResponse:
        kpis = self._ds().kpis()
        segment = _extract_segment(req.message)
        tools = ["dataset_service.kpis"]

        churn_by_seg = kpis.churn_by_segment
        worst_seg = max(churn_by_seg, key=churn_by_seg.get, default="N/A") if churn_by_seg else "N/A"
        worst_seg_rate = churn_by_seg.get(worst_seg, 0.0)

        return AgentChatResponse(
            intent=intent,
            executive_summary=(
                f"Segment analysis reveals that **{worst_seg}** has the highest churn rate at "
                f"{worst_seg_rate:.1f}%. "
                + (f"Requested segment '{segment}' churn rate: {churn_by_seg.get(segment, 'N/A')}%." if segment else "")
            ),
            key_findings=[
                f"Highest-churn segment: {worst_seg} ({worst_seg_rate:.1f}%)",
            ] + [f"{s}: {v:.1f}%" for s, v in sorted(churn_by_seg.items(), key=lambda x: -x[1])],
            recommended_actions=[
                f"Design segment-specific retention offers for {worst_seg} customers.",
                "Review product-market fit and pricing for high-churn segments.",
                "Map churn drivers to segment-specific pain points.",
            ],
            supporting_data={"churn_by_segment": churn_by_seg},
            confidence_level=0.86,
            tools_used=tools,
        )

    def _handle_kpi_summary(self, req: AgentChatRequest, intent: str) -> AgentChatResponse:
        kpis = self._ds().kpis()
        tools = ["dataset_service.kpis"]
        return AgentChatResponse(
            intent=intent,
            executive_summary=(
                f"Customer retention performance summary: {kpis.total_customers:,} total customers, "
                f"{kpis.churn_rate_pct:.1f}% churn rate, ${kpis.avg_clv:,.0f} average CLV, "
                f"and ${kpis.revenue_at_risk:,.0f} revenue at risk."
            ),
            key_findings=[
                f"Total customers: {kpis.total_customers:,}",
                f"Churn rate: {kpis.churn_rate_pct:.1f}%",
                f"Avg CLV: ${kpis.avg_clv:,.2f}",
                f"Revenue at risk: ${kpis.revenue_at_risk:,.2f}",
                f"Avg churn risk score: {kpis.avg_churn_risk_score:.2f}",
                f"Avg satisfaction score: {kpis.avg_satisfaction_score:.2f}",
            ],
            recommended_actions=[
                "Present this KPI snapshot in the weekly leadership review.",
                "Set threshold alerts for churn rate and revenue-at-risk.",
                "Drill into segments and regions showing above-average churn.",
            ],
            supporting_data={
                "total_customers": kpis.total_customers,
                "churn_rate_pct": kpis.churn_rate_pct,
                "avg_clv": kpis.avg_clv,
                "revenue_at_risk": kpis.revenue_at_risk,
                "avg_churn_risk_score": kpis.avg_churn_risk_score,
                "avg_satisfaction_score": kpis.avg_satisfaction_score,
            },
            confidence_level=0.95,
            tools_used=tools,
        )

    def _handle_recommend(self, req: AgentChatRequest, intent: str) -> AgentChatResponse:
        segment = _extract_segment(req.message)
        region = _extract_region(req.message)
        summary = self._rs().strategy_summary()
        tools = ["recommendation_service.strategy_summary"]

        top_strategy = summary.strategies[0] if summary.strategies else None
        scope_desc = f" for {segment} customers" if segment else ""
        scope_desc += f" in the {region} region" if region else ""

        return AgentChatResponse(
            intent=intent,
            executive_summary=(
                f"Retention strategy recommendation{scope_desc}: "
                + (
                    f"The most prevalent action is '{top_strategy.strategy}' "
                    f"covering {top_strategy.customer_count:,} customers "
                    f"({top_strategy.pct_of_total:.1f}%) with "
                    f"${top_strategy.total_revenue_protected:,.0f} estimated revenue protected."
                    if top_strategy else "No strategy data available."
                )
            ),
            key_findings=[
                f"{b.strategy}: {b.customer_count} customers ({b.pct_of_total:.1f}%)"
                for b in summary.strategies
            ],
            recommended_actions=[
                "Execute Premium Retention Offers for Critical-priority customers this week.",
                "Schedule Service Recovery Calls within 48 hours for complaint-heavy accounts.",
                "Route Upsell candidates to the sales team for plan upgrade conversations.",
                "Monitor 'Monitor' segment monthly — no immediate action required.",
            ],
            supporting_data={
                "strategy_breakdown": [b.model_dump() for b in summary.strategies],
                "total_revenue_protected": sum(b.total_revenue_protected for b in summary.strategies),
            },
            confidence_level=0.82,
            tools_used=tools,
        )

    def _handle_predict(self, req: AgentChatRequest, intent: str) -> AgentChatResponse:
        return AgentChatResponse(
            intent=intent,
            executive_summary=(
                "Churn predictions are available via the /predict/churn endpoint. "
                "Submit a customer record with features such as tenure, charges, "
                "and behaviour signals to receive a churn probability and risk label."
            ),
            key_findings=[
                "Prediction API: POST /predict/churn",
                "Batch scoring API: POST /predict/batch",
                "Model metrics: GET /predict/metrics",
                "Models evaluated: Logistic Regression, Random Forest, XGBoost",
            ],
            recommended_actions=[
                "Run model training: python -m app.services.model_training",
                "Call POST /predict/churn with a customer payload to get a live score.",
                "Use GET /predict/metrics to review model performance.",
            ],
            supporting_data=None,
            confidence_level=0.70,
            tools_used=["prediction_service (info only)"],
        )

    def _handle_data_profile(self, req: AgentChatRequest, intent: str) -> AgentChatResponse:
        profile = self._ds().profile()
        tools = ["dataset_service.profile"]
        high_null_cols = [
            c.name for c in profile.missing_values_report if c.null_pct > 10
        ]
        return AgentChatResponse(
            intent=intent,
            executive_summary=(
                f"The dataset contains {profile.total_rows:,} rows × {profile.total_columns} columns "
                f"with {profile.duplicate_rows} duplicate rows. "
                f"{len(profile.missing_values_report)} columns have missing values."
            ),
            key_findings=[
                f"Total rows: {profile.total_rows:,}",
                f"Total columns: {profile.total_columns}",
                f"Duplicate rows: {profile.duplicate_rows}",
                f"Columns with nulls: {len(profile.missing_values_report)}",
            ] + ([f"High-null columns (>10%): {', '.join(high_null_cols)}"] if high_null_cols else []),
            recommended_actions=[
                "Impute or drop columns with >30% missing values before modelling.",
                "Investigate and remove duplicate rows to avoid training bias.",
                "Review high-null columns for data pipeline issues.",
            ],
            supporting_data={
                "shape": {"rows": profile.total_rows, "columns": profile.total_columns},
                "duplicates": profile.duplicate_rows,
                "high_null_columns": high_null_cols,
            },
            confidence_level=0.92,
            tools_used=tools,
        )

    def _handle_unknown(self, req: AgentChatRequest, intent: str) -> AgentChatResponse:
        return AgentChatResponse(
            intent="unknown",
            executive_summary=(
                "I'm not sure how to interpret that query. "
                "Try asking about churn rate, high-risk customers, revenue at risk, "
                "regional analysis, retention strategies, or data quality."
            ),
            key_findings=["Intent not recognised."],
            recommended_actions=[
                "Try: 'What is the churn rate?'",
                "Try: 'Show top high-risk customers in the South region.'",
                "Try: 'Recommend a retention strategy for premium customers.'",
                "Try: 'Which region has the highest revenue at risk?'",
            ],
            supporting_data=None,
            confidence_level=0.0,
            tools_used=[],
        )
