"""
Pydantic schemas for the AI Agent chat endpoint.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AgentChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Natural-language user query")
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional context dict passed from the frontend",
    )


# ---------------------------------------------------------------------------
# Consulting-grade response building blocks
# ---------------------------------------------------------------------------

class RecommendedAction(BaseModel):
    priority: str = Field(..., description="High | Medium | Low")
    action: str = Field(..., description="Specific action to take")
    rationale: str = Field(..., description="Why this action is recommended")


class BusinessImpact(BaseModel):
    revenue_at_risk: Optional[str] = Field(
        None, description="Formatted revenue figure at risk (e.g. '$1,250,000')"
    )
    affected_customers: Optional[int] = Field(
        None, description="Count of customers directly impacted"
    )
    risk_level: str = Field(
        ..., description="Critical | High | Elevated | Moderate"
    )


# ---------------------------------------------------------------------------
# Top-level response
# ---------------------------------------------------------------------------

class AgentChatResponse(BaseModel):
    intent: str
    executive_summary: str = Field(
        ..., description="2–3 line business-readable summary"
    )
    key_insights: List[str] = Field(
        ..., description="3–5 bullet-style insights drawn from data"
    )
    business_impact: Optional[BusinessImpact] = Field(
        None, description="Revenue, customer count, and risk level"
    )
    recommended_actions: List[RecommendedAction] = Field(
        ..., description="Prioritised actions with rationale"
    )
    confidence_level: str = Field(
        ..., description="High | Medium | Low"
    )
    tools_used: List[str]
    supporting_data: Optional[Dict[str, Any]] = None
    insight: Optional[Any] = Field(
        None, description="Structured InsightResponse from decision engine"
    )
