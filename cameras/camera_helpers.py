from typing import Any, Optional
from connection_managers.ring_connection_manager import RingConnectionManager
from utils.logging_config import get_logger

from ring_doorbell import Ring, RingDoorBell

logger = get_logger(__name__)

def find_device(connection_manager: 'RingConnectionManager', device_name: str) -> Optional[Any]:
    """Find a Ring device by name.
    
    Args:
        connection_manager: The Ring connection manager
        device_name: Name of the device to find
        
    Returns:
        The device object if found, None otherwise
    """
    if connection_manager._ring is None:
        return None
        
    connection_manager._ring.update_data()
    for device in connection_manager._ring.video_devices():
        if device.name == device_name:
            return device
    return None

async def get_video_device_object(ring: Ring, device_name: str) -> Optional[RingDoorBell]:
    """Get video device object from Ring."""
    try:
        ring.update_data()
        devices = ring.video_devices()
        for device in devices:
            if device.name == device_name:
                return device
        return None
    except Exception as e:
        logger.error(f"Failed to get video devices: {e}")
        raise

def get_camera_name(self: Any, camera_id: str) -> Optional[str]:
    """
    Retrieves the name of a specific Ring camera.
    Args:
        camera_id: The ID of the camera to get the name for
    Returns:
        The name of the camera if found, None otherwise
    """
    if not self._is_authenticated:
        logger.info("Not authenticated, skipping get_camera_name")
        return None
    
    try:
        if self._ring is None:
            return None
            
        self._ring.update_data()
        cameras = self._ring.video_devices()
        for camera in cameras:
            if str(camera.id) == str(camera_id):
                logger.info(f"Found camera name: {camera.name}")
                return str(camera.name)  # Explicitly convert to str
        logger.warning(f"No camera found with ID {camera_id}")
        return None
    except Exception as e:
        logger.error(f"Error retrieving camera name: {e}")
        logger.exception("Full traceback:")
        return None