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
        description="Optional context dict (e.g. active filters) passed from the frontend",
    )


class AgentChatResponse(BaseModel):
    intent: str                          # classified intent label
    executive_summary: str               # one-paragraph prose answer
    key_findings: List[str]              # bullet-point findings
    recommended_actions: List[str]       # actionable next steps
    supporting_data: Optional[Dict[str, Any]] = None  # raw numbers / table snippet
    confidence_level: float = Field(..., ge=0.0, le=1.0)
    tools_used: List[str]                # which internal services were called
