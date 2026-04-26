"""Shared / reusable Pydantic schemas."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    message: str
