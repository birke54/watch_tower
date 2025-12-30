"""
Management API

This module provides a FastAPI-based management API for monitoring and controlling
the Watch Tower application.
"""

import logging

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from utils import metrics as metrics_module  # noqa: F401 - Imported for side effects
from watch_tower.core.business_logic_manager import BUSINESS_LOGIC_MANAGER as business_logic_manager
from watch_tower.exceptions import BusinessLogicError, ConfigurationError

from api.errors import handle_business_logic_operation_error
from api.schemas import HealthResponse, OperationResponse
from api.health_checks import (
    check_aws_s3_health,
    check_database_health,
    get_business_logic_status,
    get_camera_health,
    check_aws_rekognition_health,
)

logger = logging.getLogger(__name__)


def create_management_app() -> FastAPI:
    """Create and return the FastAPI management application."""
    app = FastAPI(
        title="Watch Tower Management API",
        description="API for managing and monitoring the Watch Tower application"
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins (development only!)
        allow_credentials=False,  # Must be False when using allow_origins=["*"]
        allow_methods=["GET", "POST", "HEAD"],
        allow_headers=["*"],  # Allow all headers
    )

    async def _control_business_logic(operation: str, action: str) -> OperationResponse:
        """Shared handler for start/stop business logic operations."""
        try:
            logger.info(f"Received HTTP request to {operation} business logic loop")
            if action == "start":
                await business_logic_manager.start()
                message = "Business logic loop started successfully"
            else:
                await business_logic_manager.stop()
                message = "Business logic loop stopped successfully"
            
            return OperationResponse(status="success", message=message)
        except (BusinessLogicError, ConfigurationError, Exception) as e:
            handle_business_logic_operation_error(operation, e)

    @app.get(
        "/health",
        response_model=HealthResponse,
        summary="System Health Check",
        description="Returns the health status of all system components including database, AWS, business logic, and cameras."
    )
    async def health() -> HealthResponse:
        """Get comprehensive system health status."""
        database_health = check_database_health()
        aws_s3_health = check_aws_s3_health()
        aws_rekognition_health = check_aws_rekognition_health()
        business_logic_status = get_business_logic_status()
        cameras, camera_error = get_camera_health()

        return HealthResponse(
            database=database_health,
            aws_s3=aws_s3_health,
            aws_rekognition=aws_rekognition_health,
            business_logic=business_logic_status,
            event_loop=business_logic_status,  # Alias for backward compatibility
            cameras=cameras,
            camera_error=camera_error
        )

    @app.post(
        "/start",
        response_model=OperationResponse,
        summary="Start Business Logic Loop",
        description="Starts the business logic loop that processes camera events and manages video analysis."
    )
    async def start_business_logic() -> OperationResponse:
        """Start the business logic loop via HTTP API."""
        return await _control_business_logic("start", "start")

    @app.post(
        "/stop",
        response_model=OperationResponse,
        summary="Stop Business Logic Loop",
        description="Stops the business logic loop gracefully, allowing current operations to complete."
    )
    async def stop_business_logic() -> OperationResponse:
        """Stop the business logic loop via HTTP API."""
        return await _control_business_logic("stop", "stop")
    
    @app.api_route(
        "/metrics",
        methods=["GET", "HEAD"],
        summary="Prometheus Metrics",
        description="Endpoint for Prometheus to scrape application metrics."
    )
    async def metrics_scraper() -> Response:
        """Endpoint for Prometheus to scrape metrics."""
        metrics_data = generate_latest()
        return Response(
            content=metrics_data,
            media_type=CONTENT_TYPE_LATEST
        )

    return app


app = create_management_app()

