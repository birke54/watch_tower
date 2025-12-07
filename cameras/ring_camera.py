"""
Ring Camera Module

This module provides the Ring camera implementation, handling motion event
retrieval, video download, and S3 upload for Ring doorbell devices.
"""
"""
Ring Camera Module

This module provides the Ring camera implementation, handling motion event
retrieval, video download, and S3 upload for Ring doorbell devices.
"""
import os
import tempfile
from datetime import datetime
import tempfile
from datetime import datetime
from typing import Any, Dict, List, cast

import requests
import requests
from ring_doorbell import RingDoorBell

from cameras.camera_base import CameraBase
from connection_managers.plugin_type import PluginType
from connection_managers.ring_connection_manager import RingConnectionManager
from data_models.motion_event import MotionEvent
from db.connection import get_database_connection
from db.repositories.motion_event_repository import MotionEventRepository

from aws.s3.s3_service import S3_SERVICE
from watch_tower.config import config

from aws.s3.s3_service import S3_SERVICE
from watch_tower.config import config
from watch_tower.exceptions import DatabaseEventNotFoundError
from watch_tower.registry.connection_manager_registry import (
    REGISTRY as connection_manager_registry
)
from utils.logging_config import get_logger
from utils.video_converter import video_converter

try:
    from zoneinfo import ZoneInfo
except ImportError:
    # Fallback for Python < 3.9
    import pytz
    ZoneInfo = pytz.timezone

LOGGER = get_logger(__name__)


