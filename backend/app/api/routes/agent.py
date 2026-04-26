"""
AI Agent chat route.

POST /agent/chat  — deterministic intent-routing assistant.

The agent classifies the user's natural-language message, routes it to the
correct internal service (KPIs, filter, prediction, recommendations, summary),
and returns a structured JSON response — no paid API key required.
"""

from fastapi import APIRouter, HTTPException

from app.schemas.agent_schema import AgentChatRequest, AgentChatResponse
from app.services.agent_service import AgentService

router = APIRouter()

_service: AgentService | None = None


def get_service() -> AgentService:
    global _service
    if _service is None:
        _service = AgentService()
    return _service


@router.post(
    "/chat",
    response_model=AgentChatResponse,
    summary="AI Agent — natural language query",
)
async def agent_chat(body: AgentChatRequest) -> AgentChatResponse:
    """
    Send a natural-language question about customer retention.

    The agent will:
    1. Classify intent (churn_query, risk_query, recommendation_query, etc.)
    2. Route to the relevant backend service
    3. Return a structured executive response

    Example messages:
    - "What is the churn rate?"
    - "Show top high-risk customers in the South region."
    - "Which segment has the highest revenue at risk?"
    - "Recommend a retention strategy for premium customers."
    """
    try:
        return get_service().handle(body)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
