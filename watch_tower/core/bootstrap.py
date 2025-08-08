import asyncio
from typing import List, Tuple, Any, cast
from watch_tower.registry.camera_registry import registry as camera_registry
from watch_tower.registry.connection_manager_registry import VendorStatus, registry
from connection_managers.connection_manager_factory import ConnectionManagerFactory
from connection_managers.plugin_type import PluginType
from db.connection import get_database_connection
from db.models import Vendors
from db.camera_state_db import init_camera_state_db
from utils.logging_config import get_logger
from utils.error_handler import handle_async_errors
from utils.performance_monitor import monitor_async_performance

logger = get_logger(__name__)

engine, session_factory = get_database_connection()

@monitor_async_performance("bootstrap")
@handle_async_errors(log_error=True, reraise=True)
async def bootstrap() -> None:
    """Bootstrap the application."""
    # Initialize SQLite database for camera state
    init_camera_state_db()

    vendors = retrieve_vendors()
    register_connection_managers(vendors)
    await login_to_vendors(vendors)
    cameras = await retrieve_cameras(vendors)
    await add_cameras_to_registry(cameras)

async def add_cameras_to_registry(cameras: List[Tuple[PluginType, Any]]) -> None:
    """Add cameras to the camera registry."""
    from cameras.ring_camera import RingCamera
    registry = camera_registry  # Use the singleton instance
    logger.info(f"Adding {len(cameras)} cameras to registry")
    for camera in cameras:
        if camera[0] in PluginType:
            camera_object = camera[1]
            logger.info(f"Adding camera: {camera_object}")
            await registry.add(RingCamera(camera_object))
    logger.info(f"Camera registry now contains {len(registry.cameras)} cameras")
    logger.info(f"Active cameras: {len(registry.get_all_active())}")
    logger.debug(f"Camera registry: {registry.cameras}")

def retrieve_vendors() -> List[Vendors]:
    """Retrieve vendors from the database."""
    with session_factory() as session:
        vendors = session.query(Vendors).all()
        logger.info(f"Retrieved {len(vendors)} vendors from the database")
        logger.debug(f"Vendors: {vendors}")
        return list(vendors)  # Convert to list to ensure List[Vendors] return type

def register_connection_managers(vendors: List[Vendors]) -> None:
    """Register connection managers for each vendor."""
    for vendor in vendors:
        plugin_type = PluginType(vendor.plugin_type)
        connection_manager = ConnectionManagerFactory.create(plugin_type)
        registry.register_connection_manager(plugin_type, connection_manager)
        logger.debug(f"Registered connection manager for {vendor.plugin_type}")
    logger.info(f"Registered {len(vendors)} connection managers")

async def login_to_vendors(vendors: List[Vendors]) -> None:
    """Login to vendors."""
    for connection_manager in registry.get_all_connection_managers():
        logger.debug(f"Attempting to login to {connection_manager['connection_manager'].__class__.__name__}")
        try:
            await connection_manager['connection_manager'].login()
            plugin_type = cast(PluginType, connection_manager['connection_manager']._plugin_type)
            registry.update_status(plugin_type, VendorStatus.ACTIVE)
            logger.info(f"Logged in to {connection_manager['connection_manager'].__class__.__name__}")
        except Exception as e:
            logger.error(f"Failed to login to {connection_manager['connection_manager'].__class__.__name__}: {e}")
            plugin_type = cast(PluginType, connection_manager['connection_manager']._plugin_type)
            registry.update_status(plugin_type, VendorStatus.INACTIVE)

async def retrieve_cameras(vendors: List[Vendors]) -> List[Tuple[PluginType, Any]]:
    """Retrieve active connection managers and retrieve cameras from them."""
    cameras: List[Tuple[PluginType, Any]] = []
    logger.info("Starting camera retrieval process")
    for connection_manager in registry.get_all_connection_managers():
        logger.debug(f"Checking connection manager: {connection_manager['connection_manager'].__class__.__name__}, status: {connection_manager['status']}")
        if connection_manager['status'] == VendorStatus.ACTIVE:
            logger.debug(f"{connection_manager['connection_manager'].__class__.__name__} is active, attempting to get cameras")
            camera_objects = await connection_manager['connection_manager'].get_cameras()
            logger.debug(f"Retrieved {len(camera_objects)} camera objects, attempting to add to camera registry")
            logger.debug(f"Camera objects: {camera_objects}")
            if camera_objects:
                plugin_type = cast(PluginType, connection_manager['connection_manager']._plugin_type)
                cameras.extend([(plugin_type, camera) for camera in camera_objects])
    return cameras

async def __main__() -> None:
    """Main function."""
    await bootstrap()

if __name__ == "__main__":
    asyncio.run(__main__())