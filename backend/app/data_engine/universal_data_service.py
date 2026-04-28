"""
Universal Data Service
POST /upload/data

Handles CSV, Excel, TXT, PDF uploads.
Profiles the dataset and infers domain context using deterministic rules.
No paid APIs or external LLMs required.

──────────────────────────────────────────────────────────────────
DOMAIN INFERENCE RULES (column-name keyword matching)
──────────────────────────────────────────────────────────────────
churn / customer / retention / tenure / subscription → Customer Retention
sales / revenue / date / sku / product / order       → Revenue Forecasting
employee / attrition / salary / department / hr      → HR Analytics
loan / credit / default / borrower / interest        → Credit Risk
transaction / fraud / amount / merchant              → Fraud Detection
inventory / demand / stock / warehouse / supply      → Supply Chain
(otherwise)                                          → General Analytics
"""
from __future__ import annotations

import io
import os
import uuid
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# ─────────────────────────────────────────────────────────────────────────────
# Module-level store — holds context of the LATEST uploaded file.
# Used by MultiAgentOrchestrator to answer questions about uploaded data.
# ─────────────────────────────────────────────────────────────────────────────

_LATEST_UPLOAD: Optional[Dict[str, Any]] = None

LARGE_FILE_THRESHOLD_BYTES = 50 * 1024 * 1024   # 50 MB → sample profiling
SAMPLE_ROWS_FOR_PROFILE    = 100_000             # rows to read for large files
MAX_TEXT_SAMPLE            = 8_000               # chars for TXT/PDF preview


def get_latest_upload_context() -> Optional[Dict[str, Any]]:
    """Return the inference context from the most recently uploaded file."""
    return _LATEST_UPLOAD


def _set_latest_upload(ctx: Dict[str, Any]) -> None:
    global _LATEST_UPLOAD
    _LATEST_UPLOAD = ctx


# ─────────────────────────────────────────────────────────────────────────────
# Domain inference
# ─────────────────────────────────────────────────────────────────────────────

_DOMAIN_RULES: List[Tuple[str, List[str]]] = [
    ("Customer Retention",   ["churn", "retention", "tenure", "subscription", "customer_id", "customerid", "monthly_charges", "contract"]),
    ("Revenue Forecasting",  ["sales", "revenue", "order", "sku", "product", "invoice", "fiscal", "forecast", "discount"]),
    ("HR Analytics",         ["employee", "attrition", "salary", "department", "hr", "headcount", "performance", "hire", "termination"]),
    ("Credit Risk",          ["loan", "credit", "default", "borrower", "interest", "delinquent", "repayment", "collateral", "mortgage"]),
    ("Fraud Detection",      ["fraud", "transaction", "merchant", "suspicious", "flagged", "card", "account_balance", "anomaly"]),
    ("Supply Chain",         ["inventory", "demand", "stock", "warehouse", "supply", "shipment", "sku", "logistics", "reorder"]),
]


def _infer_domain(col_names: List[str], text_sample: str = "") -> str:
    combined = " ".join(col_names).lower() + " " + text_sample[:500].lower()
    scores: Dict[str, int] = {}
    for domain, keywords in _DOMAIN_RULES:
        score = sum(1 for kw in keywords if kw in combined)
        if score:
            scores[domain] = score
    if not scores:
        return "General Analytics"
    return max(scores, key=lambda d: scores[d])


