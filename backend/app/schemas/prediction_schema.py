"""
Pydantic schemas for churn prediction endpoints.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Single prediction
# ---------------------------------------------------------------------------
class ChurnPredictRequest(BaseModel):
    customer_id: Optional[str] = None
    region: Optional[str] = None
    state: Optional[str] = None
    city_tier: Optional[str] = None
    customer_segment: Optional[str] = None
    plan_type: Optional[str] = None
    contract_type: Optional[str] = None
    acquisition_channel: Optional[str] = None
    tenure_months: Optional[float] = None
    monthly_charges: Optional[float] = None
    total_charges: Optional[float] = None
    estimated_clv: Optional[float] = None
    churn_risk_score: Optional[float] = None
    upsell_probability: Optional[float] = None
    satisfaction_score: Optional[float] = None
    complaints_90d: Optional[int] = None
    payment_failures_12m: Optional[int] = None
    support_tickets_12m: Optional[int] = None
    retention_offer_cost: Optional[float] = None
    model_config = {"extra": "allow"}


class RiskFactor(BaseModel):
    feature: str
    importance: float
    direction: str  # "increases_risk" | "decreases_risk"


class ChurnPredictResponse(BaseModel):
    customer_id: Optional[str]
    churn_probability: float = Field(..., ge=0.0, le=1.0)
    churn_prediction: bool
    risk_label: str  # "High" | "Medium" | "Low"
    top_risk_factors: List[RiskFactor]
    model_used: str
    insight: Optional[Any] = Field(None, description="Consulting-grade executive insight")


# ---------------------------------------------------------------------------
# Batch prediction
# ---------------------------------------------------------------------------
class BatchPredictRequest(BaseModel):
    customers: List[ChurnPredictRequest]


class BatchPredictResponse(BaseModel):
    total_scored: int
    high_risk_count: int
    medium_risk_count: int
    low_risk_count: int
    predictions: List[ChurnPredictResponse]
    insight: Optional[Any] = Field(None, description="Consulting-grade executive insight")


# ---------------------------------------------------------------------------
# Model metrics
# ---------------------------------------------------------------------------
class ModelMetric(BaseModel):
    model_name: str
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    roc_auc: float


class FeatureImportance(BaseModel):
    feature: str
    importance: float


class ModelMetricsResponse(BaseModel):
    best_model: str
    metrics: List[ModelMetric]
    feature_importance: List[FeatureImportance]
    trained_at: Optional[str] = None
    training_samples: Optional[int] = None
