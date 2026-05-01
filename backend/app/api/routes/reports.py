"""
Report generation routes.

Endpoints:
  POST /reports/pdf      — PDF executive report (reportlab)
  POST /reports/csv      — CSV customer action list
  POST /reports/ppt      — PowerPoint summary (python-pptx) or Markdown fallback
  POST /reports/markdown — Structured Markdown executive report (no extra deps)
  GET  /reports/export/{filename} — download any generated report
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.schemas.report_schema import ReportRequest, ReportResponse
from app.services.report_service import ReportService

router = APIRouter()

_service: ReportService | None = None


def get_service() -> ReportService:
    global _service
    if _service is None:
        _service = ReportService()
    return _service


@router.post("/pdf", response_model=ReportResponse, summary="Generate PDF executive report")
async def generate_pdf(body: ReportRequest) -> ReportResponse:
    """Generate a PDF executive report and return its download path."""
    try:
        return get_service().generate_pdf(body)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/csv", response_model=ReportResponse, summary="Generate CSV customer action list")
async def generate_csv(body: ReportRequest) -> ReportResponse:
    """Export high-risk customer action list as a downloadable CSV."""
    try:
        return get_service().generate_csv(body)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/ppt", response_model=ReportResponse, summary="Generate PPT or Markdown summary")
async def generate_ppt(body: ReportRequest) -> ReportResponse:
    """
    Generate a PowerPoint business summary.
    Falls back to a Markdown report if python-pptx is unavailable.
    """
    try:
        return get_service().generate_ppt(body)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/markdown",
    response_model=ReportResponse,
    summary="Generate structured Markdown executive report",
    tags=["Reports"],
)
async def generate_markdown(body: ReportRequest) -> ReportResponse:
    """
    Generate a 6-section business-readable Markdown report:

    1. Executive Summary — from KPI insight or executive_note
    2. Current State — churn rate, revenue at risk, core KPIs
    3. Key Insights — top 3 drivers from the decision engine
    4. Financial Impact — revenue at risk (risk > 0.6), high-value customers
    5. Recommended Actions — top 3 from the priority list
    6. Expected Outcome — derived recovery estimate with confidence level

    No extra dependencies. Report saved to /reports/ and returned as a download path.
    """
    try:
        return get_service().generate_markdown_report(body)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Dataset not available — cannot generate report: {exc}",
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/export/{filename}", summary="Download a generated report file")
async def download_report(filename: str) -> FileResponse:
    """Stream a previously generated report file by filename."""
    import os
    from app.config import settings

    filepath = os.path.join(settings.REPORTS_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail=f"Report '{filename}' not found.")
    return FileResponse(path=filepath, filename=filename)