_DOMAIN_META: Dict[str, Dict[str, List[str]]] = {
    "Customer Retention": {
        "use_cases":   ["Churn prediction", "Retention campaign targeting", "CLV optimisation", "Cohort analysis"],
        "key_metrics": ["Churn rate", "Customer Lifetime Value (CLV)", "Monthly Recurring Revenue (MRR)", "Net Revenue Retention", "CSAT / NPS"],
        "analysis":    ["Segment churn by plan/region", "Build churn propensity model", "Run scenario simulation for retention budget", "Identify high-value at-risk customers"],
    },
    "Revenue Forecasting": {
        "use_cases":   ["Sales trend forecasting", "Product performance analysis", "Discount impact modelling", "Revenue attribution"],
        "key_metrics": ["Total revenue", "Revenue growth rate", "Average order value", "Conversion rate", "Win rate"],
        "analysis":    ["Time-series decomposition", "Product-level revenue breakdown", "Seasonal demand analysis", "Price elasticity study"],
    },
    "HR Analytics": {
        "use_cases":   ["Attrition prediction", "Workforce planning", "Compensation benchmarking", "Diversity & inclusion reporting"],
        "key_metrics": ["Attrition rate", "Average tenure", "Salary percentile", "Headcount growth", "Time-to-hire"],
        "analysis":    ["Attrition drivers by department", "Salary band analysis", "Performance vs. retention correlation", "Flight-risk identification"],
    },
    "Credit Risk": {
        "use_cases":   ["Default probability scoring", "Credit limit optimisation", "Portfolio risk management", "Regulatory stress testing"],
        "key_metrics": ["Default rate", "Loss Given Default (LGD)", "Probability of Default (PD)", "Debt-to-Income ratio"],
        "analysis":    ["Scorecard modelling", "Vintage analysis", "Segment-level risk profiling", "Delinquency trend tracking"],
    },
    "Fraud Detection": {
        "use_cases":   ["Real-time fraud scoring", "Anomaly detection", "Transaction pattern analysis", "False positive reduction"],
        "key_metrics": ["Fraud rate", "False positive rate", "Detection precision/recall", "Average fraud amount"],
        "analysis":    ["Merchant-level fraud clustering", "Time-of-day patterns", "Device / channel risk scoring", "Network graph analysis"],
    },
    "Supply Chain": {
        "use_cases":   ["Demand forecasting", "Inventory optimisation", "Supplier performance tracking", "Stockout risk modelling"],
        "key_metrics": ["Fill rate", "Days of inventory outstanding (DIO)", "Stockout frequency", "Lead time variance"],
        "analysis":    ["SKU-level demand decomposition", "Reorder point optimisation", "Supplier reliability scoring", "Safety stock calibration"],
    },
    "General Analytics": {
        "use_cases":   ["Descriptive analysis", "KPI dashboard", "Trend identification", "Data quality baseline"],
        "key_metrics": ["Record count", "Coverage %", "Numeric summary stats", "Categorical distribution"],
        "analysis":    ["Column profiling", "Outlier detection", "Correlation matrix", "Missing value imputation strategy"],
    },
}


def infer_dataset_context(
    df_or_text: "pd.DataFrame | str",
    filename: str = "",
) -> Dict[str, Any]:
    """
    Rule-based dataset domain inference.

    Parameters
    ----------
    df_or_text : pd.DataFrame for tabular files, str for TXT/PDF
    filename   : original filename — used as extra signal

    Returns
    -------
    dict with detected_domain, possible_use_cases, key_metrics,
    data_quality_issues, recommended_analysis, executive_summary
    """
    if isinstance(df_or_text, pd.DataFrame):
        col_names  = list(df_or_text.columns)
        text_extra = filename
    else:
        col_names  = []
        text_extra = str(df_or_text)[:500] + " " + filename

    domain = _infer_domain(col_names, text_extra)
    meta   = _DOMAIN_META.get(domain, _DOMAIN_META["General Analytics"])

    # Data quality issues (only for DataFrames)
    issues: List[str] = []
    if isinstance(df_or_text, pd.DataFrame):
        df = df_or_text
        miss_pct = df.isnull().mean() * 100
        high_miss = miss_pct[miss_pct > 20]
        for col, pct in high_miss.items():
            issues.append(f"'{col}' has {pct:.1f}% missing values")
        dup_count = int(df.duplicated().sum())
        if dup_count:
            issues.append(f"{dup_count:,} duplicate rows detected ({dup_count/max(len(df),1)*100:.1f}%)")
        for col in df.select_dtypes(include="number").columns:
            s = pd.to_numeric(df[col], errors="coerce")
            q1, q3 = s.quantile(0.25), s.quantile(0.75)
            iqr = q3 - q1
            n_out = int(((s < q1 - 3*iqr) | (s > q3 + 3*iqr)).sum())
            if n_out > max(5, len(df) * 0.01):
                issues.append(f"'{col}' contains {n_out:,} potential outliers")
                if len(issues) >= 6:  # cap for readability
                    break

    row_info = ""
    if isinstance(df_or_text, pd.DataFrame):
        row_info = f" across {len(df_or_text):,} rows and {len(df_or_text.columns)} columns"

    exec_summary = (
        f"This dataset appears to be a **{domain}** dataset{row_info}. "
        f"Primary use cases include {', '.join(meta['use_cases'][:2])}. "
        f"Key metrics to track: {', '.join(meta['key_metrics'][:3])}. "
        + (f" {len(issues)} data quality issue(s) flagged." if issues else " No critical quality issues detected.")
    )

    return {
        "detected_domain":      domain,
        "possible_use_cases":   meta["use_cases"],
        "key_metrics":          meta["key_metrics"],
        "data_quality_issues":  issues if issues else ["No critical issues detected"],
        "recommended_analysis": meta["analysis"],
        "executive_summary":    exec_summary,
    }


# ─────────────────────────────────────────────────────────────────────────────
# File reading
# ─────────────────────────────────────────────────────────────────────────────

