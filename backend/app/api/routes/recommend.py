"""
Recommendation routes — Next Best Action engine.
"""

from collections import Counter
from fastapi import APIRouter, HTTPException, Query

from app.schemas.recommendation_schema import (
    CustomerRecommendRequest,
    CustomerRecommendResponse,
    BatchRecommendRequest,
    BatchRecommendResponse,
    PriorityListResponse,
    StrategySummaryResponse,
)
from app.services.recommendation_service import RecommendationService
from app.decision_engine.insight_engine import InsightEngine

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
    try:
        return get_service().recommend_single(body)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/batch",
    response_model=BatchRecommendResponse,
    summary="Batch NBA scoring + executive insight",
)
async def recommend_batch(body: BatchRecommendRequest) -> BatchRecommendResponse:
    """Bulk NBA scoring — returns prioritised actions plus executive insight overlay."""
    try:
        result = get_service().recommend_batch(body)
        try:
            strategy_counts = dict(Counter(r.recommendation for r in result.recommendations))
            result.insight = InsightEngine.from_batch_recommend(
                total_customers=result.total_customers,
                total_revenue_protected=result.total_revenue_protected,
                strategy_counts=strategy_counts,
            )
        except Exception:
            pass
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/strategy-summary",
    response_model=StrategySummaryResponse,
    summary="Aggregate strategy distribution",
)
async def strategy_summary() -> StrategySummaryResponse:
    try:
        return get_service().strategy_summary()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/priority-list",
    response_model=PriorityListResponse,
    summary="Customer prioritisation list — top 500 by composite score",
    tags=["Prioritisation"],
)
async def priority_list(
    top_n: int = Query(
        default=500,
        ge=1,
        le=5000,
        description="Maximum number of customers to return (default 500, max 5000)",
    ),
) -> PriorityListResponse:
    """
    Score every customer with the composite priority formula:

        priority_score = (churn_risk_score × 0.5)
                       + (normalized_clv × 0.3)
                       + (complaints_weight × 0.2)

    Where:
    - **normalized_clv** = estimated_clv min-max scaled to [0, 1]
    - **complaints_weight** = complaints_90d min-max scaled to [0, 1]
    - Missing values are filled with 0 before scaling

    Priority classes:
    - **High Priority** — score ≥ 0.70
    - **Medium Priority** — score ≥ 0.40 and < 0.70
    - **Low Priority** — score < 0.40

    Returns the top `top_n` customers sorted by priority_score descending.
    Each record includes all input signals, the composite score,
    the priority class, a recommended action, and a rationale.
    """
    try:
        return get_service().priority_list(top_n=top_n)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Dataset not available — cannot compute priority list: {exc}",
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
