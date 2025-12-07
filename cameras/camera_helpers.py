"""
Camera Helpers Module

This module provides helper functions for working with Ring cameras and devices.
"""
from typing import Any, Optional

from ring_doorbell import Ring, RingDoorBell

from utils.logging_config import get_logger

LOGGER = get_logger(__name__)


def find_device(
        connection_manager: 'RingConnectionManager',
        device_name: str) -> Optional[Any]:
    """Find a Ring device by name.

    Args:
        connection_manager: The Ring connection manager
        device_name: Name of the device to find

    Returns:
        The device object if found, None otherwise
    """
    # Access protected member to check and update Ring data
    if connection_manager._ring is None:  # pylint: disable=protected-access
        return None

    connection_manager._ring.update_data()  # pylint: disable=protected-access
    for device in connection_manager._ring.video_devices():  # pylint: disable=protected-access
        if device.name == device_name:
            return device
    return None


async def get_video_device_object(ring: Ring,
                                  device_name: str) -> Optional[RingDoorBell]:
    """Get video device object from Ring."""
    try:
        ring.update_data()
        devices = ring.video_devices()
        for device in devices:
            if device.name == device_name:
                return device
        return None
    except Exception as e:
        LOGGER.error("Failed to get video devices: %s", e)
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
        LOGGER.info("Not authenticated, skipping get_camera_name")
        return None

    try:
        if self._ring is None:
            return None

        self._ring.update_data()
        cameras = self._ring.video_devices()
        for camera in cameras:
            if str(camera.id) == str(camera_id):
                LOGGER.info("Found camera name: %s", camera.name)
                return str(camera.name)  # Explicitly convert to str
        LOGGER.warning("No camera found with ID %d", camera_id)
        return None
    except Exception as e:
        LOGGER.error("Error retrieving camera name: %s", e)
        LOGGER.exception("Full traceback:")
        return None