def _read_csv(path: str, file_size: int) -> Tuple[pd.DataFrame, List[str]]:
    warnings: List[str] = []
    if file_size > LARGE_FILE_THRESHOLD_BYTES:
        warnings.append(
            f"Large file ({file_size / 1024**2:.1f} MB) — profiling first "
            f"{SAMPLE_ROWS_FOR_PROFILE:,} rows only."
        )
        chunks = []
        reader = pd.read_csv(path, chunksize=10_000, low_memory=True)
        rows_read = 0
        for chunk in reader:
            chunks.append(chunk)
            rows_read += len(chunk)
            if rows_read >= SAMPLE_ROWS_FOR_PROFILE:
                break
        df = pd.concat(chunks, ignore_index=True)
    else:
        df = pd.read_csv(path, low_memory=False)
    df.columns = [str(c).strip() for c in df.columns]
    return df, warnings


def _read_excel(path: str, file_size: int) -> Tuple[pd.DataFrame, List[str], List[str]]:
    warnings: List[str] = []
    sheet_names: List[str] = []
    try:
        xl = pd.ExcelFile(path, engine="openpyxl")
        sheet_names = xl.sheet_names
        if len(sheet_names) > 1:
            warnings.append(
                f"Workbook has {len(sheet_names)} sheets: {sheet_names}. "
                f"Profiling first sheet '{sheet_names[0]}'."
            )
        df = xl.parse(sheet_names[0])
        if file_size > LARGE_FILE_THRESHOLD_BYTES:
            warnings.append(
                f"Large Excel file ({file_size / 1024**2:.1f} MB) — "
                f"profiling first {SAMPLE_ROWS_FOR_PROFILE:,} rows."
            )
            df = df.head(SAMPLE_ROWS_FOR_PROFILE)
        df.columns = [str(c).strip() for c in df.columns]
    except ImportError:
        raise RuntimeError("openpyxl is not installed. Run: pip install openpyxl")
    return df, warnings, sheet_names


def _read_txt(path: str) -> Tuple[Optional[pd.DataFrame], str, List[str]]:
    warnings: List[str] = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read(MAX_TEXT_SAMPLE * 4)   # read a bit more to try CSV detection

    # Try to detect delimited structure (CSV / TSV inside TXT)
    sample_lines = text.split("\n")[:20]
    for sep, sep_name in [(",", "CSV"), ("\t", "TSV"), ("|", "pipe-delimited")]:
        col_counts = [len(line.split(sep)) for line in sample_lines if line.strip()]
        if col_counts and min(col_counts) > 1 and max(col_counts) - min(col_counts) <= 2:
            try:
                df = pd.read_csv(io.StringIO(text), sep=sep)
                if len(df.columns) > 1:
                    warnings.append(f"TXT file detected as {sep_name} — parsed as table.")
                    return df, text[:MAX_TEXT_SAMPLE], warnings
            except Exception:
                pass

    warnings.append("TXT file could not be parsed as tabular data — showing text sample.")
    return None, text[:MAX_TEXT_SAMPLE], warnings


