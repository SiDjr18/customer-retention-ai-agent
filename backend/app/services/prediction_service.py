"""
PredictionService — loads the trained model artefacts and serves predictions.

Artefacts expected at backend/artifacts/:
  churn_model.pkl         (sklearn Pipeline with preprocessor + classifier)
  model_metrics.json      (eval results written by model_training.py)

If artefacts are missing, call model_training.train() first or run:
  cd backend && python -m app.services.model_training
"""

from __future__ import annotations

import json
import os
import pickle
from typing import List, Optional

import numpy as np
import pandas as pd

from app.services.model_training import IMPORTANCE_PATH, METRICS_PATH, MODEL_PATH
from app.schemas.prediction_schema import (
    BatchPredictRequest,
    BatchPredictResponse,
    ChurnPredictRequest,
    ChurnPredictResponse,
    FeatureImportance,
    ModelMetric,
    ModelMetricsResponse,
    RiskFactor,
)


def _risk_label(prob: float) -> str:
    if prob >= 0.65:
        return "High"
    if prob >= 0.35:
        return "Medium"
    return "Low"


class PredictionService:
    """Serves churn predictions from a persisted sklearn Pipeline."""

    def __init__(self) -> None:
        self._model = self._load_model()
        self._metrics_data = self._load_metrics()

    # ------------------------------------------------------------------
    # Artefact loaders
    # ------------------------------------------------------------------

    def _load_model(self):
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(
                f"Model artefact not found at '{MODEL_PATH}'. "
                "Run: python -m app.services.model_training"
            )
        with open(MODEL_PATH, "rb") as f:
            return pickle.load(f)

    def _load_metrics(self) -> dict:
        if not os.path.exists(METRICS_PATH):
            return {}
        with open(METRICS_PATH) as f:
            return json.load(f)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _request_to_df(self, req: ChurnPredictRequest) -> pd.DataFrame:
        """Convert a single request to a one-row DataFrame."""
        data = req.model_dump(exclude={"customer_id"}, exclude_none=False)
        return pd.DataFrame([data])

    def _make_risk_factors(self, row_df: pd.DataFrame) -> List[RiskFactor]:
        """
        Return top feature importances as RiskFactor objects.
        Uses global importance ranking stored in metrics JSON.
        """
        importance_list = self._metrics_data.get("feature_importance", [])[:5]
        factors: List[RiskFactor] = []
        for item in importance_list:
            feature = item["feature"]
            # Check if this feature is present in the row
            val = row_df.get(feature, [None])[0] if feature in row_df.columns else None
            direction = "increases_risk"  # simplified for rule-based interpretation
            factors.append(
                RiskFactor(
                    feature=feature,
                    importance=round(float(item["importance"]), 4),
                    direction=direction,
                )
            )
        return factors

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def predict_single(self, req: ChurnPredictRequest) -> ChurnPredictResponse:
        """Score one customer record."""
        row_df = self._request_to_df(req)

        try:
            prob = float(self._model.predict_proba(row_df)[0, 1])
        except Exception:
            # Fallback: use decision function or raw predict
            raw = self._model.predict(row_df)[0]
            prob = float(raw)

        prediction = prob >= 0.5
        best_model_name = self._metrics_data.get("best_model", "Unknown")

        return ChurnPredictResponse(
            customer_id=req.customer_id,
            churn_probability=round(prob, 4),
            churn_prediction=prediction,
            risk_label=_risk_label(prob),
            top_risk_factors=self._make_risk_factors(row_df),
            model_used=best_model_name,
        )

    def predict_batch(self, req: BatchPredictRequest) -> BatchPredictResponse:
        """Score a list of customer records."""
        predictions = [self.predict_single(c) for c in req.customers]

        high = sum(1 for p in predictions if p.risk_label == "High")
        med = sum(1 for p in predictions if p.risk_label == "Medium")
        low = sum(1 for p in predictions if p.risk_label == "Low")

        return BatchPredictResponse(
            total_scored=len(predictions),
            high_risk_count=high,
            medium_risk_count=med,
            low_risk_count=low,
            predictions=predictions,
        )

    def get_metrics(self) -> ModelMetricsResponse:
        """Return model evaluation metrics and feature importance."""
        if not self._metrics_data:
            raise FileNotFoundError(
                "Model metrics not found. Run model training first."
            )
        raw_metrics = self._metrics_data.get("metrics", [])
        metrics = [
            ModelMetric(
                model_name=m["model_name"],
                accuracy=m["accuracy"],
                precision=m["precision"],
                recall=m["recall"],
                f1_score=m["f1_score"],
                roc_auc=m["roc_auc"],
            )
            for m in raw_metrics
        ]

        raw_importance = self._metrics_data.get("feature_importance", [])
        importance = [
            FeatureImportance(feature=i["feature"], importance=i["importance"])
            for i in raw_importance
        ]

        return ModelMetricsResponse(
            best_model=self._metrics_data.get("best_model", "Unknown"),
            metrics=metrics,
            feature_importance=importance,
            trained_at=self._metrics_data.get("trained_at"),
            training_samples=self._metrics_data.get("training_samples"),
        )
