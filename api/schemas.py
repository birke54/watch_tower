"""
API Schemas

Pydantic models for FastAPI request/response validation and documentation.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class ComponentHealth(BaseModel):
    """Health status of a single component."""
    healthy: bool
    error: Optional[str] = None


class BusinessLogicStatus(BaseModel):
    """Business logic loop status."""
    running: bool
    uptime: Optional[str] = None
    start_time: Optional[str] = None
    error: Optional[str] = None


class CameraInfo(BaseModel):
    """Camera information for health check."""
    name: str
    vendor: str
    status: str
    healthy: bool
    last_polled: str
    status_last_updated: str


class HealthResponse(BaseModel):
    """Health check response model."""
    database: ComponentHealth
    aws_s3: ComponentHealth
    aws_rekognition: ComponentHealth
    business_logic: BusinessLogicStatus
    event_loop: BusinessLogicStatus
    cameras: List[CameraInfo]
    camera_error: Optional[str] = None


class OperationResponse(BaseModel):
    """Response model for start/stop operations."""
    status: str = Field(..., description="Operation status")
    message: str = Field(..., description="Operation message")

