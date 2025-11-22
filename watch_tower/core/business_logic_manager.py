"""
Business Logic Manager

This module manages the business logic loop for the Watch Tower application,
providing start/stop functionality and state management.
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from data_models.motion_event import MotionEvent
from watch_tower.core.events_loop import (
    insert_events_into_db,
    poll_for_events,
    start_facial_recognition_tasks,
    start_video_retrieval_tasks,
)
from watch_tower.exceptions import BusinessLogicError
from watch_tower.registry.camera_registry import REGISTRY as camera_registry

LOGGER = logging.getLogger(__name__)

# State file for cross-process access
STATE_FILE = "/tmp/watch_tower_business_logic_state.json"


@dataclass
class BusinessLogicState:
    """Data class that stores business loop state information"""
    running: bool
    start_time: Optional[datetime]
    task: Optional[asyncio.Task]
    shutdown_event: bool


class BusinessLogicManager:
    """Manages the business logic loop lifecycle with file-based state persistence."""

    def __init__(self):
        self.task: Optional[asyncio.Task] = None
        self.running = False
        self.shutdown_event = asyncio.Event()
        self.start_time: Optional[datetime] = None


    def _save_state(self) -> None:
        """Save the current state to a file for cross-process access."""
        state = {
            "running": self.running,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "business_logic_completed": self.task.done() if self.task else None,
            "business_logic_cancelled": self.task.cancelled() if self.task else None,
            "last_updated": datetime.now(
                timezone.utc).isoformat()}
        try:
            with open(STATE_FILE, 'w') as state_file:
                json.dump(state, state_file)
        except (OSError, IOError) as e:
            LOGGER.error("Failed to save state file: %s", e)
            raise BusinessLogicError(f"Failed to save state file: {str(e)}")
        except Exception as e:
            LOGGER.error("Unexpected error saving state: %s", e)
            raise BusinessLogicError(
                f"Unexpected error saving state: {str(e)}")


    @staticmethod
    def _load_state() -> Dict[str, Any]:
        """Load the current state from file."""
        try:
            with open(STATE_FILE, 'r') as state_file:
                return json.load(state_file)
        except (OSError, IOError) as e:
            LOGGER.error("Failed to load state file: %s", e)
            raise
        except json.JSONDecodeError as e:
            LOGGER.error("Failed to parse state file JSON: %s", e)
            raise
        except Exception as e:
            LOGGER.error("Unexpected error loading state: %s", e)
            raise


    def _capture_state(self) -> BusinessLogicState:
        """Capture the current state of the business logic loop."""
        return BusinessLogicState(
            running=self.running,
            start_time=self.start_time,
            task=self.task,
            shutdown_event=self.shutdown_event.is_set()
        )


    def _restore_state(self, state: BusinessLogicState) -> None:
        """Restore the business logic loop to a previous state."""
        self.running = state.running
        self.start_time = state.start_time
        self.task = state.task
        if state.shutdown_event:
            self.shutdown_event.set()
        else:
            self.shutdown_event.clear()

    async def _wait_for_task_completion(self, timeout: float) -> None:
        """Wait for the task to complete gracefully, with timeout and cancellation handling.

        Args:
            timeout: Maximum time to wait before cancelling the task
        """
        task_status = f"done={self.task.done()}, cancelled={self.task.cancelled()}"
        LOGGER.debug("Waiting for task to complete. Status: %s", task_status)

        try:
            await asyncio.wait_for(self.task, timeout=timeout)
            LOGGER.info("Task completed gracefully")
        except asyncio.TimeoutError:
            LOGGER.warning(
                "Business logic loop did not stop within %s seconds, cancelling...", timeout)
            self.task.cancel()
            await self._await_cancelled_task()

    async def _await_cancelled_task(self) -> None:
        """Await a cancelled task and handle any errors."""
        try:
            await self.task
            LOGGER.info("Task cancelled successfully")
        except asyncio.CancelledError:
            LOGGER.debug("Task cancellation confirmed")
        except Exception as cancel_error:
            LOGGER.error("Error while waiting for cancelled task: %s", cancel_error)
            raise BusinessLogicError(
                f"Error during task cancellation: {str(cancel_error)}")

    async def start(self) -> None:
        """Start the business logic loop."""
        if self.running:
            LOGGER.warning("Business logic loop is already running")
            return

        # Store original state for rollback
        original_state = self._capture_state()

        try:
            LOGGER.info("Starting business logic loop...")
            self.running = True
            self.start_time = datetime.now(timezone.utc)
            self.shutdown_event.clear()
            self.task = asyncio.create_task(self._run_business_logic_loop())

            # Save state immediately to reflect shutdown signal
            # If this fails, we'll rollback to maintain consistency
            self._save_state()

            LOGGER.info("Business logic loop started successfully")
        except Exception as e:
            LOGGER.error("Failed to start business logic loop: %s", e)

            # Rollback state changes to maintain consistency between in-memory and file state
            self._restore_state(original_state)

            try:
                self._save_state()  # Save the rolled back state
            except Exception as save_error:
                # Error already logged in _save_state, but log rollback save failure separately
                LOGGER.error(
                    "Failed to save rolled back state: %s", save_error)
                # Re-raise with appropriate error type
                raise BusinessLogicError(
                    f"Error stopping business logic loop: {str(e)}. "
                    f"Additionally, failed to save rolled back state: {str(save_error)}"
                ) from save_error

    async def stop(self, timeout: float = 30.0) -> None:
        """Stop the business logic loop gracefully.

        Args:
            timeout: Maximum time to wait for graceful shutdown before cancelling (default: 30.0 seconds)
        """
        if not self.running:
            LOGGER.warning("Business logic loop is not running")
            return

        # Store original state for rollback if state save fails
        original_state = self._capture_state()

        try:
            LOGGER.info("Stopping business logic loop...")

            # Signal shutdown first
            self.running = False
            self.shutdown_event.set()

            # Save state immediately to reflect shutdown signal
            # If this fails, we'll rollback to maintain consistency
            self._save_state()

            # Wait for task to complete gracefully
            if self.task and not self.task.done():
                await self._wait_for_task_completion(timeout)
            elif self.task:
                LOGGER.debug("Task already done: %s", self.task.done())

            # Clean up task reference
            self.task = None

            # Save final state after successful shutdown
            self._save_state()
            LOGGER.info("Business logic loop stopped successfully")
        except Exception as e:
            LOGGER.error("Error stopping business logic loop: %s", e)
            # Rollback state changes to maintain consistency between in-memory and file state
            self._restore_state(original_state)
            try:
                self._save_state()  # Save the rolled back state
            except Exception as save_error:
                # Error already logged in _save_state, but log rollback save failure separately
                LOGGER.error(
                    "Failed to save rolled back state: %s", save_error)
                # Re-raise with appropriate error type
                raise BusinessLogicError(
                    f"Error stopping business logic loop: {str(e)}. "
                    f"Additionally, failed to save rolled back state: {str(save_error)}"
                ) from save_error

    async def _run_business_logic_loop(self) -> None:
        """Internal method to run the business logic loop with shutdown handling."""
        try:
            # Heartbeat counter - log every 5 minutes (300 seconds / 5 seconds = 60
            # iterations)
            heartbeat_counter = 0
            # Log heartbeat every 60 iterations (5 minutes)
            heartbeat_interval = 60

            # Run the business logic loop until shutdown is requested
            while self.running and not self.shutdown_event.is_set():
                try:
                    # Add heartbeat log every 5 minutes
                    heartbeat_counter += 1
                    if heartbeat_counter >= heartbeat_interval:
                        LOGGER.info(
                            "[HEARTBEAT] Business logic loop is running inside the Docker container.")
                        heartbeat_counter = 0

                    # Run one iteration of the business logic loop
                    active_cameras = camera_registry.get_all_active()
                    current_time = datetime.now(timezone.utc)
                    new_events: List[MotionEvent] = []

                    for camera in active_cameras:
                        await poll_for_events(camera, current_time, new_events)

                    if new_events:
                        insert_events_into_db(new_events)

                    await start_video_retrieval_tasks()
                    await start_facial_recognition_tasks()

                    # Wait before next iteration, but check for shutdown
                    await asyncio.sleep(5)

                except Exception as e:
                    # Log error but continue running unless explicitly stopped
                    error_type = type(e).__name__
                    LOGGER.error("%s in loop iteration: %s", error_type, e)
                    if self.running:
                        await asyncio.sleep(5)  # Wait before retrying
        except asyncio.CancelledError:
            LOGGER.info("Business logic loop task cancelled")
        except Exception as e:
            LOGGER.error("Unexpected error in business logic loop: %s", e)
            raise BusinessLogicError(
                f"Unexpected error in business logic loop: {str(e)}")
        finally:
            self.running = False
            try:
                self._save_state()
            except Exception as e:
                LOGGER.error("Failed to save state in finally block: %s", e)
                # Don't raise - we're already shutting down

    @staticmethod
    def get_status() -> Dict[str, Any]:
        """Get the current status of the business logic loop."""
        try:
            # Load state from file for cross-process access
            state = BusinessLogicManager._load_state()

            # Calculate uptime only if the business logic loop is running
            uptime = None
            try:
                if state.get('running', False) and state.get('start_time'):
                    start_time = datetime.fromisoformat(state['start_time'])
                    uptime = str(datetime.now(timezone.utc) - start_time)
                elif not state.get('running', False) and state.get('start_time'):
                    # If not running, show the total runtime before it stopped
                    start_time = datetime.fromisoformat(state['start_time'])
                    # Use last_updated as the stop time if available, otherwise use
                    # current time
                    if state.get('last_updated'):
                        stop_time = datetime.fromisoformat(
                            state['last_updated'])
                    else:
                        stop_time = datetime.now(timezone.utc)
                    uptime = f"{str(stop_time - start_time)} (stopped)"
            except ValueError as e:
                LOGGER.error("Failed to parse timestamps: %s", e)
                uptime = "Unknown (invalid timestamps)"
            except Exception as e:
                LOGGER.error("Failed to calculate total runtime: %s", e)
                uptime = "Unknown"

            return {
                "running": state.get('running', False),
                "start_time": state.get('start_time'),
                "uptime": uptime,
                "business_logic_completed": state.get('business_logic_completed'),
                "business_logic_cancelled": state.get('business_logic_cancelled')
            }
        except Exception as e:
            LOGGER.error("Failed to get business logic status: %s", e)
            raise BusinessLogicError(
                f"Failed to get business logic status: {str(e)}")


# Create a singleton instance
BUSINESS_LOGIC_MANAGER = BusinessLogicManager()
