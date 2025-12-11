"""Tests for the main application entry point."""
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app import main


class TestApp:
    """Test the main application entry point."""

    @patch('app.asyncio.get_event_loop')
    @patch('app.bootstrap')
    @patch('app._run_main_application_loop')
    def test_main_success(
            self,
            mock_run_main_loop: AsyncMock,
            mock_bootstrap: AsyncMock,
            mock_get_event_loop
    ) -> None:
        """Test successful application startup."""
        # Setup
        mock_loop = Mock()
        mock_get_event_loop.return_value = mock_loop
        mock_loop.run_until_complete.side_effect = lambda coro: coro

        # Execute
        main()

        # Verify
        mock_get_event_loop.assert_called_once()
        # bootstrap and _run_main_application_loop
        assert mock_loop.run_until_complete.call_count == 2
        mock_bootstrap.assert_called_once()
        mock_run_main_loop.assert_called_once()

    @patch('app.asyncio.get_event_loop')
    @patch('app.bootstrap')
    def test_main_bootstrap_failure(
            self,
            mock_bootstrap: AsyncMock,
            mock_get_event_loop
    ) -> None:
        """Test application startup with bootstrap failure."""
        # Setup
        mock_loop = Mock()
        mock_get_event_loop.return_value = mock_loop
        mock_loop.run_until_complete.side_effect = Exception("Bootstrap failed")

        # Execute and Verify
        with pytest.raises(SystemExit):
            main()

        # Verify bootstrap was called
        mock_bootstrap.assert_called_once()
