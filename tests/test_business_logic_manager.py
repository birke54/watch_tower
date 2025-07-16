import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timezone
import asyncio
import os

from watch_tower.core.business_logic_manager import BusinessLogicManager, BusinessLogicError


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