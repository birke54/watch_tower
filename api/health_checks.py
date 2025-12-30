"""
Health Check Functions

Functions for checking the health status of various system components.
"""

import logging
from typing import List, Optional, Tuple

from sqlalchemy import text

from aws.exceptions import ConfigError, ClientError, RekognitionError, S3Error
from aws.rekognition.rekognition_service import REKOGNITION_SERVICE
from aws.s3.s3_service import S3_SERVICE
from db.connection import get_database_connection
from db.exceptions import DatabaseConnectionError
from watch_tower.config import config
from watch_tower.core.business_logic_manager import BUSINESS_LOGIC_MANAGER as business_logic_manager
from watch_tower.exceptions import BusinessLogicError
from watch_tower.registry.camera_registry import REGISTRY as camera_registry

from api.schemas import ComponentHealth, BusinessLogicStatus, CameraInfo

logger = logging.getLogger(__name__)


def check_database_health() -> ComponentHealth:
    """Check database connection health.
    
    Returns:
        ComponentHealth: Health status of the database connection
    """
    try:
        _, session_factory = get_database_connection()
        with session_factory() as session:
            session.execute(text("SELECT 1"))
        return ComponentHealth(healthy=True)
    except DatabaseConnectionError as e:
        error_msg = f"Database connection error: {str(e)}"
        logger.error(error_msg)
        return ComponentHealth(healthy=False, error=error_msg)
    except Exception as e:
        error_msg = f"Database health check failed: {str(e)}"
        logger.error(error_msg)
        return ComponentHealth(healthy=False, error=error_msg)


def check_aws_s3_health() -> ComponentHealth:
    """Check AWS S3 service health.
    
    Returns:
        ComponentHealth: Health status of the AWS S3 service
    """
    try:
        S3_SERVICE.check_bucket_exists(config.event_recordings_bucket)
        return ComponentHealth(healthy=True)
    except ConfigError as e:
        error_msg = f"AWS configuration error: {str(e)}"
        logger.error(error_msg)
        return ComponentHealth(healthy=False, error=error_msg)
    except ClientError as e:
        error_msg = f"AWS client error: {str(e)}"
        logger.error(error_msg)
        return ComponentHealth(healthy=False, error=error_msg)
    except S3Error as e:
        error_msg = f"AWS S3 health check failed: {str(e)}"
        logger.error(error_msg)
        return ComponentHealth(healthy=False, error=error_msg)


def check_aws_rekognition_health() -> ComponentHealth:
    """Check AWS Rekognition service health.
    
    Returns:
        ComponentHealth: Health status of the AWS Rekognition service
    """
    try:
        REKOGNITION_SERVICE.check_collection_exists(config.rekognition_collection_id)
        return ComponentHealth(healthy=True)
    except RekognitionError as e:
        error_msg = f"AWS Rekognition error: {str(e)}"
        logger.error(error_msg)
        return ComponentHealth(healthy=False, error=error_msg)
    except Exception as e:
        error_msg = f"AWS Rekognition health check failed: {str(e)}"
        logger.error(error_msg)
        return ComponentHealth(healthy=False, error=error_msg)


def get_business_logic_status() -> BusinessLogicStatus:
    """Get business logic loop status.
    
    Returns:
        BusinessLogicStatus: Current status of the business logic loop
    """
    try:
        status = business_logic_manager.get_status()
        return BusinessLogicStatus(
            running=status.get('running', False),
            uptime=status.get('uptime'),
            start_time=status.get('start_time')
        )
    except BusinessLogicError as e:
        error_msg = f"Business logic error: {str(e)}"
        logger.error(error_msg)
        return BusinessLogicStatus(
            running=False,
            uptime='Unknown',
            start_time='Unknown',
            error=error_msg
        )
    except Exception as e:
        error_msg = f"Business logic loop status check failed: {str(e)}"
        logger.error(error_msg)
        return BusinessLogicStatus(
            running=False,
            uptime='Unknown',
            start_time='Unknown',
            error=error_msg
        )


def get_camera_health() -> Tuple[List[CameraInfo], Optional[str]]:
    """Get camera registry health information.
    
    Returns:
        Tuple containing:
            - List of CameraInfo objects for each registered camera
            - Optional error message if camera registry check failed
    """
    cameras = []
    camera_error = None
    try:
        for entry in camera_registry.cameras.values():
            camera = entry.camera
            name = getattr(camera, 'name', str(camera))
            vendor = getattr(camera, 'plugin_type', 'UNKNOWN')
            status = entry.status.name
            healthy = status == 'ACTIVE'
            cameras.append(CameraInfo(
                name=name,
                vendor=str(vendor),
                status=status,
                healthy=healthy,
                last_polled=str(entry.last_polled),
                status_last_updated=str(entry.status_last_updated)
            ))
    except Exception as e:
        camera_error = f"Camera registry health check failed: {str(e)}"
        logger.error(camera_error)
    return cameras, camera_error

