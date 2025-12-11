"""Tests for RingCamera class."""
from datetime import datetime, timedelta, timezone
from typing import Generator
from unittest.mock import Mock, patch, MagicMock

import pytest
from ring_doorbell import RingDoorBell

from cameras.ring_camera import RingCamera
from connection_managers.plugin_type import PluginType
from data_models.motion_event import MotionEvent


@pytest.fixture
def mock_device_object() -> Mock:
    """Create a mock Ring doorbell device object."""
    device = Mock(spec=RingDoorBell)
    # Set up properties as regular attributes
    device.name = "Test Camera"
    device.id = "test-camera-123"
    device.motion_detection = True
    device.volume = 5
    device.battery_life = 100
    device.connection_status = "online"
    device.firmware = "1.0.0"
    device.history = Mock(return_value=[])
    return device


@pytest.fixture
def mock_connection_manager() -> Mock:
    """Create a mock connection manager."""
    manager = Mock()
    manager._ring = Mock()
    manager._ring.update_data = Mock()
    return manager


@pytest.fixture
def mock_registry(mock_connection_manager: Mock) -> Generator[Mock, None, None]:
    """Mock the connection manager registry."""
    with patch('cameras.ring_camera.connection_manager_registry') as mock:
        mock.get_connection_manager.return_value = mock_connection_manager
        yield mock


@pytest.fixture
def ring_camera(mock_device_object: Mock) -> RingCamera:
    """Create a RingCamera instance with mocked dependencies."""
    return RingCamera(mock_device_object)


