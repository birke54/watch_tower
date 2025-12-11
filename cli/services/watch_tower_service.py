"""
Watch Tower Service

This module contains the WatchTowerService class that handles business logic
operations and external API interactions for the CLI.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict

from watch_tower.config import config
from utils.errors import (
    DependencyError,
    ManagementAPIError,
)

from cli.utils.errors import create_error_status_response

LOGGER = logging.getLogger(__name__)

# Constants
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8080
DEFAULT_TIMEOUT = 10
HEALTH_CHECK_TIMEOUT = 5


class WatchTowerService:
    """Service layer for Watch Tower CLI operations."""

    def __init__(self):
        self.state_file = config.cli.state_file_path

    def get_status(self) -> Dict[str, Any]:
        """Get the current status of the business logic loop."""
        try:
            health_data = asyncio.run(self.check_management_api())

            # Try new field name first, fall back to old for backward compatibility
            if 'business_logic' in health_data:
                business_logic = health_data['business_logic']
                return {
                    "running": business_logic.get(
                        'running',
                        False),
                    "start_time": business_logic.get('start_time'),
                    "uptime": business_logic.get('uptime'),
                    "business_logic_completed": not business_logic.get(
                        'running',
                        False),
                    "business_logic_cancelled": False}
            elif 'event_loop' in health_data:
                event_loop = health_data['event_loop']
                return {
                    "running": event_loop.get('running', False),
                    "start_time": event_loop.get('start_time'),
                    "uptime": event_loop.get('uptime'),
                    "business_logic_completed": not event_loop.get('running', False),
                    "business_logic_cancelled": False
                }
            return create_error_status_response(
                "No business logic status found in health data")

        except DependencyError as e:
            LOGGER.error("Dependency error: %s", e)
            return create_error_status_response(str(e))
        except ManagementAPIError as e:
            LOGGER.error("Management API error: %s", e)
            return create_error_status_response(str(e))
        except Exception as e:
            LOGGER.error("Failed to get business logic loop status: %s", e)
            return create_error_status_response(str(e))

    async def start_business_logic_api(
            self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> Dict[str, Any]:
        """Start the business logic loop via HTTP API."""
        try:
            import aiohttp  # pylint: disable=import-outside-toplevel
        except ImportError:
            raise DependencyError("aiohttp", "pip install aiohttp")

        url = f"http://{host}:{port}/start"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, timeout=DEFAULT_TIMEOUT) as response:
                    if response.status == 200:
                        return await response.json()
                    raise ManagementAPIError(
                        f"Start API returned status {response.status}",
                        status_code=response.status
                    )
        except ManagementAPIError:
            raise
        except Exception as e:
            raise ManagementAPIError(
                f"Failed to connect to start API: {e}", original_error=e)

    async def stop_business_logic_api(
            self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> Dict[str, Any]:
        """Stop the business logic loop via HTTP API."""
        try:
            import aiohttp  # pylint: disable=import-outside-toplevel
        except ImportError:
            raise DependencyError("aiohttp", "pip install aiohttp")

        url = f"http://{host}:{port}/stop"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, timeout=DEFAULT_TIMEOUT) as response:
                    if response.status == 200:
                        return await response.json()
                    raise ManagementAPIError(
                        f"Stop API returned status {response.status}",
                        status_code=response.status
                    )
        except ManagementAPIError:
            raise
        except Exception as e:
            raise ManagementAPIError(
                f"Failed to connect to stop API: {e}", original_error=e)

    def start_business_logic(self) -> None:
        """Start the business logic loop by updating the state file."""
        state = {
            "running": True,
            "start_time": datetime.now(timezone.utc).isoformat(),
            "business_logic_completed": False,
            "business_logic_cancelled": False,
            "last_updated": datetime.now(timezone.utc).isoformat()
        }

        with open(self.state_file, "w") as file_handle:
            json.dump(state, file_handle)

        LOGGER.info(
            "Business logic loop start requested - main process will pick this up")

    async def check_management_api(
            self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> Dict[str, Any]:
        """Check the management API endpoint."""
        try:
            import aiohttp  # pylint: disable=import-outside-toplevel
        except ImportError:
            raise DependencyError("aiohttp", "pip install aiohttp")

        url = f"http://{host}:{port}/health"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=HEALTH_CHECK_TIMEOUT) as response:
                    if response.status == 200:
                        return await response.json()
                    raise ManagementAPIError(
                        f"Management API returned status {response.status}",
                        status_code=response.status
                    )
        except ManagementAPIError:
            raise
        except Exception as e:
            raise ManagementAPIError(
                f"Failed to connect to management API: {e}", original_error=e)

    @staticmethod
    def validate_config() -> None:
        """Validate the current configuration."""
        config.validate()
