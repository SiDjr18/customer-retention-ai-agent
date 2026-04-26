"""
Health check route.
GET /health — returns service liveness status.
"""

from fastapi import APIRouter
from app.schemas.common import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Liveness probe — returns 200 when the service is running."""
    return HealthResponse(status="ok", message="Customer Retention AI Agent is running.")
