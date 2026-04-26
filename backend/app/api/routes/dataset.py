"""
Dataset routes — data engine for 01_Customer_Retention.csv.

Endpoints:
  GET  /dataset/profile   — full profiling report (dtypes, nulls, duplicates, stats)
  GET  /dataset/kpis      — business KPI summary
  GET  /dataset/columns   — column names + dtypes
  GET  /dataset/sample    — first N rows as JSON
  POST /dataset/filter    — filtered subset with optional aggregations
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from app.schemas.dataset import (
    DatasetProfileResponse,
    KPISummaryResponse,
    ColumnsResponse,
    SampleResponse,
    FilterRequest,
    FilterResponse,
)
from app.services.dataset_service import DatasetService

router = APIRouter()

# Module-level singleton — loaded once on first request, cached afterwards.
_service: Optional[DatasetService] = None


def get_service() -> DatasetService:
    """Return the cached DatasetService, initialising it on first call."""
    global _service
    if _service is None:
        try:
            _service = DatasetService()
        except FileNotFoundError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    return _service


# ---------------------------------------------------------------------------
# GET /dataset/columns
# ---------------------------------------------------------------------------
@router.get("/columns", response_model=ColumnsResponse, summary="List all columns")
async def get_columns() -> ColumnsResponse:
    """Return every column name and its pandas dtype."""
    return get_service().columns()


# ---------------------------------------------------------------------------
# GET /dataset/sample
# ---------------------------------------------------------------------------
@router.get("/sample", response_model=SampleResponse, summary="Preview dataset rows")
async def get_sample(
    n: int = Query(default=10, ge=1, le=500, description="Number of rows to return"),
) -> SampleResponse:
    """Return the first *n* rows of the dataset as JSON records."""
    return get_service().sample(n)


# ---------------------------------------------------------------------------
# GET /dataset/profile
# ---------------------------------------------------------------------------
@router.get(
    "/profile",
    response_model=DatasetProfileResponse,
    summary="Full dataset profile",
)
async def get_profile() -> DatasetProfileResponse:
    """
    Return a comprehensive profiling report including:
    - Shape (rows × columns)
    - Per-column dtype, null count, null %, unique count
    - Duplicate row count
    - Descriptive statistics for numeric columns
    """
    return get_service().profile()


# ---------------------------------------------------------------------------
# GET /dataset/kpis
# ---------------------------------------------------------------------------
@router.get(
    "/kpis",
    response_model=KPISummaryResponse,
    summary="Business KPI summary",
)
async def get_kpis() -> KPISummaryResponse:
    """
    Return high-level business KPIs:
    - Total customers
    - Churn rate (%)
    - Average Customer Lifetime Value (CLV)
    - Revenue at risk (sum of CLV for churned / high-risk customers)
    - Average churn risk score
    - Average satisfaction score
    """
    return get_service().kpis()


# ---------------------------------------------------------------------------
# POST /dataset/filter
# ---------------------------------------------------------------------------
@router.post(
    "/filter",
    response_model=FilterResponse,
    summary="Filter dataset by dimension values",
)
async def filter_dataset(body: FilterRequest) -> FilterResponse:
    """
    Apply one or more dimension filters and return matching records.

    Filterable dimensions:
      region, state, city_tier, customer_segment,
      acquisition_channel, plan_type, contract_type

    All filters are combined with AND logic.
    Omit a field (or set it to null) to skip that filter.
    """
    return get_service().filter_data(body)
