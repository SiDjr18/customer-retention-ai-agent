"""
Recommendation routes — Next Best Action engine.

Endpoints:
  POST /recommend/customer         — single customer NBA
  POST /recommend/batch            — batch NBA for a list of customers
  GET  /recommend/strategy-summary — aggregate strategy breakdown
"""

from fastapi import APIRouter, HTTPException

from app.schemas.recommendation_schema import (
    CustomerRecommendRequest,
    CustomerRecommendResponse,
    BatchRecommendRequest,
    BatchRecommendResponse,
    StrategySummaryResponse,
)
from app.services.recommendation_service import RecommendationService

router = APIRouter()

_service: RecommendationService | None = None


def get_service() -> RecommendationService:
    global _service
    if _service is None:
        _service = RecommendationService()
    return _service


@router.post(
    "/customer",
    response_model=CustomerRecommendResponse,
    summary="Next Best Action for a single customer",
)
async def recommend_customer(body: CustomerRecommendRequest) -> CustomerRecommendResponse:
    """
    Apply NBA rules to a single customer record and return
    the recommended action with reason, priority, and confidence.
    """
    try:
        return get_service().recommend_single(body)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/batch",
    response_model=BatchRecommendResponse,
    summary="Next Best Action for a batch of customers",
)
async def recommend_batch(body: BatchRecommendRequest) -> BatchRecommendResponse:
    """Bulk NBA scoring — processes all records and returns prioritised actions."""
    try:
        return get_service().recommend_batch(body)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/strategy-summary",
    response_model=StrategySummaryResponse,
    summary="Aggregate strategy distribution across all customers",
)
async def strategy_summary() -> StrategySummaryResponse:
    """
    Returns a breakdown of how customers are distributed across
    each NBA strategy (counts + % + total revenue protected).
    """
    try:
        return get_service().strategy_summary()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
