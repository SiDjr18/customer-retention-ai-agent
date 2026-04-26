"""
Pydantic schemas for report generation endpoints.
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel


class ReportRequest(BaseModel):
    title: Optional[str] = "Customer Retention AI — Executive Report"
    region: Optional[str] = None          # optional filter — None = all
    customer_segment: Optional[str] = None
    include_high_risk_list: bool = True
    top_n_customers: int = 50             # rows in customer action list


class ReportResponse(BaseModel):
    report_type: str       # "pdf" | "csv" | "pptx" | "markdown"
    filename: str
    download_path: str     # relative path — use GET /reports/export/{filename}
    generated_at: str
    size_bytes: Optional[int] = None