class RingCamera(CameraBase):
    """Ring camera implementation."""

    def __init__(self, device_object: RingDoorBell) -> None:
        """Initialize a Ring camera.

        Args:
            device_object: The Ring doorbell device object

        Raises:
            ValueError: If the device cannot be found
        """
        self.device_object = device_object
        # Initialize the base class with current time and poll interval from config
        super().__init__(config.ring.motion_poll_interval)

    @property
    def plugin_type(self) -> PluginType:
        """Get the plugin type for this camera."""
        return PluginType.RING

    @property
    def camera_name(self) -> str:
        """Get the name of this camera."""
        return self.device_object.name

    async def retrieve_motion_events(
            self,
            from_time: datetime,
            to_time: datetime) -> List[MotionEvent]:
        """Retrieve motion events from the camera within a specified time range.

        Args:
            from_time: Start of the time range (inclusive)
            to_time: End of the time range (inclusive)

        Returns:
            List of motion events found within the time range
        """
        try:
            connection_manager = cast(
                RingConnectionManager, connection_manager_registry.get_connection_manager(PluginType.RING))
            connection_manager._ring.update_data()  # pylint: disable=protected-access
            connection_manager._ring.update_data()  # pylint: disable=protected-access

            # Get more events to ensure we don't miss any within our time window
            events = self.device_object.history(limit=5)
            LOGGER.debug("Events: %r", events)
            LOGGER.debug("Retrieved %d events from Ring history", len(events))
            LOGGER.debug(
                "Looking for new %s events between %s and %s", self.device_object.name, from_time, to_time)

            matching_events = []
            for event in events:
                # Convert event timestamp to timezone-aware datetime if it isn't already
                event_time = event.get("created_at")
                if event_time is not None:
                    event_time = event_time.astimezone(
                        ZoneInfo("America/Los_Angeles"))

                    if from_time <= event_time <= to_time:
                        motion_event = MotionEvent.from_ring_event(event)
                        matching_events.append(motion_event)

            LOGGER.debug("Found %d matching events", len(matching_events))
            return matching_events
        except Exception as e:
            LOGGER.error("Error retrieving motion videos: %s", e)
            LOGGER.exception("Full traceback:")
            return []

    async def retrieve_video_from_event_and_upload_to_s3(
            self, event: MotionEvent) -> None:
        """Retrieve the video and upload it to S3.

        Args:
            event: The motion event to retrieve video for
        """
        # Get the event ID from the event metadata
        event_id = event.event_metadata.get("event_id")
        if not event_id:
            LOGGER.error(
                "No event ID found in metadata for event %s", event.event_id)
            raise ValueError(
                f"No event ID found in metadata for event {event.event_id}")

        bucket_name = config.event_recordings_bucket
        temp_file_path = None
        h264_file_path = None
        h264_is_temp = False

        try:
            video_url = self.device_object.recording_url(event_id)
            if video_url is None:
                LOGGER.warning("No video URL found for Ring event %s", event_id)
                raise ValueError(
                    f"No video URL found for Ring event {event_id}")
            object_key = f'ring_{event_id}.mp4'
            temp_file = tempfile.NamedTemporaryFile(
                delete=False, suffix='.mp4')
            temp_file_path = temp_file.name
            try:
                # Download the video to the temp file
                with requests.get(video_url, stream=True) as response:
                    response.raise_for_status()
                    for chunk in response.iter_content(chunk_size=8192):
                with requests.get(video_url, stream=True) as response:
                    response.raise_for_status()
                    for chunk in response.iter_content(chunk_size=8192):
                        temp_file.write(chunk)
                temp_file.close()  # Close so S3 can read it

                # If file is not already H.264, convert it to H.264 for Rekognition
                if not VIDEO_CONVERTER.get_video_info(
                        temp_file_path).get('codec') == 'h264':
                    h264_file_path, h264_is_temp = VIDEO_CONVERTER.convert_for_rekognition(
                        temp_file_path)
                else:
                    h264_file_path = temp_file_path
                    h264_is_temp = False

                # Upload to S3
                S3_SERVICE.upload_file(h264_file_path, bucket_name, object_key)
                S3_SERVICE.upload_file(h264_file_path, bucket_name, object_key)
            finally:
                # Always clean up the temp files
                if temp_file_path and os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
                if h264_is_temp and h264_file_path and os.path.exists(h264_file_path):
                    os.remove(h264_file_path)
        except Exception as e:
            LOGGER.warning(
                "Error retrieving video URL for Ring event %s: %s", event_id, e)
            raise ValueError(
                f"Error retrieving video URL for Ring event {event_id}: {e}")

        # Update the event in the database with the video URL
        _, session_factory = get_database_connection()
        _, session_factory = get_database_connection()
        motion_event_repository = MotionEventRepository()

        with session_factory() as session:
            # Find the event by Ring event ID in metadata
            events = session.query(motion_event_repository.model).filter(
                motion_event_repository.model.event_metadata.op(
                    '->>')('event_id') == str(event_id)
            ).all()

            if not events or len(events) != 1:
                LOGGER.error(
                    "No database event found for Ring event ID %s", event_id)
                raise DatabaseEventNotFoundError(
                    f"No database event found for Ring event ID {event_id}")

            # Update the first matching event
            motion_event_repository.update_s3_url(
                session,
                events[0].id,
                f's3://{bucket_name}/{object_key}',
                datetime.now(ZoneInfo("America/Los_Angeles"))
            )

    async def is_healthy(self) -> bool:
        """Check if the camera is healthy and functioning properly.

        Returns:
            True if the camera is healthy and can be accessed, False otherwise
        """
        try:
            connection_manager = cast(
                RingConnectionManager,
                connection_manager_registry.get_connection_manager(PluginType.RING))
            # Access protected member to update Ring data
            connection_manager._ring.update_data()  # pylint: disable=protected-access
                RingConnectionManager,
                connection_manager_registry.get_connection_manager(PluginType.RING))
            # Access protected member to update Ring data
            connection_manager._ring.update_data()  # pylint: disable=protected-access
            device_properties = await self.get_properties()
            return device_properties.get("connection_status") == "online"
        except Exception as e:
            LOGGER.error("Error checking camera health: %s", e)
            LOGGER.exception("Full traceback:")
            return False

    async def get_properties(self) -> Dict[str, Any]:
        """Get the current properties and status of the camera.

        Returns:
            Dictionary containing camera properties and status
        """
        try:
            connection_manager = cast(
                RingConnectionManager,
                connection_manager_registry.get_connection_manager(PluginType.RING))
            # Access protected member to update Ring data
            connection_manager._ring.update_data()  # pylint: disable=protected-access
                RingConnectionManager,
                connection_manager_registry.get_connection_manager(PluginType.RING))
            # Access protected member to update Ring data
            connection_manager._ring.update_data()  # pylint: disable=protected-access

            # Access all properties in a single try block
            name = self.device_object.name
            device_id = self.device_object.id
            device_id = self.device_object.id
            motion_detection = self.device_object.motion_detection
            volume = self.device_object.volume
            battery_life = self.device_object.battery_life
            connection_status = self.device_object.connection_status
            firmware = self.device_object.firmware

            return {
                "name": name,
                "id": device_id,
                "id": device_id,
                "motion_detection": motion_detection,
                "volume": volume,
                "battery_life": battery_life,
                "connection_status": connection_status,
                "firmware": firmware
            }
        except Exception as e:
            LOGGER.error("Error getting camera properties: %s", e)
            LOGGER.exception("Full traceback:")
            return {}
