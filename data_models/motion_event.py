from dataclasses import dataclass, field
import datetime
from typing import Any, Dict, Optional

from connection_managers.plugin_type import PluginType

try:
    from zoneinfo import ZoneInfo
except ImportError:
    # Fallback for Python < 3.9
    import pytz
    ZoneInfo = pytz.timezone

@dataclass
class MotionEvent:
    event_id: str
    camera_vendor: PluginType
    camera_name: str
    timestamp: datetime.datetime
    video_file: Optional[bytes] = None
    s3_url: Optional[str] = None
    event_metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_ring_event(cls, event: Dict[str, Any]) -> "MotionEvent":
        """Create a MotionEvent from a Ring event.

        Args:
            event: The raw event data from the Ring API containing doorbot information
                  and event details. 

        Returns:
            MotionEvent: The MotionEvent object.

        Raises:
            ValueError: If required fields (created_at, doorbot, id) are missing or invalid.
        """
        # Convert the timestamp to a datetime object in Pacific time
        timestamp = event.get("created_at")
        if timestamp is None:
            raise ValueError("created_at timestamp is missing from event")
        if not isinstance(timestamp, datetime.datetime):
            timestamp = datetime.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        
        # Convert to Pacific time
        timestamp = timestamp.astimezone(ZoneInfo("America/Los_Angeles"))
        
        doorbot = event.get("doorbot")
        if doorbot is None:
            raise ValueError("doorbot information is missing from event")
        if not isinstance(doorbot, dict):
            raise ValueError("doorbot information is not in expected format")
        
        camera_name = doorbot.get("description")
        if camera_name is None:
            raise ValueError("camera name is missing from doorbot information")
        
        # Get the Ring event ID
        ring_event_id = event.get("id")
        if ring_event_id is None:
            raise ValueError("event id is missing from event data")
        
        return cls(
            event_id=str(ring_event_id),  # Use the Ring event ID as the event_id
            camera_vendor=PluginType.RING,
            camera_name=camera_name,
            timestamp=timestamp,
            video_file=None,
            s3_url=None,
            event_metadata={"event_id": ring_event_id}  # Store the Ring event ID in metadata
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert the MotionEvent to a dictionary."""
        return {
            "event_id": self.event_id,
            "camera_name": self.camera_name,
            "timestamp": self.timestamp,
            "video_file": self.video_file,
            "s3_url": self.s3_url,
        }
