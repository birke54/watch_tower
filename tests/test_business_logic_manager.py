import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone, timedelta
import asyncio
import os
import sys

from watch_tower.core.business_logic_manager import BusinessLogicManager, BusinessLogicError
from connection_managers.plugin_type import PluginType
from watch_tower.registry.camera_registry import REGISTRY as camera_registry


class TestBusinessLogicManager:
    """Test cases for BusinessLogicManager."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        # Clean up any existing state file
        if os.path.exists('/tmp/test_state.json'):
            os.remove('/tmp/test_state.json')

    def teardown_method(self) -> None:
        """Clean up test fixtures."""
        # Clean up any existing state file
        if os.path.exists('/tmp/test_state.json'):
            os.remove('/tmp/test_state.json')

    def test_start_rollback_on_save_state_failure(self) -> None:
        """Test that state is properly rolled back when _save_state fails during start."""
        # Create manager in an async context
        async def run_test():
            manager = BusinessLogicManager()

            # Store original state
            original_running = manager.running
            original_start_time = manager.start_time
            original_task = manager.task

            # Mock _save_state to fail
            with patch.object(manager, '_save_state', side_effect=BusinessLogicError("Save failed")):
                with patch.object(manager, '_run_business_logic_loop'):
                    try:
                        await manager.start()
                    except BusinessLogicError:
                        # Check state inside the exception handler
                        assert manager.running == original_running
                        assert manager.start_time == original_start_time
                        assert manager.task == original_task
                        raise

        with pytest.raises(BusinessLogicError, match="Save failed"):
            asyncio.run(run_test())

    def test_stop_rollback_on_save_state_failure(self) -> None:
        """Test that state is properly rolled back when _save_state fails during stop."""
        # Create manager in an async context
        async def run_test():
            manager = BusinessLogicManager()

            # Set up manager as running
            manager.running = True
            manager.start_time = datetime.now(timezone.utc)
            manager.task = Mock()
            manager.task.done.return_value = True  # Task is already done

            # Store original state
            original_running = manager.running
            original_task = manager.task

            # Mock _save_state to fail
            with patch.object(manager, '_save_state', side_effect=BusinessLogicError("Save failed")):
                try:
                    await manager.stop()
                except BusinessLogicError:
                    # Check state inside the exception handler
                    assert manager.running == original_running
                    assert manager.task == original_task
                    raise

        with pytest.raises(BusinessLogicError, match="Save failed"):
            asyncio.run(run_test())

    def test_start_successful_save_state(self) -> None:
        """Test that state is properly saved when start succeeds."""
        # Create manager in an async context
        async def run_test():
            manager = BusinessLogicManager()

            # Mock _save_state to succeed
            with patch.object(manager, '_save_state') as mock_save:
                with patch.object(manager, '_run_business_logic_loop'):
                    await manager.start()

            # Verify _save_state was called
            assert mock_save.called
            assert manager.running is True
            assert manager.start_time is not None

        asyncio.run(run_test())

    def test_stop_successful_save_state(self) -> None:
        """Test that state is properly saved when stop succeeds."""
        # Create manager in an async context
        async def run_test():
            manager = BusinessLogicManager()

            # Set up manager as running
            manager.running = True
            manager.start_time = datetime.now(timezone.utc)
            manager.task = Mock()
            manager.task.done.return_value = True  # Task is already done

            # Mock _save_state to succeed
            with patch.object(manager, '_save_state') as mock_save:
                await manager.stop()

            # Verify _save_state was called
            assert mock_save.called
            assert manager.running is False

        asyncio.run(run_test())

    @pytest.mark.asyncio
    async def test_start_updates_last_polled_for_all_cameras(self) -> None:
        """Test that start() updates last_polled for all cameras in the registry."""
        manager = BusinessLogicManager()

        # Create mock cameras
        mock_camera1 = Mock()
        mock_camera1.plugin_type = PluginType.RING
        mock_camera1.camera_name = "Camera 1"

        mock_camera2 = Mock()
        mock_camera2.plugin_type = PluginType.RING
        mock_camera2.camera_name = "Camera 2"

        # Mock camera registry methods
        original_get_all = camera_registry.get_all
        original_update_last_polled = camera_registry.update_last_polled
        
        try:
            camera_registry.get_all = Mock(return_value=[mock_camera1, mock_camera2])
            camera_registry.update_last_polled = Mock()

            with patch.object(manager, '_save_state'):
                with patch.object(manager, '_run_business_logic_loop'):
                    await manager.start()

            # Verify update_last_polled was called for each camera
            assert camera_registry.update_last_polled.call_count == 2

            # Verify it was called with correct arguments for each camera
            calls = camera_registry.update_last_polled.call_args_list
            camera_names = {call[0][1] for call in calls}  # Extract camera_name (2nd arg) from each call
            assert "Camera 1" in camera_names
            assert "Camera 2" in camera_names

            # Verify all calls used the same timezone (within a small time delta)
            timestamps = [call[0][2] for call in calls]  # Extract datetime (3rd arg) from each call
            if len(timestamps) > 1:
                time_diffs = [abs((timestamps[i] - timestamps[0]).total_seconds())
                             for i in range(1, len(timestamps))]
                # All timestamps should be within 1 second of each other
                assert all(diff < 1.0 for diff in time_diffs)
        finally:
            # Restore original methods
            camera_registry.get_all = original_get_all
            camera_registry.update_last_polled = original_update_last_polled

    @pytest.mark.asyncio
    async def test_start_updates_last_polled_with_configured_timezone(self) -> None:
        """Test that start() uses the configured timezone when updating last_polled."""
        manager = BusinessLogicManager()

        # Create mock camera
        mock_camera = Mock()
        mock_camera.plugin_type = PluginType.RING
        mock_camera.camera_name = "Test Camera"

        original_get_all = camera_registry.get_all
        original_update_last_polled = camera_registry.update_last_polled
        
        try:
            camera_registry.get_all = Mock(return_value=[mock_camera])
            camera_registry.update_last_polled = Mock()

            with patch.object(manager, '_save_state'):
                with patch.object(manager, '_run_business_logic_loop'):
                    await manager.start()

            # Verify update_last_polled was called
            assert camera_registry.update_last_polled.called

            # Verify the timestamp passed has a timezone (from get_timezone())
            call_args = camera_registry.update_last_polled.call_args[0]
            polled_time = call_args[2]  # Third argument is the datetime
            assert polled_time.tzinfo is not None, "Timestamp should have timezone info"
            # Verify it's a timezone-aware datetime
            assert isinstance(polled_time, datetime)
        finally:
            # Restore original methods
            camera_registry.get_all = original_get_all
            camera_registry.update_last_polled = original_update_last_polled

    @pytest.mark.asyncio
    async def test_restart_updates_last_polled_again(self) -> None:
        """Test that restarting the business loop (stop then start) updates last_polled again."""
        manager = BusinessLogicManager()

        # Create mock camera
        mock_camera = Mock()
        mock_camera.plugin_type = PluginType.RING
        mock_camera.camera_name = "Test Camera"

        # Track when update_last_polled is called
        update_times = []

        def capture_update_time(*args, **kwargs):
            update_times.append(datetime.now(timezone.utc))

        original_get_all = camera_registry.get_all
        original_update_last_polled = camera_registry.update_last_polled
        
        try:
            camera_registry.get_all = Mock(return_value=[mock_camera])
            camera_registry.update_last_polled = Mock(side_effect=capture_update_time)

            # First start
            with patch.object(manager, '_save_state'):
                with patch.object(manager, '_run_business_logic_loop'):
                    await manager.start()

            first_update_count = len(update_times)
            assert first_update_count == 1

            # Stop
            manager.running = False
            manager.task = Mock()
            manager.task.done.return_value = True

            with patch.object(manager, '_save_state'):
                await manager.stop()

            # Second start (restart)
            manager.running = False  # Reset for restart
            with patch.object(manager, '_save_state'):
                with patch.object(manager, '_run_business_logic_loop'):
                    await manager.start()

            # Verify update_last_polled was called again
            assert len(update_times) == 2
            assert update_times[1] > update_times[0]
        finally:
            # Restore original methods
            camera_registry.get_all = original_get_all
            camera_registry.update_last_polled = original_update_last_polled

    @pytest.mark.asyncio
    async def test_start_does_not_update_last_polled_if_already_running(self) -> None:
        """Test that start() does not update last_polled if the loop is already running."""
        manager = BusinessLogicManager()
        manager.running = True  # Set as already running

        # Create mock camera
        mock_camera = Mock()
        mock_camera.plugin_type = PluginType.RING
        mock_camera.camera_name = "Test Camera"

        original_get_all = camera_registry.get_all
        original_update_last_polled = camera_registry.update_last_polled
        
        try:
            camera_registry.get_all = Mock(return_value=[mock_camera])
            camera_registry.update_last_polled = Mock()

            await manager.start()

            # Verify update_last_polled was NOT called (early return)
            camera_registry.update_last_polled.assert_not_called()
        finally:
            # Restore original methods
            camera_registry.get_all = original_get_all
            camera_registry.update_last_polled = original_update_last_polled

    @pytest.mark.asyncio
    async def test_start_updates_last_polled_before_saving_state(self) -> None:
        """Test that last_polled is updated before state is saved, ensuring consistency."""
        manager = BusinessLogicManager()

        # Create mock camera
        mock_camera = Mock()
        mock_camera.plugin_type = PluginType.RING
        mock_camera.camera_name = "Test Camera"

        call_order = []

        def track_save_state():
            call_order.append('save_state')

        def track_update_last_polled(*args, **kwargs):
            call_order.append('update_last_polled')

        original_get_all = camera_registry.get_all
        original_update_last_polled = camera_registry.update_last_polled
        
        try:
            camera_registry.get_all = Mock(return_value=[mock_camera])
            camera_registry.update_last_polled = Mock(side_effect=track_update_last_polled)

            with patch.object(manager, '_save_state', side_effect=track_save_state):
                with patch.object(manager, '_run_business_logic_loop'):
                    await manager.start()

            # Verify update_last_polled was called before save_state
            assert 'update_last_polled' in call_order
            assert 'save_state' in call_order
            assert call_order.index('update_last_polled') < call_order.index('save_state')
        finally:
            # Restore original methods
            camera_registry.get_all = original_get_all
            camera_registry.update_last_polled = original_update_last_polled
