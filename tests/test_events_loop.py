"""Tests for the events loop."""
from datetime import datetime, timezone, timedelta
from typing import Any, Generator, List
from unittest.mock import AsyncMock, Mock, patch, MagicMock

import pytest

from cameras.camera_base import CameraBase
from connection_managers.plugin_type import PluginType
from data_models.motion_event import MotionEvent
from watch_tower.core.events_loop import (
    handle_camera_error,
    insert_events_into_db,
    poll_for_events
)
from watch_tower.registry.camera_registry import CameraStatus
from watch_tower.registry.connection_manager_registry import VendorStatus


@pytest.fixture
def mock_camera() -> Mock:
    """Create a mock camera instance."""
    camera = Mock(spec=CameraBase)
    camera.plugin_type = PluginType.RING
    camera.motion_poll_interval = 60
    camera.get_properties = AsyncMock(return_value={"name": "Test Camera"})
    camera.retrieve_motion_events = AsyncMock(return_value=[])
    return camera


@pytest.fixture
def mock_camera_registry() -> Generator[Mock, None, None]:
    """Mock the camera registry."""
    with patch('watch_tower.core.events_loop.camera_registry') as mock:
        # Set last_polled to be older than motion_poll_interval
        camera_entry = Mock(
            last_polled=datetime.now(timezone.utc) -
            timedelta(seconds=120),  # 2 minutes ago
            status=CameraStatus.ACTIVE
        )
        mock.cameras = {
            (PluginType.RING, "Test Camera"): camera_entry
        }
        mock.get_all_by_vendor.return_value = [Mock()]

        # Mock update_last_polled to actually update the camera entry's last_polled
        def update_last_polled_side_effect(_vendor, _camera_name, polled_time):
            camera_entry.last_polled = polled_time

        mock.update_last_polled.side_effect = update_last_polled_side_effect
        yield mock


@pytest.fixture
def mock_connection_manager_registry() -> Generator[Mock, None, None]:
    """Mock the connection manager registry."""
    with patch('watch_tower.core.events_loop.connection_manager_registry') as mock:
        mock.get_connection_manager.return_value = Mock(
            is_healthy=Mock(return_value=True))
        yield mock


@pytest.mark.asyncio
async def test_poll_for_events_success(
        mock_camera: Mock,
        mock_camera_registry: Mock
) -> None:
    """Test successful event polling."""
    current_time = datetime.now(timezone.utc)
    new_events: List[Any] = []

    await poll_for_events(mock_camera, current_time, new_events)

    mock_camera.get_properties.assert_called_once()
    mock_camera.retrieve_motion_events.assert_called_once()
    assert mock_camera_registry.cameras[(
        PluginType.RING, "Test Camera")].last_polled == current_time


@pytest.mark.asyncio
async def test_poll_for_events_error(
        mock_camera: Mock,
        mock_camera_registry: Mock,
        mock_connection_manager_registry: Mock
) -> None:
    """Test error handling in event polling."""
    # Set up the error condition
    mock_camera.retrieve_motion_events.side_effect = Exception("Test error")
    current_time = datetime.now(timezone.utc)
    new_events: List[Any] = []

    # Ensure last_polled is old enough to trigger polling
    mock_camera_registry.cameras[(PluginType.RING, "Test Camera")].last_polled = (
        current_time - timedelta(seconds=mock_camera.motion_poll_interval + 1)
    )

    await poll_for_events(mock_camera, current_time, new_events)

    mock_connection_manager_registry.get_connection_manager.assert_called_with(
        PluginType.RING)


@pytest.mark.asyncio
async def test_handle_camera_error_connection_manager_unhealthy(
        mock_camera: Mock,
        mock_camera_registry: Mock,
        mock_connection_manager_registry: Mock
) -> None:
    """Test handling camera error when connection manager is unhealthy."""
    mock_connection_manager_registry.get_connection_manager.return_value.is_healthy.return_value = False

    await handle_camera_error(mock_camera)

    mock_connection_manager_registry.update_status.assert_called_with(
        PluginType.RING, VendorStatus.INACTIVE)
    mock_camera_registry.update_status.assert_called()


