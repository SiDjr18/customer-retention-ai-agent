"""
Pydantic schemas for dataset endpoints.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Columns
# ---------------------------------------------------------------------------
class ColumnInfo(BaseModel):
    name: str
    dtype: str
    null_count: int
    null_pct: float
    unique_count: int


class ColumnsResponse(BaseModel):
    total_columns: int
    columns: List[ColumnInfo]


# ---------------------------------------------------------------------------
# Sample
# ---------------------------------------------------------------------------
class SampleResponse(BaseModel):
    total_rows: int
    returned_rows: int
    records: List[Dict[str, Any]]


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------
class DatasetProfileResponse(BaseModel):
    total_rows: int
    total_columns: int
    duplicate_rows: int
    missing_values_report: List[ColumnInfo]
    numeric_stats: Dict[str, Any]
    categorical_stats: Dict[str, Any]


# ---------------------------------------------------------------------------
# KPIs (original — kept for backward compat, used by agent_service)
# ---------------------------------------------------------------------------
class KPISummaryResponse(BaseModel):
    total_customers: int
    churn_rate_pct: float = Field(..., description="% of customers with churn_flag = 1")
    avg_clv: float = Field(..., description="Average Customer Lifetime Value (USD)")
    revenue_at_risk: float = Field(
        ..., description="Sum of CLV for customers predicted/flagged as churned"
    )
    avg_churn_risk_score: float
    avg_satisfaction_score: float
    churn_by_segment: Dict[str, float]
    churn_by_region: Dict[str, float]
    insight: Optional[Any] = Field(None, description="Consulting-grade executive insight")


# ---------------------------------------------------------------------------
# Enhanced KPIs — new nested structure
# ---------------------------------------------------------------------------
class CoreKPIs(BaseModel):
    total_customers: int
    churn_rate_pct: float = Field(..., description="% of customers with churn_flag = 1")
    avg_clv: float = Field(..., description="Average Customer Lifetime Value (USD)")
    revenue_at_risk: float = Field(..., description="Sum of CLV for churned customers")
    avg_churn_risk_score: float
    avg_satisfaction_score: float
    churn_by_segment: Dict[str, float]
    churn_by_region: Dict[str, float]


class ChurnConcentration(BaseModel):
    top_region: str
    customer_count: int
    pct_of_total_churned: float


class BusinessMetrics(BaseModel):
    revenue_at_risk: float = Field(
        ..., description="Sum of CLV where churn_risk_score > 0.6"
    )
    high_value_customers: int = Field(
        ..., description="Count of customers with CLV above 75th percentile"
    )
    high_value_pct: float = Field(
        ..., description="% of total customers that are high-value"
    )
    churn_concentration: ChurnConcentration


class RiskSegment(BaseModel):
    region: str
    customer_segment: str
    plan_type: str
    customer_count: int
    avg_churn_risk_score: float
    churn_rate: float
    total_clv: float
    revenue_at_risk: float


class EnhancedKPISummaryResponse(BaseModel):
    core_kpis: CoreKPIs
    business_metrics: BusinessMetrics
    risk_segments: List[RiskSegment]
    executive_note: str
    insight: Optional[Any] = Field(None, description="Consulting-grade executive insight")


# ---------------------------------------------------------------------------
# Filter
# ---------------------------------------------------------------------------
class FilterRequest(BaseModel):
    region: Optional[str] = None
    state: Optional[str] = None
    city_tier: Optional[str] = None
    customer_segment: Optional[str] = None
    acquisition_channel: Optional[str] = None
    plan_type: Optional[str] = None
    contract_type: Optional[str] = None
    limit: int = Field(default=100, ge=1, le=5000)


class FilterResponse(BaseModel):
    total_matches: int
    returned_rows: int
    filters_applied: Dict[str, str]
    records: List[Dict[str, Any]]