def _read_pdf(path: str) -> Tuple[str, List[str]]:
    warnings: List[str] = []
    text = ""
    try:
        import pypdf  # type: ignore
        reader = pypdf.PdfReader(path)
        parts = []
        for page in reader.pages[:20]:   # cap at 20 pages
            parts.append(page.extract_text() or "")
        text = "\n".join(parts)[:MAX_TEXT_SAMPLE]
        if not text.strip():
            warnings.append("PDF text extraction returned empty content — may be a scanned/image PDF.")
    except ImportError:
        try:
            import PyPDF2  # type: ignore
            with open(path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                parts = []
                for page in reader.pages[:20]:
                    parts.append(page.extract_text() or "")
            text = "\n".join(parts)[:MAX_TEXT_SAMPLE]
        except ImportError:
            warnings.append(
                "PDF text extraction unavailable — neither 'pypdf' nor 'PyPDF2' is installed. "
                "Run: pip install pypdf"
            )
    return text, warnings


# ─────────────────────────────────────────────────────────────────────────────
# Profiling
# ─────────────────────────────────────────────────────────────────────────────

def _safe_val(v) -> Any:
    """Convert numpy scalars and NaN to plain Python for JSON serialisation."""
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        f = float(v)
        return None if (f != f) else f   # NaN check
    return v


def profile_dataframe(df: pd.DataFrame) -> Dict[str, Any]:
    num_cols  = list(df.select_dtypes(include="number").columns)
    cat_cols  = list(df.select_dtypes(include=["object", "category", "bool"]).columns)
    miss_map  = {col: int(df[col].isna().sum()) for col in df.columns if df[col].isna().any()}
    miss_pct  = {col: round(cnt / max(len(df), 1) * 100, 2) for col, cnt in miss_map.items()}
    top5_miss = sorted(miss_pct.items(), key=lambda x: x[1], reverse=True)[:5]
    dup_rows  = int(df.duplicated().sum())

    # Summary stats for numeric columns (cap at 20 cols to keep response lean)
    summary_stats: Dict[str, Any] = {}
    for col in num_cols[:20]:
        s = pd.to_numeric(df[col], errors="coerce")
        desc = s.describe()
        summary_stats[col] = {k: _safe_val(v) for k, v in desc.items()}

    # Sample rows — first 5, drop nulls for readability
    sample = df.head(5).replace({np.nan: None}).to_dict(orient="records")
    for row in sample:
        for k, v in row.items():
            row[k] = _safe_val(v)

    return {
        "column_count":        len(df.columns),
        "numeric_columns":     num_cols,
        "categorical_columns": cat_cols,
        "missing_values":      miss_map,
        "missing_pct":         miss_pct,
        "duplicate_rows":      dup_rows,
        "top_missing_columns": [{"column": c, "missing_pct": p} for c, p in top5_miss],
        "summary_stats":       summary_stats,
        "sample_rows":         sample,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────

ALLOWED_TYPES = {
    "text/csv":                                                        "csv",
    "application/vnd.ms-excel":                                        "xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/pdf":                                                 "pdf",
    "text/plain":                                                      "txt",
    "application/octet-stream":                                        None,  # resolved by extension
}

EXTENSION_MAP = {
    ".csv":  "csv",
    ".xls":  "xls",
    ".xlsx": "xlsx",
    ".txt":  "txt",
    ".pdf":  "pdf",
}


def process_upload(
    file_path: str,
    original_filename: str,
    content_type: str,
    file_size: int,
    uploads_dir: str,
) -> Dict[str, Any]:
    """
    Core upload processing pipeline.

    1. Detect file type
    2. Read into DataFrame (or raw text for PDF/TXT)
    3. Profile the data
    4. Infer domain
    5. Store context globally for multi-agent access
    6. Return structured response dict
    """
    warnings: List[str] = []
    sheet_names: List[str] = []
    text_sample: str = ""

    # Resolve file type
    ext = os.path.splitext(original_filename)[1].lower()
    file_type = EXTENSION_MAP.get(ext) or ALLOWED_TYPES.get(content_type)
    if file_type is None:
        file_type = "unknown"
        warnings.append(
            f"Unknown file type (extension='{ext}', content-type='{content_type}'). "
            "Attempting CSV parse."
        )

    # Read
    df: Optional[pd.DataFrame] = None

    if file_type in ("csv", "unknown"):
        try:
            df, w = _read_csv(file_path, file_size)
            warnings.extend(w)
        except Exception as exc:
            warnings.append(f"CSV parse failed: {exc}")

    elif file_type in ("xls", "xlsx"):
        try:
            df, w, sheet_names = _read_excel(file_path, file_size)
            warnings.extend(w)
        except Exception as exc:
            warnings.append(f"Excel parse failed: {exc}")

    elif file_type == "txt":
        df, text_sample, w = _read_txt(file_path)
        warnings.extend(w)

    elif file_type == "pdf":
        text_sample, w = _read_pdf(file_path)
        warnings.extend(w)

    else:
        warnings.append(f"Unsupported file type: {file_type}")

    # Profile
    rows = 0
    columns: List[str] = []
    profile: Dict[str, Any] = {}

    if df is not None:
        rows    = len(df)
        columns = list(df.columns)
        profile = profile_dataframe(df)
        if sheet_names:
            profile["sheet_names"] = sheet_names
        if text_sample:
            profile["text_sample"] = text_sample

        inference = infer_dataset_context(df, original_filename)
    else:
        # Text-only path (PDF / unparseable TXT)
        profile["text_sample"] = text_sample or ""
        inference = infer_dataset_context(text_sample, original_filename)

    # Build response
    file_id = str(uuid.uuid4())
    result  = {
        "file_id":       file_id,
        "filename":      original_filename,
        "file_type":     file_type,
        "rows":          rows,
        "columns":       columns,
        "profile_summary": profile,
        "inference":     inference,
        "warnings":      warnings,
    }

    # Persist for multi-agent use
    _set_latest_upload({
        "file_id":         file_id,
        "filename":        original_filename,
        "detected_domain": inference["detected_domain"],
        "executive_summary": inference["executive_summary"],
        "key_metrics":     inference["key_metrics"],
        "recommended_analysis": inference["recommended_analysis"],
        "rows":            rows,
        "columns":         columns,
        "data_quality_issues": inference["data_quality_issues"],
    })

    return result