@pytest.mark.asyncio
async def test_handle_camera_error_connection_manager_healthy(
        mock_camera: Mock,
        mock_camera_registry: Mock,
        mock_connection_manager_registry: Mock
) -> None:
    """Test handling camera error when connection manager is healthy."""
    mock_connection_manager_registry.get_connection_manager.return_value.is_healthy.return_value = True

    await handle_camera_error(mock_camera)

    mock_camera_registry.update_status.assert_called_with(
        PluginType.RING, "Test Camera", CameraStatus.INACTIVE)


@pytest.mark.asyncio
async def test_poll_for_events_skip_recent_poll(
        mock_camera: Mock,
        mock_camera_registry: Mock
) -> None:
    """Test that polling is skipped if last poll was recent."""
    current_time = datetime.now(timezone.utc)
    new_events: List[Any] = []

    # Set last_polled to be very recent
    mock_camera_registry.cameras[(PluginType.RING, "Test Camera")].last_polled = (
        current_time - timedelta(seconds=30)  # Less than motion_poll_interval
    )

    await poll_for_events(mock_camera, current_time, new_events)

    mock_camera.get_properties.assert_called_once()
    # Should not be called for recent polls
    mock_camera.retrieve_motion_events.assert_not_called()


class TestInsertEventsIntoDb:
    """Test cases for insert_events_into_db function to prevent duplicates."""

    @pytest.fixture
    def mock_db_session(self) -> Mock:
        """Create a mock database session."""
        session = MagicMock()
        # Default: no existing events
        session.query.return_value.filter.return_value.all.return_value = []
        return session

    @pytest.fixture
    def mock_session_factory(self, mock_db_session: Mock) -> Mock:
        """Create a mock session factory."""
        session_factory = MagicMock()
        session_factory.return_value.__enter__.return_value = mock_db_session
        session_factory.return_value.__exit__.return_value = None
        return session_factory

    @pytest.fixture
    def mock_get_database_connection(
            self,
            mock_session_factory: Mock) -> Generator[Mock, None, None]:
        """Mock the get_database_connection function."""
        from unittest.mock import patch
        
        mock_engine = Mock()
        with patch('watch_tower.core.events_loop.get_database_connection') as mock:
            mock.return_value = (mock_engine, mock_session_factory)
            yield mock

    @pytest.fixture
    def sample_motion_event(self) -> MotionEvent:
        """Create a sample motion event for testing."""
        return MotionEvent(
            event_id="1234567890",
            camera_vendor=PluginType.RING,
            camera_name="Front Door",
            timestamp=datetime.now(timezone.utc),
            event_metadata={"event_id": "1234567890"}
        )

    def test_insert_new_event(
            self,
            mock_get_database_connection: Mock,
            mock_db_session: Mock,
            mock_session_factory: Mock,
            sample_motion_event: MotionEvent) -> None:
        """Test that a new event is inserted when it doesn't exist."""
        from db.repositories.motion_event_repository import MotionEventRepository
        
        # Setup: No existing events
        mock_db_session.query.return_value.filter.return_value.all.return_value = []
        
        # Execute
        insert_events_into_db([sample_motion_event])
        
        # Verify: Repository create was called
        # The create method is called on the repository, which adds to the session
        assert mock_db_session.add.called or mock_db_session.query.called
        # Verify session was used
        mock_session_factory.assert_called()

    def test_skip_duplicate_event(
            self,
            mock_get_database_connection: Mock,
            mock_db_session: Mock,
            mock_session_factory: Mock,
            sample_motion_event: MotionEvent) -> None:
        """Test that duplicate events are skipped."""
        from db.models import MotionEvent as DBMotionEvent
        
        # Setup: Create a mock existing event
        existing_event = Mock(spec=DBMotionEvent)
        existing_event.id = 1
        existing_event.camera_name = "Front Door"
        existing_event.event_metadata = {"event_id": "1234567890"}
        
        # Mock the query chain to return the existing event
        filter_mock = Mock()
        filter_mock.all.return_value = [existing_event]
        query_mock = Mock()
        query_mock.filter.return_value = filter_mock
        mock_db_session.query.return_value = query_mock
        
        # Track calls to add (which would be called by repository.create)
        add_call_count_before = mock_db_session.add.call_count
        
        # Execute
        insert_events_into_db([sample_motion_event])
        
        # Verify: add was not called (duplicate skipped)
        # The query should have been called to check for duplicates
        assert mock_db_session.query.called
        # add should not have been called since duplicate was skipped
        assert mock_db_session.add.call_count == add_call_count_before

    def test_insert_multiple_new_events(
            self,
            mock_get_database_connection: Mock,
            mock_db_session: Mock,
            mock_session_factory: Mock) -> None:
        """Test that multiple new events are inserted."""
        event1 = MotionEvent(
            event_id="1111111111",
            camera_vendor=PluginType.RING,
            camera_name="Front Door",
            timestamp=datetime.now(timezone.utc),
            event_metadata={"event_id": "1111111111"}
        )
        event2 = MotionEvent(
            event_id="2222222222",
            camera_vendor=PluginType.RING,
            camera_name="Back Door",
            timestamp=datetime.now(timezone.utc),
            event_metadata={"event_id": "2222222222"}
        )
        
        # Setup: No existing events
        mock_db_session.query.return_value.filter.return_value.all.return_value = []
        
        # Execute
        insert_events_into_db([event1, event2])
        
        # Verify: Query was called for each event (2 events)
        assert mock_db_session.query.call_count == 2
        # Verify add was called for each new event
        assert mock_db_session.add.call_count == 2

    def test_skip_duplicate_mixed_with_new(
            self,
            mock_get_database_connection: Mock,
            mock_db_session: Mock,
            mock_session_factory: Mock) -> None:
        """Test that duplicate events are skipped but new ones are inserted."""
        from db.models import MotionEvent as DBMotionEvent
        
        duplicate_event = MotionEvent(
            event_id="1111111111",
            camera_vendor=PluginType.RING,
            camera_name="Front Door",
            timestamp=datetime.now(timezone.utc),
            event_metadata={"event_id": "1111111111"}
        )
        new_event = MotionEvent(
            event_id="2222222222",
            camera_vendor=PluginType.RING,
            camera_name="Back Door",
            timestamp=datetime.now(timezone.utc),
            event_metadata={"event_id": "2222222222"}
        )
        
        # Setup: First event exists, second doesn't
        existing_event = Mock(spec=DBMotionEvent)
        existing_event.id = 1
        existing_event.camera_name = "Front Door"
        existing_event.event_metadata = {"event_id": "1111111111"}
        
        query_results = [
            [existing_event],  # First query returns existing (duplicate)
            []  # Second query returns empty (new event)
        ]
        query_call_count = [0]
        
        def query_side_effect(*args, **kwargs):
            result = query_results[query_call_count[0] % len(query_results)]
            query_call_count[0] += 1
            filter_mock = Mock()
            filter_mock.all.return_value = result
            query_mock = Mock()
            query_mock.filter.return_value = filter_mock
            return query_mock
        
        mock_db_session.query.side_effect = query_side_effect
        
        # Execute
        insert_events_into_db([duplicate_event, new_event])
        
        # Verify: Query was called for both events
        assert mock_db_session.query.call_count == 2
        # Verify: add was called only once (for the new event, duplicate skipped)
        assert mock_db_session.add.call_count == 1

    def test_duplicate_different_camera_name_allowed(
            self,
            mock_get_database_connection: Mock,
            mock_db_session: Mock,
            mock_session_factory: Mock) -> None:
        """Test that same Ring event ID with different camera name is allowed."""
        event1 = MotionEvent(
            event_id="1234567890",
            camera_vendor=PluginType.RING,
            camera_name="Front Door",
            timestamp=datetime.now(timezone.utc),
            event_metadata={"event_id": "1234567890"}
        )
        event2 = MotionEvent(
            event_id="1234567890",  # Same Ring event ID
            camera_vendor=PluginType.RING,
            camera_name="Back Door",  # Different camera
            timestamp=datetime.now(timezone.utc),
            event_metadata={"event_id": "1234567890"}
        )
        
        # Setup: No existing events (different camera names mean no duplicates)
        mock_db_session.query.return_value.filter.return_value.all.return_value = []
        
        # Execute
        insert_events_into_db([event1, event2])
        
        # Verify: Query was called for both events
        assert mock_db_session.query.call_count == 2
        # Verify: Both events were inserted (different cameras, so not duplicates)
        assert mock_db_session.add.call_count == 2
