"""
Prediction routes — churn scoring endpoints.

Endpoints:
  POST /predict/churn   — single customer churn prediction
  POST /predict/batch   — batch churn scoring from a list of customers
  GET  /model/metrics   — trained model evaluation metrics + feature importance
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

router = APIRouter()

# Module-level singleton
_service: PredictionService | None = None


def get_service() -> PredictionService:
    global _service
    if _service is None:
        try:
            _service = PredictionService()
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=f"Prediction service unavailable: {exc}",
            ) from exc
    return _service


# ---------------------------------------------------------------------------
# POST /predict/churn
# ---------------------------------------------------------------------------
@router.post(
    "/churn",
    response_model=ChurnPredictResponse,
    summary="Single customer churn prediction",
)
async def predict_churn(body: ChurnPredictRequest) -> ChurnPredictResponse:
    """
    Score a single customer record.
    Returns churn probability, binary prediction, and top risk factors.
    """
    try:
        return get_service().predict_single(body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# POST /predict/batch
# ---------------------------------------------------------------------------
@router.post(
    "/batch",
    response_model=BatchPredictResponse,
    summary="Batch churn scoring",
)
async def predict_batch(body: BatchPredictRequest) -> BatchPredictResponse:
    """
    Score a list of customer records in one call.
    Useful for bulk risk triage.
    """
    try:
        return get_service().predict_batch(body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# GET /model/metrics  (mounted at app level under /predict router)
# ---------------------------------------------------------------------------
@router.get(
    "/metrics",
    response_model=ModelMetricsResponse,
    summary="Model evaluation metrics & feature importance",
    tags=["Model"],
)
async def get_model_metrics() -> ModelMetricsResponse:
    """
    Return accuracy, precision, recall, F1, ROC-AUC, and
    top-N feature importance scores for the active churn model.
    """
    try:
        return get_service().get_metrics()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
