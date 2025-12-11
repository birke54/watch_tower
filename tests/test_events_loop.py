"""Tests for the events loop."""
from datetime import datetime, timezone, timedelta
from typing import Any, Generator, List
from unittest.mock import AsyncMock, Mock, patch

import pytest

from cameras.camera_base import CameraBase
from connection_managers.plugin_type import PluginType
from watch_tower.core.events_loop import handle_camera_error, poll_for_events
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
