from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, Any, List
from connection_managers.plugin_type import PluginType
from data_models.motion_event import MotionEvent
from utils.logging_config import get_logger

logger = get_logger(__name__)

class CameraBase(ABC):
    """Base interface for all camera types."""
    
    def __init__(self, motion_poll_interval: int = 60) -> None:
        """Initialize the camera interface.
        
        Args:
            motion_poll_interval: How often to poll for motion events in seconds
        """
        self.motion_poll_interval = motion_poll_interval
        self.last_motion_video_retrieval: datetime = datetime.now(timezone.utc)
    
    @property
    @abstractmethod
    def plugin_type(self) -> PluginType:
        """Get the plugin type for this camera."""
    
    @property
    @abstractmethod
    def camera_name(self) -> str:
        """Get the name of this camera."""
    
    @abstractmethod
    async def retrieve_motion_events(self, from_time: datetime, to_time: datetime) -> List[MotionEvent]:
        """Retrieve motion events from the camera within a specified time range.
        
        Args:
            from_time: Start of the time range (inclusive)
            to_time: End of the time range (inclusive)
            
        Returns:
            List of motion events found within the time range
        """
    
    @abstractmethod
    async def retrieve_video_from_event_and_upload_to_s3(self, event: MotionEvent) -> None:
        """Retrieve the video and upload it to S3."""

    @abstractmethod
    async def is_healthy(self) -> bool:
        """Check if the camera is healthy and functioning properly.
        
        Returns:
            True if the camera is healthy and can be accessed, False otherwise
        """
    
    @abstractmethod
    async def get_properties(self) -> Dict[str, Any]:
        """Get the current properties and status of the camera.
        
        Returns:
            Dictionary containing camera properties and status
        """
