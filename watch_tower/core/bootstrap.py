"""Bootstrap module for the Watch Tower application. Initializes databases, registers connection managers,
logs into vendors, and retrieves cameras to populate the camera registry."""

import asyncio
from typing import List, Tuple, Any

from watch_tower.registry.camera_registry import REGISTRY as camera_registry
from watch_tower.registry.connection_manager_registry import VendorStatus, REGISTRY as connection_manager_registry
from watch_tower.exceptions import RingConnectionManagerError
from connection_managers.plugin_type import PluginType
from db.connection import get_database_connection
from db.models import Vendors
from db.repositories.vendors_repository import VendorsRepository
from db.camera_state_db import init_camera_state_db
from utils.logging_config import get_logger
from utils.error_handler import handle_async_errors
from utils.performance_monitor import monitor_async_performance
from utils.metrics import MetricDataPointName
from utils.metric_helpers import inc_counter_metric

LOGGER = get_logger(__name__)

ENGINE, SESSION_FACTORY = get_database_connection()


@monitor_async_performance("bootstrap")
@handle_async_errors(log_error=True, reraise=True)
async def bootstrap() -> None:
    """Bootstrap the application."""
    try:
        # Initialize SQLite database for camera state
        init_camera_state_db()

        vendors = retrieve_vendors()
        register_connection_managers(vendors)
        await login_to_vendors()
        cameras = await retrieve_cameras()
        await add_cameras_to_registry(cameras)
        LOGGER.info("Bootstrap successful")
        inc_counter_metric(MetricDataPointName.WATCH_TOWER_BOOTSTRAP_SUCCESS_COUNT)
    except Exception:
        # Log and record metrics for failure, then re-raise
        LOGGER.error("Bootstrap failed")
        inc_counter_metric(MetricDataPointName.WATCH_TOWER_BOOTSTRAP_ERROR_COUNT)
        raise


async def add_cameras_to_registry(cameras: List[Tuple[PluginType, Any]]) -> None:
    """Add cameras to the camera registry."""
    from cameras.ring_camera import RingCamera  # pylint: disable=import-outside-toplevel
    registry = camera_registry  # Use the singleton instance
    LOGGER.info("Adding %d cameras to registry", len(cameras))
    for camera in cameras:
        camera_object = camera[1]
        LOGGER.info("Adding camera: %s", camera_object)
        await registry.add(RingCamera(camera_object))
    LOGGER.info("Camera registry now contains %d cameras", len(registry.cameras))
    LOGGER.info("Active cameras: %d", len(registry.get_all_active()))
    LOGGER.debug("Camera registry: %s", registry.cameras)


def retrieve_vendors() -> List[Vendors]:
    """Retrieve vendors from the database."""
    with SESSION_FACTORY() as session:
        vendors = VendorsRepository().get_all(session)
        LOGGER.info("Retrieved %d vendors from the database", len(vendors))
        LOGGER.debug("Vendors: %s", vendors)
        return list(vendors)  # Convert to list to ensure List[Vendors] return type


def register_connection_managers(vendors: List[Vendors]) -> List[Vendors]:
    """Register connection managers for each vendor."""
    from connection_managers.connection_manager_factory import ConnectionManagerFactory  # pylint: disable=import-outside-toplevel
    for vendor in vendors:
        plugin_type = PluginType(vendor.plugin_type)
        connection_manager = ConnectionManagerFactory.create(plugin_type)
        connection_manager_registry.register_connection_manager(plugin_type, connection_manager)
        LOGGER.debug("Registered connection manager for vendor: %s", vendor)
    LOGGER.info("Registered %d connection managers", len(vendors))


async def login_to_vendors() -> None:
    """Login to vendors."""
    for connection_manager in connection_manager_registry.get_all_connection_managers():
        plugin_type = connection_manager['connection_manager'].plugin_type
        LOGGER.debug(
            "Attempting to login to connection manager: %s",
            connection_manager['connection_manager'].__class__.__name__
        )
        try:
            await connection_manager['connection_manager'].login()
            connection_manager_registry.update_status(plugin_type, VendorStatus.ACTIVE)
            LOGGER.info(
                "Logged in to %s successfully", plugin_type)
        except RingConnectionManagerError as e:
            LOGGER.error(
                "Failed to login to: %s, error: %s", plugin_type, e)


async def retrieve_cameras() -> List[Tuple[PluginType, Any]]:
    """Retrieve active connection managers and retrieve cameras from them."""
    cameras: List[Tuple[PluginType, Any]] = []
    LOGGER.info("Starting camera retrieval process")
    for connection_manager in connection_manager_registry.get_all_connection_managers():
        LOGGER.debug(
            "Checking connection manager: %s, status: %s",
            connection_manager['connection_manager'].__class__.__name__,
            connection_manager['status'])
        if connection_manager['status'] == VendorStatus.ACTIVE:
            LOGGER.debug(
                "%s is active, attempting to get cameras", connection_manager['connection_manager'].__class__.__name__)
            camera_objects = await connection_manager['connection_manager'].get_cameras()
            LOGGER.debug(
                "Retrieved %d camera objects, attempting to add to camera registry", len(camera_objects))
            LOGGER.debug("Camera objects: %s", camera_objects)
            if camera_objects:
                plugin_type = connection_manager['connection_manager'].plugin_type
                cameras.extend([(plugin_type, camera) for camera in camera_objects])
    return cameras


async def __main__() -> None:
    """Main function."""
    await bootstrap()

if __name__ == "__main__":
    asyncio.run(__main__())
