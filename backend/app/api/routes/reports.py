"""
Report generation routes.

Endpoints:
  POST /reports/pdf  — PDF executive report (reportlab)
  POST /reports/csv  — CSV customer action list
  POST /reports/ppt  — PowerPoint summary (python-pptx) or Markdown fallback
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


@router.get("/export/{filename}", summary="Download a generated report file")
async def download_report(filename: str) -> FileResponse:
    """Stream a previously generated report file by filename."""
    import os
    from app.config import settings

    filepath = os.path.join(settings.REPORTS_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail=f"Report '{filename}' not found.")
    return FileResponse(path=filepath, filename=filename)
