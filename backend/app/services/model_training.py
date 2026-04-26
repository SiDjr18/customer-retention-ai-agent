"""
model_training.py — ML engine for churn prediction.

Pipeline:
  1. Load 01_Customer_Retention.csv via DatasetService
  2. Preprocess: impute → encode → scale
  3. Train:
       a. Logistic Regression (baseline)
       b. Random Forest
       c. XGBoost (graceful skip if not installed)
  4. Evaluate: accuracy, precision, recall, F1, ROC-AUC
  5. Select best model (highest ROC-AUC)
  6. Save artefacts:
       backend/artifacts/churn_model.pkl       (best estimator)
       backend/artifacts/preprocessor.pkl      (sklearn Pipeline)
       backend/artifacts/model_metrics.json    (eval results)
       backend/artifacts/feature_importance.json

Run manually:
  cd backend
  python -m app.services.model_training
"""

from __future__ import annotations

import json
import logging
import os
import pickle
import warnings
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder

from app.config import settings

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "artifacts")
MODEL_PATH = os.path.join(ARTIFACTS_DIR, "churn_model.pkl")
PREPROCESSOR_PATH = os.path.join(ARTIFACTS_DIR, "preprocessor.pkl")
METRICS_PATH = os.path.join(ARTIFACTS_DIR, "model_metrics.json")
IMPORTANCE_PATH = os.path.join(ARTIFACTS_DIR, "feature_importance.json")

# ---------------------------------------------------------------------------
# Column aliases — mirrors dataset_service.py
# ---------------------------------------------------------------------------
_CHURN_ALIASES = ["churn_flag", "churned", "churn", "is_churn"]
_DROP_COLS = ["customer_id", "customerid", "id"]  # identifiers, not features

# Preferred categorical features (present in most retention datasets)
PREFERRED_CAT_FEATURES = [
    "region", "state", "city_tier", "customer_segment",
    "acquisition_channel", "plan_type", "contract_type",
    "payment_method", "gender",
]

# Preferred numeric features
PREFERRED_NUM_FEATURES = [
    "tenure_months", "monthly_charges", "total_charges", "estimated_clv",
    "churn_risk_score", "upsell_probability", "satisfaction_score",
    "complaints_90d", "payment_failures_12m", "support_tickets_12m",
    "retention_offer_cost", "age", "num_products",
]


def _find_col(df: pd.DataFrame, aliases: List[str]) -> Optional[str]:
    lower_map = {c.lower(): c for c in df.columns}
    for alias in aliases:
        if alias.lower() in lower_map:
            return lower_map[alias.lower()]
    return None


# ---------------------------------------------------------------------------
# Data loading & feature selection
# ---------------------------------------------------------------------------

def load_and_split(
    test_size: float = 0.2,
    random_state: int = 42,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series, List[str], List[str]]:
    """
    Load CSV, detect target, select features, split into train/test.

    Returns
    -------
    X_train, X_test, y_train, y_test, num_features, cat_features
    """
    csv_path = os.path.join(settings.DATA_DIR, settings.DATASET_FILENAME)
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Dataset not found at {csv_path}")

    df = pd.read_csv(csv_path, low_memory=False)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # Detect target column
    churn_col = _find_col(df, _CHURN_ALIASES)
    if churn_col is None:
        raise ValueError(
            "Cannot find a churn target column. "
            f"Expected one of: {_CHURN_ALIASES}"
        )

    y = df[churn_col].astype(int)

    # Drop target and identifiers
    drop = [churn_col] + [c for c in _DROP_COLS if c in df.columns]
    X = df.drop(columns=drop)

    # Select numeric features
    num_features = [
        c for c in PREFERRED_NUM_FEATURES if c in X.columns
    ]
    # Fall back: use all numeric columns not already chosen
    all_num = X.select_dtypes(include="number").columns.tolist()
    for c in all_num:
        if c not in num_features:
            num_features.append(c)

    # Select categorical features
    cat_features = [
        c for c in PREFERRED_CAT_FEATURES if c in X.columns
    ]
    all_cat = X.select_dtypes(include=["object", "category"]).columns.tolist()
    for c in all_cat:
        if c not in cat_features and X[c].nunique() <= 30:
            cat_features.append(c)

    X = X[num_features + cat_features]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )
    return X_train, X_test, y_train, y_test, num_features, cat_features


# ---------------------------------------------------------------------------
# Preprocessing pipeline
# ---------------------------------------------------------------------------

def build_preprocessor(
    num_features: List[str], cat_features: List[str]
) -> ColumnTransformer:
    """Return a ColumnTransformer that imputes and encodes features."""
    numeric_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])
    categorical_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ])
    return ColumnTransformer(
        transformers=[
            ("num", numeric_pipeline, num_features),
            ("cat", categorical_pipeline, cat_features),
        ],
        remainder="drop",
    )


# ---------------------------------------------------------------------------
# Model evaluation helper
# ---------------------------------------------------------------------------

def _evaluate(
    name: str,
    model: Any,
    X_test: pd.DataFrame,
    y_test: pd.Series,
) -> Dict[str, Any]:
    y_pred = model.predict(X_test)
    y_prob = (
        model.predict_proba(X_test)[:, 1]
        if hasattr(model, "predict_proba")
        else y_pred.astype(float)
    )
    return {
        "model_name": name,
        "accuracy": round(accuracy_score(y_test, y_pred), 4),
        "precision": round(precision_score(y_test, y_pred, zero_division=0), 4),
        "recall": round(recall_score(y_test, y_pred, zero_division=0), 4),
        "f1_score": round(f1_score(y_test, y_pred, zero_division=0), 4),
        "roc_auc": round(roc_auc_score(y_test, y_prob), 4),
    }


