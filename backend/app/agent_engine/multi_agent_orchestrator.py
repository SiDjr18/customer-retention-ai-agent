"""
Multi-Agent Orchestrator
POST /agent/multi-chat

4 deterministic agents routed by keyword matching — no external LLM required.

Agents:
  DataAnalystAgent       — KPI, churn rate, revenue, segment questions
  RetentionStrategistAgent — retention, offer, priority customer, campaign
  ScenarioPlannerAgent   — what-if, budget, ROI, simulation
  ExecutiveBriefingAgent — executive summary, leadership, CEO, report
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


# ─────────────────────────────────────────────────────────────────────────────
# Shared request / response schemas
# ─────────────────────────────────────────────────────────────────────────────

class MultiChatRequest(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = None   # optional caller-supplied filters


class RecommendedAction(BaseModel):
    priority: str    # "High" | "Medium" | "Low"
    action:   str
    rationale: str


class BusinessImpact(BaseModel):
    revenue_at_risk:     Optional[str] = None
    affected_customers:  Optional[int] = None
    risk_level:          str = "Moderate"


class MultiChatResponse(BaseModel):
    agent_used:        str
    executive_summary: str
    key_insights:      List[str]
    business_impact:   Optional[BusinessImpact] = None
    recommended_actions: List[RecommendedAction]
    confidence_level:  str


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _fmt_inr(v: float) -> str:
    """Format a value in INR: Cr / Lakh / plain ₹."""
    if v >= 10_000_000: return f"₹{v/10_000_000:.1f} Cr"
    if v >= 100_000:    return f"₹{v/100_000:.1f} Lakh"
    return f"₹{v:,.0f}"


def _risk_level(churn_pct: float) -> str:
    if churn_pct >= 25: return "Critical"
    if churn_pct >= 20: return "High"
    if churn_pct >= 15: return "Elevated"
    return "Moderate"


# ─────────────────────────────────────────────────────────────────────────────
# Agent 1 — Data Analyst
# ─────────────────────────────────────────────────────────────────────────────

class DataAnalystAgent:
    NAME = "DataAnalystAgent"

    def run(self, message: str, context: dict) -> MultiChatResponse:
        from app.services.dataset_service import DatasetService
        svc  = DatasetService()
        kpis = svc.kpis()
        enh  = svc.enhanced_kpis()
        biz  = enh.business_metrics
        rl   = _risk_level(kpis.churn_rate_pct)

        # Top churning segment
        top_seg = max(kpis.churn_by_segment.items(), key=lambda x: x[1], default=("N/A", 0))
        top_reg = max(kpis.churn_by_region.items(),  key=lambda x: x[1], default=("N/A", 0))

        return MultiChatResponse(
            agent_used=self.NAME,
            executive_summary=(
                f"Portfolio churn rate is {kpis.churn_rate_pct:.1f}% across "
                f"{kpis.total_customers:,} customers ({rl} risk). "
                f"Revenue at risk from churned accounts: {_fmt_inr(kpis.revenue_at_risk)}. "
                f"Top-quartile risk cohort represents an additional "
                f"{_fmt_inr(biz.revenue_at_risk)} in exposure."
            ),
            key_insights=[
                f"Churn rate: {kpis.churn_rate_pct:.1f}% — classified as {rl}",
                f"Total revenue at risk (churned CLV): {_fmt_inr(kpis.revenue_at_risk)}",
                f"Avg CLV: {_fmt_inr(kpis.avg_clv)} | Avg risk score: {kpis.avg_churn_risk_score:.2f}",
                f"Highest churn segment: {top_seg[0]} ({top_seg[1]*100:.1f}% churn rate)",
                f"Highest churn region: {top_reg[0]} ({top_reg[1]*100:.1f}% churn rate)",
            ],
            business_impact=BusinessImpact(
                revenue_at_risk=_fmt_inr(kpis.revenue_at_risk),
                affected_customers=int(kpis.total_customers * kpis.churn_rate_pct / 100),
                risk_level=rl,
            ),
            recommended_actions=[
                RecommendedAction(
                    priority="High",
                    action=f"Focus retention on {top_seg[0]} segment",
                    rationale=f"Highest churn rate at {top_seg[1]*100:.1f}%",
                ),
                RecommendedAction(
                    priority="High",
                    action=f"Deploy regional campaign in {top_reg[0]}",
                    rationale=f"Top churning region — {top_reg[1]*100:.1f}% churn",
                ),
                RecommendedAction(
                    priority="Medium",
                    action="Improve average satisfaction score",
                    rationale=f"Current avg satisfaction: {kpis.avg_satisfaction_score:.1f}/10",
                ),
            ],
            confidence_level="High",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Agent 2 — Retention Strategist
# ─────────────────────────────────────────────────────────────────────────────

class RetentionStrategistAgent:
    NAME = "RetentionStrategistAgent"

    def run(self, message: str, context: dict) -> MultiChatResponse:
        from app.services.recommendation_service import RecommendationService
        from app.services.dataset_service import DatasetService

        rs   = RecommendationService()
        pl   = rs.priority_list(top_n=10)
        svc  = DatasetService()
        kpis = svc.kpis()

        high = pl.high_priority_count
        med  = pl.medium_priority_count
        top3 = pl.customers[:3]

        actions = []
        for c in top3:
            actions.append(RecommendedAction(
                priority="High",
                action=f"{c.recommended_action} — {c.customer_id}",
                rationale=(
                    f"{c.customer_segment}/{c.plan_type} in {c.region}. "
                    f"CLV {_fmt_inr(c.estimated_clv)}, risk {c.churn_risk_score:.2f}"
                ),
            ))
        if not actions:
            actions = [RecommendedAction(
                priority="High",
                action="Immediate Retention Outreach",
                rationale="Deploy personalised retention offer to high-risk cohort",
            )]

        top_seg = max(kpis.churn_by_segment.items(), key=lambda x: x[1], default=("N/A", 0))
        rl = _risk_level(kpis.churn_rate_pct)

        return MultiChatResponse(
            agent_used=self.NAME,
            executive_summary=(
                f"{high} customers are High Priority for immediate retention outreach, "
                f"{med} are Medium Priority. "
                f"The top-CLV cohort spans {top_seg[0]} — the highest churn segment at "
                f"{top_seg[1]*100:.1f}%."
            ),
            key_insights=[
                f"{high} High Priority customers require immediate action",
                f"{med} Medium Priority customers benefit from proactive outreach",
                f"Priority score = 50% churn risk + 30% CLV + 20% complaint volume",
                f"Top at-risk segment: {top_seg[0]} ({top_seg[1]*100:.1f}% churn)",
                "Personalised offers outperform generic discounts by 2–3× in retention studies",
            ],
            business_impact=BusinessImpact(
                affected_customers=high + med,
                risk_level=rl,
            ),
            recommended_actions=actions,
            confidence_level="High",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Agent 3 — Scenario Planner
# ─────────────────────────────────────────────────────────────────────────────

class ScenarioPlannerAgent:
    NAME = "ScenarioPlannerAgent"

    # Extract numeric values from the query with simple regex
    @staticmethod
    def _extract(pattern: str, text: str, default: float) -> float:
        m = re.search(pattern, text, re.IGNORECASE)
        return float(m.group(1).replace(",", "")) if m else default

    def run(self, message: str, context: dict) -> MultiChatResponse:
        from app.decision_engine.scenario_service import ScenarioService, SimulationRequest

        budget    = self._extract(r'\$?([\d,]+(?:\.\d+)?)\s*(?:k|thousand)?.*?budget', message, 500_000)
        discount  = self._extract(r'(\d+(?:\.\d+)?)\s*%\s*(?:off|discount|offer)', message, 10.0)
        threshold = self._extract(r'risk\s*(?:threshold|score)?\s*[>=of]*\s*(0\.\d+)', message, 0.6)
        success   = self._extract(r'(\d+(?:\.\d+)?)\s*%\s*success', message, 18.0) / 100.0

        # Handle "500K" style budgets
        if re.search(r'[\d,]+k\b', message, re.IGNORECASE) and budget < 10_000:
            budget *= 1000

        sim_req = SimulationRequest(
            target_segment="All",
            risk_threshold=threshold,
            retention_budget=budget,
            offer_discount_pct=discount,
            expected_success_rate=success,
        )
        result = ScenarioService().simulate(sim_req)
        sim    = result.simulation
        base   = result.baseline
        rl     = _risk_level(
            base.total_at_risk_customers / max(1, 5000) * 100
        )

        return MultiChatResponse(
            agent_used=self.NAME,
            executive_summary=result.scenario_summary,
            key_insights=[
                f"{base.total_at_risk_customers:,} customers in at-risk cohort",
                f"Current revenue at risk: {_fmt_inr(base.current_revenue_at_risk)}",
                f"Budget covers {sim.customers_reachable:,} customers "
                f"(avg offer cost: {_fmt_inr(sim.avg_offer_cost)}/customer)",
                f"Expected retained: {sim.expected_customers_saved:,} customers "
                f"→ {_fmt_inr(sim.expected_revenue_saved)} recovered",
                f"Estimated ROI: {sim.estimated_roi:.1f}× ({sim.roi_label})",
            ],
            business_impact=BusinessImpact(
                revenue_at_risk=_fmt_inr(base.current_revenue_at_risk),
                affected_customers=base.total_at_risk_customers,
                risk_level=result.confidence_level,
            ),
            recommended_actions=[
                RecommendedAction(
                    priority="High" if sim.estimated_roi >= 2 else "Medium",
                    action="Execute retention campaign within budget",
                    rationale=result.recommendation,
                ),
                RecommendedAction(
                    priority="Medium",
                    action="Prioritise highest-CLV customers first",
                    rationale="Maximises revenue recovery per offer dollar spent",
                ),
                RecommendedAction(
                    priority="Low",
                    action="A/B test offer discount level",
                    rationale=f"Current {discount:.0f}% discount may be adjustable for better ROI",
                ),
            ],
            confidence_level=result.confidence_level,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Agent 4 — Executive Briefing
# ─────────────────────────────────────────────────────────────────────────────

class ExecutiveBriefingAgent:
    NAME = "ExecutiveBriefingAgent"

    def run(self, message: str, context: dict) -> MultiChatResponse:
        from app.services.dataset_service import DatasetService
        from app.services.recommendation_service import RecommendationService
        from app.decision_engine.insight_engine import InsightEngine

        svc  = DatasetService()
        kpis = svc.kpis()
        enh  = svc.enhanced_kpis()
        biz  = enh.business_metrics
        pl   = RecommendationService().priority_list(top_n=3)
        rl   = _risk_level(kpis.churn_rate_pct)

        try:
            insight = InsightEngine.from_kpis(kpis, svc.df)
            exec_summary = insight.executive_summary
        except Exception:
            exec_summary = (
                f"Churn is at {kpis.churn_rate_pct:.1f}% — classified as {rl}. "
                f"Revenue at risk: {_fmt_inr(kpis.revenue_at_risk)}. "
                f"Top-quartile risk cohort adds {_fmt_inr(biz.revenue_at_risk)} in exposure. "
                f"{pl.high_priority_count} customers require immediate outreach."
            )

        top_seg = max(kpis.churn_by_segment.items(), key=lambda x: x[1], default=("N/A", 0))
        top_reg = max(kpis.churn_by_region.items(),  key=lambda x: x[1], default=("N/A", 0))

        actions = []
        for c in pl.customers[:3]:
            actions.append(RecommendedAction(
                priority="High",
                action=c.recommended_action,
                rationale=(
                    f"Customer {c.customer_id} — {c.customer_segment} / {c.plan_type} "
                    f"in {c.region}. CLV {_fmt_inr(c.estimated_clv)}"
                ),
            ))

        return MultiChatResponse(
            agent_used=self.NAME,
            executive_summary=exec_summary,
            key_insights=[
                f"Churn rate: {kpis.churn_rate_pct:.1f}% ({rl} risk level)",
                f"Revenue at risk: {_fmt_inr(kpis.revenue_at_risk)} "
                f"| Top-quartile cohort: {_fmt_inr(biz.revenue_at_risk)}",
                f"High-value customers (top 25% CLV): {biz.high_value_customers:,} "
                f"({biz.high_value_pct:.1f}% of base)",
                f"Priority outreach queue: {pl.high_priority_count} High, "
                f"{pl.medium_priority_count} Medium, {pl.low_priority_count} Low",
                f"Churn concentrated in {top_seg[0]} segment and {top_reg[0]} region",
            ],
            business_impact=BusinessImpact(
                revenue_at_risk=_fmt_inr(kpis.revenue_at_risk),
                affected_customers=int(kpis.total_customers * kpis.churn_rate_pct / 100),
                risk_level=rl,
            ),
            recommended_actions=actions or [
                RecommendedAction(
                    priority="High",
                    action="Deploy immediate retention programme",
                    rationale=f"Churn at {kpis.churn_rate_pct:.1f}% — {rl} risk classification",
                )
            ],
            confidence_level="High",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Keyword Router
# ─────────────────────────────────────────────────────────────────────────────

_ROUTES = [
    # (pattern list,  agent class)
    (["kpi", "churn rate", "revenue at risk", "revenue", "segment",
      "region", "breakdown", "metric", "data", "analys"],
     DataAnalystAgent),

    (["retain", "offer", "campaign", "priority customer", "priority list",
      "outreach", "action", "discount offer", "who should", "next best"],
     RetentionStrategistAgent),

    (["simulat", "what if", "what-if", "budget", "roi", "return on",
      "scenario", "forecast", "spend", "discount"],
     ScenarioPlannerAgent),

    (["summary", "leadership", "ceo", "board", "executive", "brief",
      "report", "overview", "status"],
     ExecutiveBriefingAgent),
]

_DEFAULT_AGENT = DataAnalystAgent


def _route(message: str) -> type:
    msg_lower = message.lower()
    scores: dict[type, int] = {}
    for keywords, agent_cls in _ROUTES:
        score = sum(1 for kw in keywords if kw in msg_lower)
        if score:
            scores[agent_cls] = scores.get(agent_cls, 0) + score
    if not scores:
        return _DEFAULT_AGENT
    return max(scores, key=lambda c: scores[c])


# ─────────────────────────────────────────────────────────────────────────────
# Orchestrator entry point
# ─────────────────────────────────────────────────────────────────────────────

class MultiAgentOrchestrator:
    def run(self, req: MultiChatRequest) -> MultiChatResponse:
        agent_cls = _route(req.message)
        agent     = agent_cls()
        return agent.run(req.message, req.context or {})
