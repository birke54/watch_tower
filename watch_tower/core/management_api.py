"""
Management API

This module provides a FastAPI-based management API for monitoring and controlling
the Watch Tower application.
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from watch_tower.registry.camera_registry import registry as camera_registry
from watch_tower.config import config
import logging
from watch_tower.core.business_logic_manager import business_logic_manager
from watch_tower.exceptions import BusinessLogicError, ConfigurationError
from db.exceptions import DatabaseConnectionError
from aws.exceptions import ConfigError, ClientError

def create_management_app():
    """Create and return the FastAPI management application."""
    app = FastAPI(title="Watch Tower Management API", description="API for managing and monitoring the Watch Tower application")
    logger = logging.getLogger(__name__)

    @app.get("/health")
    async def health():
        # Database health
        db_healthy = False
        db_error = None
        try:
            from db.connection import get_database_connection
            from sqlalchemy import text
            engine, session_factory = get_database_connection()
            with session_factory() as session:
                session.execute(text("SELECT 1"))
            db_healthy = True
        except DatabaseConnectionError as e:
            db_error = f"Database connection error: {str(e)}"
            logger.error(db_error)
        except Exception as e:
            db_error = f"Database health check failed: {str(e)}"
            logger.error(db_error)

        # AWS health
        aws_healthy = False
        aws_error = None
        try:
            from aws.s3.s3_service import s3_service
            s3_service.check_bucket_exists(config.event_recordings_bucket)
            aws_healthy = True
        except ConfigError as e:
            aws_error = f"AWS configuration error: {str(e)}"
            logger.error(aws_error)
        except ClientError as e:
            aws_error = f"AWS client error: {str(e)}"
            logger.error(aws_error)
        except Exception as e:
            aws_error = f"AWS health check failed: {str(e)}"
            logger.error(aws_error)

        # Business logic loop status
        business_logic_status = {}
        bl_error = None
        try:
            status = business_logic_manager.get_status()
            business_logic_status = {
                'running': status['running'],
                'uptime': status['uptime'],
                'start_time': status['start_time']
            }
        except BusinessLogicError as e:
            bl_error = f"Business logic error: {str(e)}"
            logger.error(bl_error)
            business_logic_status = {
                'running': False,
                'uptime': 'Unknown',
                'start_time': 'Unknown',
                'error': bl_error
            }
        except Exception as e:
            bl_error = f"Business logic loop status check failed: {str(e)}"
            logger.error(bl_error)
            business_logic_status = {
                'running': False,
                'uptime': 'Unknown',
                'start_time': 'Unknown',
                'error': bl_error
            }

        # Real-time camera registry health
        cameras = []
        camera_error = None
        try:
            for entry in camera_registry.cameras.values():
                camera = entry.camera
                name = getattr(camera, 'name', str(camera))
                vendor = getattr(camera, 'plugin_type', 'UNKNOWN')
                status = entry.status.name
                healthy = status == 'ACTIVE'
                cameras.append({
                    'name': name,
                    'vendor': str(vendor),
                    'status': status,
                    'healthy': healthy,
                    'last_polled': str(entry.last_polled),
                    'status_last_updated': str(entry.status_last_updated)
                })
        except Exception as e:
            camera_error = f"Camera registry health check failed: {str(e)}"
            logger.error(camera_error)

        # Build response with detailed error information
        response = {
            'database': {
                'healthy': db_healthy,
                'error': db_error
            },
            'aws': {
                'healthy': aws_healthy,
                'error': aws_error
            },
            'business_logic': business_logic_status,
            'event_loop': business_logic_status,
            'cameras': cameras
        }

        if camera_error:
            response['camera_error'] = camera_error

        return JSONResponse(response)

    @app.post("/stop")
    async def stop_business_logic():
        """Stop the business logic loop via HTTP API."""
        try:
            logger.info("Received HTTP request to stop business logic loop")
            await business_logic_manager.stop()
            return JSONResponse({
                "status": "success",
                "message": "Business logic loop stopped successfully"
            })
        except BusinessLogicError as e:
            logger.error(f"Business logic error while stopping: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Business logic error: {str(e)}"
            )
        except ConfigurationError as e:
            logger.error(f"Configuration error while stopping: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Configuration error: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Unexpected error while stopping business logic loop: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Internal server error: {str(e)}"
            )

    @app.post("/start")
    async def start_business_logic():
        """Start the business logic loop via HTTP API."""
        try:
            logger.info("Received HTTP request to start business logic loop")
            await business_logic_manager.start()
            return JSONResponse({
                "status": "success",
                "message": "Business logic loop started successfully"
            })
        except BusinessLogicError as e:
            logger.error(f"Business logic error while starting: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Business logic error: {str(e)}"
            )
        except ConfigurationError as e:
            logger.error(f"Configuration error while starting: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Configuration error: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Unexpected error while starting business logic loop: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Internal server error: {str(e)}"
            )

    return app

app = create_management_app()