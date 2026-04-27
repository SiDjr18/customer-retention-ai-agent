"""
Pydantic schemas for the Next Best Action recommendation engine.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CustomerRecommendRequest(BaseModel):
    customer_id: Optional[str] = None
    churn_risk_score: float = Field(..., ge=0.0, le=1.0)
    estimated_clv: float = Field(..., ge=0.0)
    upsell_probability: float = Field(..., ge=0.0, le=1.0)
    retention_offer_cost: float = Field(..., ge=0.0)
    complaints_90d: int = Field(..., ge=0)
    payment_failures_12m: int = Field(..., ge=0)
    satisfaction_score: float = Field(..., ge=0.0, le=10.0)
    contract_type: Optional[str] = None
    plan_type: Optional[str] = None


class CustomerRecommendResponse(BaseModel):
    customer_id: Optional[str]
    recommendation: str
    reason: str
    expected_revenue_protected: float
    priority: str   # "Critical" | "High" | "Medium" | "Low"
    confidence: float


class BatchRecommendRequest(BaseModel):
    customers: List[CustomerRecommendRequest]


class BatchRecommendResponse(BaseModel):
    total_customers: int
    total_revenue_protected: float
    recommendations: List[CustomerRecommendResponse]
    insight: Optional[Any] = Field(None, description="Consulting-grade executive insight")


class StrategyBucket(BaseModel):
    strategy: str
    customer_count: int
    pct_of_total: float
    total_revenue_protected: float


class StrategySummaryResponse(BaseModel):
    total_customers_analysed: int
    strategies: List[StrategyBucket]


# ---------------------------------------------------------------------------
# Customer prioritisation — GET /recommend/priority-list
# ---------------------------------------------------------------------------

class PriorityCustomer(BaseModel):
    customer_id: str = Field(..., description="Unique customer identifier")
    region: str
    customer_segment: str
    plan_type: str
    estimated_clv: float = Field(..., description="Estimated Customer Lifetime Value (USD)")
    churn_risk_score: float = Field(..., ge=0.0, le=1.0)
    complaints_90d: int = Field(..., ge=0, description="Complaints in last 90 days")
    priority_score: float = Field(
        ..., ge=0.0, le=1.0,
        description="Composite score: 0.5×churn_risk + 0.3×norm_clv + 0.2×norm_complaints"
    )
    priority_class: str = Field(
        ..., description="High Priority | Medium Priority | Low Priority"
    )
    recommended_action: str
    rationale: str


class PriorityListResponse(BaseModel):
    total_returned: int
    high_priority_count: int
    medium_priority_count: int
    low_priority_count: int
    customers: List[PriorityCustomer]
