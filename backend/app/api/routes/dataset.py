"""
Dataset routes — data engine for 01_Customer_Retention.csv.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from app.schemas.dataset import (
    DatasetProfileResponse,
    EnhancedKPISummaryResponse,
    ColumnsResponse,
    SampleResponse,
    FilterRequest,
    FilterResponse,
)
from app.services.dataset_service import DatasetService
from app.decision_engine.insight_engine import InsightEngine

router = APIRouter()

_service: Optional[DatasetService] = None


def get_service() -> DatasetService:
    global _service
    if _service is None:
        try:
            _service = DatasetService()
        except FileNotFoundError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    return _service


@router.get("/columns", response_model=ColumnsResponse, summary="List all columns")
async def get_columns() -> ColumnsResponse:
    return get_service().columns()


@router.get("/sample", response_model=SampleResponse, summary="Preview dataset rows")
async def get_sample(
    n: int = Query(default=10, ge=1, le=500, description="Number of rows to return"),
) -> SampleResponse:
    return get_service().sample(n)


@router.get("/profile", response_model=DatasetProfileResponse, summary="Full dataset profile")
async def get_profile() -> DatasetProfileResponse:
    return get_service().profile()


@router.get(
    "/kpis",
    response_model=EnhancedKPISummaryResponse,
    summary="Business KPI summary + executive insight",
)
async def get_kpis() -> EnhancedKPISummaryResponse:
    """
    Return high-level business KPIs augmented with consulting-grade executive insight:
    - core_kpis: total customers, churn rate (%), avg CLV, revenue at risk, breakdowns
    - business_metrics: revenue_at_risk (risk>0.6), high_value_customers (CLV>75th pct),
                        churn_concentration (top region)
    - risk_segments: top 20 groupby(region × customer_segment × plan_type) ranked by revenue at risk
    - executive_note: narrative summary
    - insight: executive_summary, key_drivers, business_impact, recommended_actions,
               expected_outcome, confidence_level
    """
    svc = get_service()
    result = svc.enhanced_kpis()
    try:
        result.insight = InsightEngine.from_kpis(svc.kpis(), svc.df)
    except Exception:
        pass  # insight is optional — never break the core response
    return result


@router.post("/filter", response_model=FilterResponse, summary="Filter dataset by dimension values")
async def filter_dataset(body: FilterRequest) -> FilterResponse:
    return get_service().filter_data(body)