# ---------------------------------------------------------------------------
# Feature importance extraction
# ---------------------------------------------------------------------------

def _extract_importance(
    best_model: Any,
    preprocessor: ColumnTransformer,
    num_features: List[str],
    cat_features: List[str],
) -> List[Dict[str, Any]]:
    """Extract feature importance from the best model's final estimator."""
    # Reconstruct feature names after OHE
    try:
        cat_enc = preprocessor.named_transformers_["cat"]["encoder"]
        cat_names = list(cat_enc.get_feature_names_out(cat_features))
    except Exception:
        cat_names = cat_features

    feature_names = num_features + cat_names

    # Get importances
    estimator = best_model.named_steps.get("clf") or best_model
    importances: Optional[np.ndarray] = None

    if hasattr(estimator, "feature_importances_"):
        importances = estimator.feature_importances_
    elif hasattr(estimator, "coef_"):
        importances = np.abs(estimator.coef_[0])

    if importances is None or len(importances) != len(feature_names):
        return []

    pairs = sorted(
        zip(feature_names, importances), key=lambda x: x[1], reverse=True
    )
    return [
        {"feature": f, "importance": round(float(imp), 6)}
        for f, imp in pairs[:30]  # top 30
    ]


# ---------------------------------------------------------------------------
# Train function
# ---------------------------------------------------------------------------

def train() -> Dict[str, Any]:
    """
    Full training run.  Returns a summary dict with metrics and artefact paths.
    """
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)
    logger.info("Loading dataset …")

    X_train, X_test, y_train, y_test, num_features, cat_features = load_and_split()
    logger.info(
        "Train: %d rows | Test: %d rows | Features: %d num / %d cat",
        len(X_train), len(X_test), len(num_features), len(cat_features),
    )

    preprocessor = build_preprocessor(num_features, cat_features)

    # -------------------------------------------------------------------
    # Candidate models
    # -------------------------------------------------------------------
    candidates: List[Tuple[str, Any]] = [
        (
            "Logistic Regression",
            Pipeline([
                ("pre", preprocessor),
                ("clf", LogisticRegression(max_iter=500, random_state=42, class_weight="balanced")),
            ]),
        ),
        (
            "Random Forest",
            Pipeline([
                ("pre", preprocessor),
                ("clf", RandomForestClassifier(n_estimators=200, random_state=42, class_weight="balanced", n_jobs=-1)),
            ]),
        ),
    ]

    # XGBoost — graceful skip
    try:
        from xgboost import XGBClassifier  # type: ignore
        candidates.append((
            "XGBoost",
            Pipeline([
                ("pre", preprocessor),
                ("clf", XGBClassifier(
                    n_estimators=200, random_state=42,
                    eval_metric="logloss", use_label_encoder=False,
                    scale_pos_weight=(y_train == 0).sum() / max((y_train == 1).sum(), 1),
                )),
            ]),
        ))
        logger.info("XGBoost available — added to candidates.")
    except ImportError:
        logger.warning("XGBoost not installed — skipping. Install with: pip install xgboost")

    # -------------------------------------------------------------------
    # Fit & evaluate
    # -------------------------------------------------------------------
    all_metrics: List[Dict[str, Any]] = []
    trained_models: Dict[str, Any] = {}

    for name, pipeline in candidates:
        logger.info("Training %s …", name)
        pipeline.fit(X_train, y_train)
        metrics = _evaluate(name, pipeline, X_test, y_test)
        all_metrics.append(metrics)
        trained_models[name] = pipeline
        logger.info("  → ROC-AUC: %.4f | F1: %.4f", metrics["roc_auc"], metrics["f1_score"])

    # -------------------------------------------------------------------
    # Select best model (highest ROC-AUC)
    # -------------------------------------------------------------------
    best_metrics = max(all_metrics, key=lambda m: m["roc_auc"])
    best_name = best_metrics["model_name"]
    best_model = trained_models[best_name]
    logger.info("Best model: %s (ROC-AUC %.4f)", best_name, best_metrics["roc_auc"])

    # -------------------------------------------------------------------
    # Feature importance
    # -------------------------------------------------------------------
    importance = _extract_importance(
        best_model, best_model.named_steps["pre"], num_features, cat_features
    )

    # -------------------------------------------------------------------
    # Persist artefacts
    # -------------------------------------------------------------------
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(best_model, f)

    with open(PREPROCESSOR_PATH, "wb") as f:
        pickle.dump(preprocessor, f)

    timestamp = datetime.now(timezone.utc).isoformat()
    metrics_payload = {
        "best_model": best_name,
        "trained_at": timestamp,
        "training_samples": len(X_train),
        "test_samples": len(X_test),
        "metrics": all_metrics,
        "feature_importance": importance,
        "num_features": num_features,
        "cat_features": cat_features,
    }

    with open(METRICS_PATH, "w") as f:
        json.dump(metrics_payload, f, indent=2)

    with open(IMPORTANCE_PATH, "w") as f:
        json.dump(importance, f, indent=2)

    logger.info("Artefacts saved to %s", ARTIFACTS_DIR)
    return metrics_payload


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
    result = train()
    print("\n=== Training Complete ===")
    print(f"Best model : {result['best_model']}")
    print(f"Trained at : {result['trained_at']}")
    for m in result["metrics"]:
        print(
            f"  {m['model_name']:25s} "
            f"AUC={m['roc_auc']:.4f}  F1={m['f1_score']:.4f}  "
            f"Acc={m['accuracy']:.4f}"
        )