class TestRingCamera:
    """Test cases for RingCamera."""

    def test_init(self, mock_device_object: Mock) -> None:
        """Test camera initialization."""
        camera = RingCamera(mock_device_object)
        assert camera.device_object == mock_device_object
        assert camera.plugin_type == PluginType.RING
        assert not hasattr(camera, 'camera_vendor')

    @pytest.mark.asyncio
    async def test_retrieve_motion_events_success(
            self, ring_camera: RingCamera, mock_device_object: Mock, mock_registry: Mock
    ) -> None:
        """Test successful retrieval of motion videos."""
        # Setup
        from_time = datetime.now(timezone.utc) - timedelta(hours=1)
        to_time = datetime.now(timezone.utc)

        # Create mock events with raw data structure
        event1 = {
            "id": "1",
            "created_at": from_time + timedelta(minutes=30),
            "kind": "motion",
            "doorbot": {
                "description": "Front Door"
            }
        }
        event2 = {
            "id": "2",
            "created_at": to_time - timedelta(minutes=30),
            "kind": "motion",
            "doorbot": {
                "description": "Front Door"
            }
        }
        event3 = {
            "id": "3",
            "created_at": to_time + timedelta(minutes=30),  # Outside time range
            "kind": "motion",
            "doorbot": {
                "description": "Front Door"
            }
        }

        mock_device_object.history.return_value = [event1, event2, event3]

        # Execute
        result = await ring_camera.retrieve_motion_events(from_time, to_time)

        # Verify
        assert len(result) == 2
        assert all(isinstance(event, MotionEvent) for event in result)
        assert result[0].timestamp == from_time + timedelta(minutes=30)
        assert result[1].timestamp == to_time - timedelta(minutes=30)
        mock_registry.get_connection_manager.assert_called_once_with(PluginType.RING)
        mock_registry.get_connection_manager.return_value._ring.update_data.assert_called_once()

    @pytest.mark.asyncio
    async def test_retrieve_motion_events_error(
            self, ring_camera: RingCamera, mock_device_object: Mock, mock_registry: Mock
    ) -> None:
        """Test error handling in motion video retrieval."""
        # Setup
        mock_device_object.history.side_effect = Exception("Test error")

        # Execute
        result = await ring_camera.retrieve_motion_events(
            datetime.now(timezone.utc),
            datetime.now(timezone.utc) + timedelta(hours=1)
        )

        # Verify
        assert result == []

    @pytest.mark.asyncio
    async def test_is_healthy_online(
            self, ring_camera: RingCamera, mock_device_object: Mock, mock_registry: Mock
    ) -> None:
        """Test health check when camera is online."""
        # Setup
        mock_device_object.connection_status = "online"

        # Execute
        result = await ring_camera.is_healthy()

        # Verify
        assert result is True
        # Don't verify get_connection_manager calls since it's called in both
        # is_healthy and get_properties

    @pytest.mark.asyncio
    async def test_is_healthy_offline(
            self, ring_camera: RingCamera, mock_device_object: Mock, mock_registry: Mock
    ) -> None:
        """Test health check when camera is offline."""
        # Setup
        mock_device_object.connection_status = "offline"

        # Execute
        result = await ring_camera.is_healthy()

        # Verify
        assert result is False

    @pytest.mark.asyncio
    async def test_is_healthy_error(
            self, ring_camera: RingCamera, mock_device_object: Mock, mock_registry: Mock
    ) -> None:
        """Test health check error handling."""
        # Setup
        mock_device_object.connection_status = Mock(side_effect=Exception("Test error"))

        # Execute
        result = await ring_camera.is_healthy()

        # Verify
        assert result is False

    @pytest.mark.asyncio
    async def test_get_properties_success(
            self, ring_camera: RingCamera, mock_device_object: Mock, mock_registry: Mock
    ) -> None:
        """Test successful retrieval of camera properties."""
        # Execute
        result = await ring_camera.get_properties()

        # Verify
        expected_properties = {
            "name": "Test Camera",
            "id": "test-camera-123",
            "motion_detection": True,
            "volume": 5,
            "battery_life": 100,
            "connection_status": "online",
            "firmware": "1.0.0"
        }
        assert result == expected_properties
        mock_registry.get_connection_manager.assert_called_once_with(PluginType.RING)
        mock_registry.get_connection_manager.return_value._ring.update_data.assert_called_once()

    @pytest.mark.asyncio
    async def test_retrieve_video_from_event_and_upload_to_s3_no_event_id(
            self, ring_camera: RingCamera
    ) -> None:
        """Test video retrieval when event has no event_id in metadata."""
        # Setup - create event without event_id in metadata
        event = MotionEvent(
            event_id="test-event-123",
            camera_vendor="ring",
            camera_name="Test Camera",
            timestamp=datetime.now(timezone.utc),
            event_metadata={}  # Empty metadata, no event_id
        )

        # Execute - should raise ValueError for missing event_id
        with pytest.raises(ValueError, match="No event ID found in metadata for event test-event-123"):
            await ring_camera.retrieve_video_from_event_and_upload_to_s3(event)

    @pytest.mark.asyncio
    async def test_retrieve_video_from_event_and_upload_to_s3_with_event_id(
            self, ring_camera: RingCamera, mock_device_object: Mock
    ) -> None:
        """Test video retrieval when event has valid event_id."""
        # Setup
        event = MotionEvent(
            event_id="test-event-123",
            camera_vendor="ring",
            camera_name="Test Camera",
            timestamp=datetime.now(timezone.utc),
            event_metadata={"event_id": "ring-event-456"}
        )

        # Mock the recording_url method
        mock_device_object.recording_url.return_value = "https://example.com/video.mp4"

        # Mock the config
        with patch('cameras.ring_camera.config') as mock_config:
            mock_config.event_recordings_bucket = 'test-bucket'
            # Mock the S3 service - patch where it's imported, not where it's defined
            with patch('cameras.ring_camera.S3_SERVICE') as mock_s3_service:
                # Mock requests.get to return a successful response
                with patch('cameras.ring_camera.requests.get') as mock_get:
                    mock_response = Mock()
                    mock_response.raise_for_status.return_value = None
                    mock_response.iter_content.return_value = [b"fake video data"]
                    mock_get.return_value.__enter__.return_value = mock_response

                    # Mock video converter
                    with patch('cameras.ring_camera.VIDEO_CONVERTER') as mock_converter:
                        mock_converter.get_video_info.return_value = {'codec': 'h264'}
                        # Mock the database session and repository
                        with patch('cameras.ring_camera.get_database_connection') as mock_get_db_conn, \
                                patch('cameras.ring_camera.MotionEventRepository') as mock_repo_class:
                            mock_engine = Mock()
                            mock_session_factory = MagicMock()
                            mock_session = Mock()
                            mock_get_db_conn.return_value = (
                                mock_engine, mock_session_factory)
                            mock_session_factory.return_value.__enter__.return_value = mock_session
                            mock_repo = Mock()
                            mock_repo_class.return_value = mock_repo
                            # Mock the query to return a matching event
                            mock_event_model = Mock()
                            mock_event_model.id = 123
                            mock_session.query.return_value.filter.return_value.all.return_value = [
                                mock_event_model]
                            # Mock update_s3_url to do nothing
                            mock_repo.update_s3_url.return_value = None
                            # Execute
                            await ring_camera.retrieve_video_from_event_and_upload_to_s3(event)
                            # Verify
                            mock_device_object.recording_url.assert_called_once_with(
                                "ring-event-456")
                            mock_s3_service.upload_file.assert_called_once()
                            mock_repo.update_s3_url.assert_called_once()

    @pytest.mark.asyncio
    async def test_retrieve_video_from_event_and_upload_to_s3_no_video_url(
            self, ring_camera: RingCamera, mock_device_object: Mock
    ) -> None:
        """Test video retrieval when no video URL is available."""
        # Setup
        event = MotionEvent(
            event_id="test-event-123",
            camera_vendor="ring",
            camera_name="Test Camera",
            timestamp=datetime.now(timezone.utc),
            event_metadata={"event_id": "ring-event-456"}
        )

        # Mock the recording_url method to return None
        mock_device_object.recording_url.return_value = None

        # Execute - should raise ValueError for missing video URL
        with pytest.raises(ValueError, match="No video URL found for Ring event ring-event-456"):
            await ring_camera.retrieve_video_from_event_and_upload_to_s3(event)

        # Verify
        mock_device_object.recording_url.assert_called_once_with("ring-event-456")
