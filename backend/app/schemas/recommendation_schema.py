"""
Pydantic schemas for the Next Best Action recommendation engine.
"""

from __future__ import annotations

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Single recommendation
# ---------------------------------------------------------------------------
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
    recommendation: str          # e.g. "Premium Retention Offer"
    reason: str                  # human-readable explanation
    expected_revenue_protected: float
    priority: str                # "Critical" | "High" | "Medium" | "Low"
    confidence: float            # 0.0 – 1.0


# ---------------------------------------------------------------------------
# Batch recommendation
# ---------------------------------------------------------------------------
class BatchRecommendRequest(BaseModel):
    customers: List[CustomerRecommendRequest]


class BatchRecommendResponse(BaseModel):
    total_customers: int
    total_revenue_protected: float
    recommendations: List[CustomerRecommendResponse]


# ---------------------------------------------------------------------------
# Strategy summary
# ---------------------------------------------------------------------------
class StrategyBucket(BaseModel):
    strategy: str
    customer_count: int
    pct_of_total: float
    total_revenue_protected: float


class StrategySummaryResponse(BaseModel):
    total_customers_analysed: int
    strategies: List[StrategyBucket]
