"""
Business Logic Manager

This module manages the business logic loop for the Watch Tower application,
providing start/stop functionality and state management.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from watch_tower.exceptions import BusinessLogicError, ConfigurationError

logger = logging.getLogger(__name__)

# State file for cross-process access
STATE_FILE = "/tmp/watch_tower_business_logic_state.json"


class BusinessLogicManager:
    """Manages the business logic loop lifecycle with file-based state persistence."""

    def __init__(self):
        self.task: Optional[asyncio.Task] = None
        self.running = False
        self.shutdown_event = asyncio.Event()
        self.start_time: Optional[datetime] = None

    def _save_state(self) -> None:
        """Save the current state to a file for cross-process access."""
        try:
            state = {
                "running": self.running,
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "business_logic_completed": self.task.done() if self.task else None,
                "business_logic_cancelled": self.task.cancelled() if self.task else None,
                "last_updated": datetime.now(
                    timezone.utc).isoformat()}
            with open(STATE_FILE, 'w') as f:
                json.dump(state, f)
        except (OSError, IOError) as e:
            logger.error(f"Failed to save state file: {e}")
            raise BusinessLogicError(f"Failed to save state file: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error saving state: {e}")
            raise BusinessLogicError(
                f"Unexpected error saving state: {str(e)}")

    def _load_state(self) -> Dict[str, Any]:
        """Load the current state from file."""
        try:
            if os.path.exists(STATE_FILE):
                with open(STATE_FILE, 'r') as f:
                    return json.load(f)
        except (OSError, IOError) as e:
            logger.error(f"Failed to load state file: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse state file JSON: {e}")
        except Exception as e:
            logger.error(f"Unexpected error loading state: {e}")

        return {
            "running": False,
            "start_time": None,
            "business_logic_completed": None,
            "business_logic_cancelled": None
        }

    async def start(self) -> None:
        """Start the business logic loop."""
        if self.running:
            logger.warning("Business logic loop is already running")
            return

        # Store original state for rollback
        original_running = self.running
        original_start_time = self.start_time
        original_task = self.task
        original_shutdown_event_state = self.shutdown_event.is_set()
        rollback = False

        try:
            logger.info("Starting business logic loop...")
            self.running = True
            self.start_time = datetime.now(timezone.utc)
            self.shutdown_event.clear()
            self.task = asyncio.create_task(self._run_business_logic_loop())
            self._save_state()
            logger.info("Business logic loop started successfully")
        except Exception as e:
            logger.error(f"Failed to start business logic loop: {e}")
            # Rollback all state changes
            self.running = original_running
            self.start_time = original_start_time
            self.task = original_task
            if original_shutdown_event_state:
                self.shutdown_event.set()
            else:
                self.shutdown_event.clear()
            rollback = True
            try:
                self._save_state()  # Save the rolled back state
            except Exception as save_error:
                logger.error(f"Failed to save rolled back state: {save_error}")
            # Re-raise with appropriate error type
            if isinstance(e, BusinessLogicError):
                raise
            elif isinstance(e, ConfigurationError):
                raise
            else:
                raise BusinessLogicError(
                    f"Failed to start business logic loop: {str(e)}")

    async def stop(self) -> None:
        """Stop the business logic loop gracefully."""
        if not self.running:
            logger.warning("Business logic loop is not running")
            return

        # Store original state for rollback
        original_running = self.running
        original_task = self.task
        original_shutdown_event_state = self.shutdown_event.is_set()
        rollback = False

        try:
            logger.info("Stopping business logic loop...")
            self.running = False
            self.shutdown_event.set()
            self._save_state()

            if self.task and not self.task.done():
                # Wait for the task to complete with a timeout
                try:
                    await asyncio.wait_for(self.task, timeout=30.0)
                except asyncio.TimeoutError:
                    logger.warning(
                        "Business logic loop did not stop gracefully, cancelling...")
                    self.task.cancel()
                    try:
                        await self.task
                    except asyncio.CancelledError:
                        pass

            logger.info("Business logic loop stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping business logic loop: {e}")
            # Rollback state changes
            self.running = original_running
            self.task = original_task
            if original_shutdown_event_state:
                self.shutdown_event.set()
            else:
                self.shutdown_event.clear()
            rollback = True
            try:
                self._save_state()  # Save the rolled back state
            except Exception as save_error:
                logger.error(f"Failed to save rolled back state: {save_error}")
            # Re-raise with appropriate error type
            if isinstance(e, BusinessLogicError):
                raise
            elif isinstance(e, ConfigurationError):
                raise
            else:
                raise BusinessLogicError(
                    f"Error stopping business logic loop: {str(e)}")
        finally:
            if not rollback:
                self.running = False
                try:
                    self._save_state()
                except Exception as save_error:
                    logger.error(f"Failed to save final state: {save_error}")

    async def _run_business_logic_loop(self) -> None:
        """Internal method to run the business logic loop with shutdown handling."""
        try:
            # Import the functions from events_loop
            from watch_tower.registry.camera_registry import REGISTRY as camera_registry
            from data_models.motion_event import MotionEvent
            import datetime
            from watch_tower.core.events_loop import poll_for_events, insert_events_into_db, start_video_retrieval_tasks, start_facial_recognition_tasks

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
                        logger.info(
                            "[HEARTBEAT] Business logic loop is running inside the Docker container.")
                        heartbeat_counter = 0

                    # Run one iteration of the business logic loop
                    active_cameras = camera_registry.get_all_active()
                    current_time = datetime.datetime.now(datetime.timezone.utc)
                    new_events: list[MotionEvent] = []

                    for camera in active_cameras:
                        if not self.running or self.shutdown_event.is_set():
                            break
                        await poll_for_events(camera, current_time, new_events)

                    if new_events:
                        insert_events_into_db(new_events)

                    await start_video_retrieval_tasks()
                    await start_facial_recognition_tasks()

                    # Wait before next iteration, but check for shutdown
                    await asyncio.sleep(5)

                except BusinessLogicError as e:
                    logger.error(
                        f"Business logic error in loop iteration: {e}")
                    # Continue running unless explicitly stopped
                    if self.running:
                        await asyncio.sleep(5)  # Wait before retrying
                except ConfigurationError as e:
                    logger.error(f"Configuration error in loop iteration: {e}")
                    # Continue running unless explicitly stopped
                    if self.running:
                        await asyncio.sleep(5)  # Wait before retrying
                except Exception as e:
                    logger.error(
                        f"Unexpected error in business logic loop iteration: {e}")
                    # Continue running unless explicitly stopped
                    if self.running:
                        await asyncio.sleep(5)  # Wait before retrying
        except asyncio.CancelledError:
            logger.info("Business logic loop task cancelled")
        except BusinessLogicError as e:
            logger.error(f"Business logic error in main loop: {e}")
            raise
        except ConfigurationError as e:
            logger.error(f"Configuration error in main loop: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in business logic loop: {e}")
            raise BusinessLogicError(
                f"Unexpected error in business logic loop: {str(e)}")
        finally:
            self.running = False
            self._save_state()

    def get_status(self) -> Dict[str, Any]:
        """Get the current status of the business logic loop."""
        try:
            # Load state from file for cross-process access
            state = self._load_state()

            # Calculate uptime only if the business logic loop is running
            uptime = None
            if state.get('running', False) and state.get('start_time'):
                try:
                    start_time = datetime.fromisoformat(state['start_time'])
                    uptime = str(datetime.now(timezone.utc) - start_time)
                except ValueError as e:
                    logger.error(f"Failed to parse start time: {e}")
                    uptime = "Unknown (invalid start time)"
                except Exception as e:
                    logger.error(f"Failed to calculate uptime: {e}")
                    uptime = "Unknown"
            elif not state.get('running', False) and state.get('start_time'):
                # If not running, show the total runtime before it stopped
                try:
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
                    logger.error(f"Failed to parse timestamps: {e}")
                    uptime = "Unknown (invalid timestamps)"
                except Exception as e:
                    logger.error(f"Failed to calculate total runtime: {e}")
                    uptime = "Unknown"

            return {
                "running": state.get('running', False),
                "start_time": state.get('start_time'),
                "uptime": uptime,
                "business_logic_completed": state.get('business_logic_completed'),
                "business_logic_cancelled": state.get('business_logic_cancelled')
            }
        except Exception as e:
            logger.error(f"Failed to get business logic status: {e}")
            raise BusinessLogicError(
                f"Failed to get business logic status: {str(e)}")


# Create a singleton instance
business_logic_manager = BusinessLogicManager()
