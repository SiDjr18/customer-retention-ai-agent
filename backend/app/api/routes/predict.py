"""
Prediction routes — churn scoring endpoints.
"""

from fastapi import APIRouter, HTTPException

from app.schemas.prediction_schema import (
    ChurnPredictRequest,
    ChurnPredictResponse,
    BatchPredictRequest,
    BatchPredictResponse,
    ModelMetricsResponse,
)
from app.services.prediction_service import PredictionService
from app.decision_engine.insight_engine import InsightEngine

router = APIRouter()

_service: PredictionService | None = None


def get_service() -> PredictionService:
    global _service
    if _service is None:
        try:
            _service = PredictionService()
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Prediction service unavailable: {exc}") from exc
    return _service


@router.post("/churn", response_model=ChurnPredictResponse, summary="Single customer churn prediction + insight")
async def predict_churn(body: ChurnPredictRequest) -> ChurnPredictResponse:
    """
    Score a single customer record.
    Returns churn probability, binary prediction, top risk factors,
    and an executive insight overlay from the decision engine.
    """
    try:
        result = get_service().predict_single(body)
        try:
            risk_factor_labels = [rf.feature for rf in result.top_risk_factors]
            result.insight = InsightEngine.from_churn_prediction(
                churn_prob=result.churn_probability,
                customer_id=result.customer_id,
                risk_factors=risk_factor_labels,
                clv=getattr(body, "estimated_clv", None),
            )
        except Exception:
            pass
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/batch", response_model=BatchPredictResponse, summary="Batch churn scoring + insight")
async def predict_batch(body: BatchPredictRequest) -> BatchPredictResponse:
    """
    Score a list of customer records in one call.
    Returns batch risk triage plus an executive insight overlay.
    """
    try:
        result = get_service().predict_batch(body)
        try:
            preds_dicts = [{"churn_probability": p.churn_probability} for p in result.predictions]
            total_clv = sum(
                float(c.estimated_clv or 0)
                for c, p in zip(body.customers, result.predictions)
                if p.churn_probability >= 0.65
            )
            result.insight = InsightEngine.from_batch_predict(
                results=preds_dicts,
                total_clv_at_risk=total_clv,
            )
        except Exception:
            pass
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/metrics", response_model=ModelMetricsResponse, summary="Model evaluation metrics & feature importance", tags=["Model"])
async def get_model_metrics() -> ModelMetricsResponse:
    try:
        return get_service().get_metrics()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
