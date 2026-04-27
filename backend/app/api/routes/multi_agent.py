"""
Multi-Agent chat route.

POST /agent/multi-chat  — keyword-routed multi-agent orchestrator.
"""
from fastapi import APIRouter, HTTPException

from app.agent_engine.multi_agent_orchestrator import (
    MultiAgentOrchestrator, MultiChatRequest, MultiChatResponse,
)

router = APIRouter()


@router.post(
    "/multi-chat",
    response_model=MultiChatResponse,
    summary="Multi-Agent Orchestrator — routes to specialist agent by intent",
)
async def multi_agent_chat(body: MultiChatRequest) -> MultiChatResponse:
    """
    Routes the query to one of four specialist agents based on keyword matching:

    - **DataAnalystAgent** — KPI, churn rate, revenue, segment breakdowns
    - **RetentionStrategistAgent** — retention offers, priority customers, campaigns
    - **ScenarioPlannerAgent** — what-if, budget, ROI, simulation (calls ScenarioService)
    - **ExecutiveBriefingAgent** — executive summary, leadership/CEO/board reports

    No external LLM or API key required — fully deterministic.
    """
    try:
        orch = MultiAgentOrchestrator()
        return orch.run(body)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=f"Dataset unavailable: {exc}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
