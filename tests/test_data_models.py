import pytest
from datetime import datetime, timezone

from data_models.motion_event import MotionEvent
from connection_managers.plugin_type import PluginType


class TestMotionEvent:
    """Test the MotionEvent data model."""

    def test_motion_event_creation(self) -> None:
        """Test creating a MotionEvent with all required fields."""
        # Setup
        event_id = "test_event_123"
        camera_vendor = PluginType.RING
        camera_name = "Front Door"
        timestamp = datetime.now(timezone.utc)
        s3_url = "https://test-bucket.s3.amazonaws.com/video.mp4"
        event_metadata = {"test": "data"}

        # Execute
        event = MotionEvent(
            event_id=event_id,
            camera_vendor=camera_vendor,
            camera_name=camera_name,
            timestamp=timestamp,
            s3_url=s3_url,
            event_metadata=event_metadata
        )

        # Verify
        assert event.event_id == event_id
        assert event.camera_vendor == camera_vendor
        assert event.camera_name == camera_name
        assert event.timestamp == timestamp
        assert event.s3_url == s3_url
        assert event.event_metadata == event_metadata

    def test_motion_event_optional_s3_url(self) -> None:
        """Test creating a MotionEvent with optional s3_url."""
        # Setup
        event_id = "test_event_123"
        camera_vendor = PluginType.RING
        camera_name = "Front Door"
        timestamp = datetime.now(timezone.utc)

        # Execute
        event = MotionEvent(
            event_id=event_id,
            camera_vendor=camera_vendor,
            camera_name=camera_name,
            timestamp=timestamp,
            s3_url=None,
            event_metadata={}
        )

        # Verify
        assert event.s3_url is None

    def test_motion_event_default_metadata(self) -> None:
        """Test creating a MotionEvent with default metadata."""
        # Setup
        event_id = "test_event_123"
        camera_vendor = PluginType.RING
        camera_name = "Front Door"
        timestamp = datetime.now(timezone.utc)

        # Execute
        event = MotionEvent(
            event_id=event_id,
            camera_vendor=camera_vendor,
            camera_name=camera_name,
            timestamp=timestamp,
            s3_url="https://test.com/video.mp4"
        )

        # Verify
        assert event.event_metadata == {}

    def test_from_ring_event_success(self) -> None:
        """Test creating MotionEvent from Ring event data."""
        # Setup
        ring_event = {
            "id": 123456789,
            "created_at": datetime.now(timezone.utc),
            "doorbot": {
                "description": "Front Door Camera"
            }
        }

        # Execute
        event = MotionEvent.from_ring_event(ring_event)

        # Verify
        assert event.event_id == "123456789"
        assert event.camera_vendor == PluginType.RING
        assert event.camera_name == "Front Door Camera"
        assert event.timestamp == ring_event["created_at"]
        assert event.s3_url is None
        assert event.event_metadata == {"event_id": 123456789}

    def test_from_ring_event_missing_created_at(self) -> None:
        """Test creating MotionEvent from Ring event with missing created_at."""
        # Setup
        ring_event = {
            "id": 123456789,
            "doorbot": {
                "description": "Front Door Camera"
            }
        }

        # Execute and Verify
        with pytest.raises(ValueError, match="created_at timestamp is missing"):
            MotionEvent.from_ring_event(ring_event)

    def test_from_ring_event_missing_doorbot(self) -> None:
        """Test creating MotionEvent from Ring event with missing doorbot."""
        # Setup
        ring_event = {
            "id": 123456789,
            "created_at": datetime.now(timezone.utc)
        }

        # Execute and Verify
        with pytest.raises(ValueError, match="doorbot information is missing"):
            MotionEvent.from_ring_event(ring_event)

    def test_from_ring_event_invalid_doorbot_format(self) -> None:
        """Test creating MotionEvent from Ring event with invalid doorbot format."""
        # Setup
        ring_event = {
            "id": 123456789,
            "created_at": datetime.now(timezone.utc),
            "doorbot": "invalid_format"
        }

        # Execute and Verify
        with pytest.raises(ValueError, match="doorbot information is not in expected format"):
            MotionEvent.from_ring_event(ring_event)

    def test_from_ring_event_missing_description(self) -> None:
        """Test creating MotionEvent from Ring event with missing description."""
        # Setup
        ring_event = {
            "id": 123456789,
            "created_at": datetime.now(timezone.utc),
            "doorbot": {}
        }

        # Execute and Verify
        with pytest.raises(ValueError, match="camera name is missing from doorbot information"):
            MotionEvent.from_ring_event(ring_event)

    def test_from_ring_event_missing_id(self) -> None:
        """Test creating MotionEvent from Ring event with missing id."""
        # Setup
        ring_event = {
            "created_at": datetime.now(timezone.utc),
            "doorbot": {
                "description": "Front Door Camera"
            }
        }

        # Execute and Verify
        with pytest.raises(ValueError, match="event id is missing"):
            MotionEvent.from_ring_event(ring_event)

    def test_motion_event_equality(self) -> None:
        """Test MotionEvent equality comparison."""
        # Setup
        timestamp = datetime.now(timezone.utc)
        event1 = MotionEvent(
            event_id="test_123",
            camera_vendor=PluginType.RING,
            camera_name="Front Door",
            timestamp=timestamp,
            s3_url="https://test.com/video.mp4",
            event_metadata={"test": "data"}
        )

        event2 = MotionEvent(
            event_id="test_123",
            camera_vendor=PluginType.RING,
            camera_name="Front Door",
            timestamp=timestamp,
            s3_url="https://test.com/video.mp4",
            event_metadata={"test": "data"}
        )

        event3 = MotionEvent(
            event_id="different_123",
            camera_vendor=PluginType.RING,
            camera_name="Front Door",
            timestamp=timestamp,
            s3_url="https://test.com/video.mp4",
            event_metadata={"test": "data"}
        )

        # Verify
        assert event1 == event2
        assert event1 != event3
        assert event2 != event3

    def test_motion_event_repr(self) -> None:
        """Test MotionEvent string representation."""
        # Setup
        event = MotionEvent(
            event_id="test_123",
            camera_vendor=PluginType.RING,
            camera_name="Front Door",
            timestamp=datetime.now(timezone.utc),
            s3_url="https://test.com/video.mp4",
            event_metadata={"test": "data"}
        )

        # Execute
        repr_str = repr(event)

        # Verify
        assert "MotionEvent" in repr_str
        assert "test_123" in repr_str
        assert "Front Door" in repr_str