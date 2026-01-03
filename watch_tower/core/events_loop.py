"""
Events Loop

This module contains the main events loop that polls cameras for motion events,
processes them, and manages the business logic flow.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

from sqlalchemy.exc import SQLAlchemyError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception,
)

from aws.exceptions import RekognitionError
from cameras.camera_base import CameraBase
from cameras.camera_base import PluginType
from data_models.motion_event import MotionEvent
from db.connection import get_database_connection
from db.exceptions import DatabaseConnectionError
from db.repositories.motion_event_repository import MotionEventRepository
from utils.error_handler import handle_async_errors
from utils.metric_helpers import add_histogram_metric, inc_counter_metric
from utils.metrics import MetricDataPointName as Metric
from watch_tower.config import config, get_timezone
from watch_tower.exceptions import RingConnectionManagerError
from watch_tower.registry.camera_registry import CameraStatus, REGISTRY as camera_registry
from watch_tower.registry.connection_manager_registry import VendorStatus, REGISTRY as connection_manager_registry

LOGGER = logging.getLogger(__name__)

# Keep track of running tasks
enqueued_upload_tasks: Dict[int, asyncio.Task] = {}
enqueued_facial_recognition_tasks: Dict[str, asyncio.Task] = {}

# Semaphores to limit concurrent operations using config
UPLOAD_SEMAPHORE = asyncio.Semaphore(config.video.max_concurrent_uploads)
FACE_RECOGNITION_SEMAPHORE = asyncio.Semaphore(
    config.video.max_concurrent_face_recognition)


@handle_async_errors(log_error=True, reraise=False)
async def handle_camera_error(camera: CameraBase) -> None:
    """Handle camera errors by updating registry status."""
    try:
        if not connection_manager_registry.get_connection_manager(
                camera.plugin_type).is_healthy():
            connection_manager_registry.update_status(
                camera.plugin_type, VendorStatus.INACTIVE)
            for cam in camera_registry.get_all_by_vendor(camera.plugin_type):
                camera_registry.update_status(
                    cam.plugin_type, cam.camera_name, CameraStatus.INACTIVE)
        else:
            properties = await camera.get_properties()
            camera_registry.update_status(
                camera.plugin_type,
                properties["name"],
                CameraStatus.INACTIVE)

    except Exception as e:
        LOGGER.error("Error handling camera error: %s", e)
        LOGGER.exception("Full traceback:")


def _is_retryable_error(exception: Exception) -> bool:
    """Check if an exception is retryable.
    
    Args:
        exception: The exception to check
        
    Returns:
        True if the exception should be retried, False otherwise
    """
    # Retry on Ring API errors (but not authentication errors that need re-auth)
    if isinstance(exception, RingConnectionManagerError):
        return True
    return False


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception(_is_retryable_error),
    reraise=True
)
async def _retrieve_motion_events_with_retry(
        camera: CameraBase,
        from_time: datetime,
        to_time: datetime
) -> List[MotionEvent]:
    """Retrieve motion events with retry logic.
    
    Args:
        camera: The camera to retrieve events from
        from_time: Start of the time range
        to_time: End of the time range
        
    Returns:
        List of motion events
        
    Raises:
        Exception: If all retry attempts fail
    """
    return await camera.retrieve_motion_events(from_time, to_time)


async def poll_for_events(
        camera: CameraBase,
        current_time: datetime,
        new_events: List[MotionEvent]
) -> None:
    """Poll camera for new motion events and add them to the list.
    
    This function will retry up to 3 times with exponential backoff if the
    event retrieval fails due to Ring API errors. If all retries are exhausted,
    the camera error will be handled and the function will return without
    raising an exception, allowing other cameras to continue processing.
    """
    try:
        properties = await camera.get_properties()
        camera_entry = camera_registry.cameras[(camera.plugin_type, properties["name"])]
        time_since_last_polled = current_time - camera_entry.last_polled
        if time_since_last_polled > timedelta(seconds=camera.motion_poll_interval):
            from_time = camera_entry.last_polled
            events = await _retrieve_motion_events_with_retry(camera, from_time, current_time)
            new_events.extend(events)
            camera_registry.update_last_polled(camera.plugin_type, properties["name"], current_time)
        else:
            LOGGER.debug("No new motion events found for camera %s", camera.camera_name)
    except RingConnectionManagerError as e:
        # All retries exhausted - handle the camera error
        LOGGER.error(
            "Failed to retrieve motion events for camera %s after all retries: %s",
            camera.camera_name, e
        )
        LOGGER.exception("Full traceback:")
        await handle_camera_error(camera)


def insert_events_into_db(events: List[MotionEvent]) -> None:
    """Insert motion events into the database, skipping duplicates."""
    if not events:
        return

    _, session_factory = get_database_connection()
    motion_event_repository = MotionEventRepository()

    with session_factory() as session:
        timezone_obj = get_timezone()
        now = datetime.now(timezone_obj)
        future_date = datetime(9998, 12, 31, 23, 59, 59, tzinfo=now.tzinfo)

        for event in events:
            # Use event.event_id which contains the Ring event ID from the API
            # When creating from Ring API via MotionEvent.from_ring_event(),
            # event.event_id is set to the Ring event ID
            ring_event_id = event.event_id

            if not ring_event_id:
                LOGGER.warning(
                    "Event missing Ring event ID, skipping: %s", event)
                continue

            # Check if an event with this Ring event ID and camera name already exists
            existing_events = motion_event_repository.get_by_ring_event_id_and_camera(
                session, ring_event_id, event.camera_name
            )

            if existing_events:
                # Event already exists, skip insertion
                LOGGER.debug(
                    "Skipping duplicate event: Ring event ID %s for camera %s "
                    "already exists in database (found %d existing events)",
                    ring_event_id, event.camera_name, len(existing_events))
                continue

            event_data: Dict[str, Any] = {
                "event_metadata": {"event_id": event.event_id, "camera_vendor": event.camera_vendor.value},
                "camera_name": event.camera_name,
                "motion_detected": event.timestamp,
                "uploaded_to_s3": future_date,  # Use future date to indicate unprocessed
                "facial_recognition_processed": future_date,  # Use future date to indicate unprocessed
                "s3_url": event.s3_url if event.s3_url else ""
            }
            motion_event_repository.create(session, event_data)


async def process_video_retrieval(event: MotionEvent, camera: CameraBase) -> None:
    """Process a single video retrieval task"""
    async with UPLOAD_SEMAPHORE:
        await camera.retrieve_video_from_event_and_upload_to_s3(event)

def _handle_video_retrieval_task_completion(
        task: asyncio.Task,
        event_id: int,
) -> None:
    """Handle task completion, log exceptions"""
    try:
        # This will raise if the task raised an exception
        task.result()
    except Exception as e:
        LOGGER.error(
            "Video retrieval task for event ID %d raised an exception: %s",
            event_id, e
        )
        LOGGER.exception("Full traceback:")
    finally:
        # Always remove from tracking
        enqueued_upload_tasks.pop(event_id, None)


def _handle_facial_recognition_task_completion(
        task: asyncio.Task,
        event_key: str,
        db_event: Any,
) -> None:
    """Handle task completion, log exceptions"""
    try:
        # This will raise if the task raised an exception
        task.result()
    except Exception as e:
        LOGGER.error(
            "Task for event %s (ID: %d) raised an exception: %s",
            event_key, db_event.id, e
        )
        LOGGER.exception("Full traceback:")

    finally:
        # Always remove from tracking
        enqueued_facial_recognition_tasks.pop(event_key, None)


async def start_facial_recognition_tasks() -> None:
    """Start facial recognition tasks for unprocessed events"""
    from aws.rekognition.rekognition_service import RekognitionService
    rekognition_service = RekognitionService()
    _, session_factory = get_database_connection()
    with session_factory() as session:
        unprocessed_events = MotionEventRepository().get_unprocessed_events(session)

        for db_event in unprocessed_events:
            if db_event.s3_url in enqueued_facial_recognition_tasks:
                # Skip if a task is already running for this event
                continue
            # Convert DB event to MotionEvent
            motion_event = MotionEvent(
                event_id=str(db_event.id),
                camera_vendor=PluginType(db_event.event_metadata.get('camera_vendor')),
                camera_name=db_event.camera_name,
                timestamp=db_event.motion_detected,
                s3_url=db_event.s3_url if db_event.s3_url else None,
                event_metadata=db_event.event_metadata
            )

            event_s3_url = motion_event.s3_url
            event_db_event = db_event

            # Create a task for this facial recognition with result processing
            task = asyncio.create_task(
                process_face_search_with_visitor_logs_with_semaphore(
                    rekognition_service,
                    motion_event,
                    event_db_event,
                    session_factory
                )
            )
            enqueued_facial_recognition_tasks[event_s3_url] = task
            task.add_done_callback(
                lambda t, key=event_s3_url, event=event_db_event:
                _handle_facial_recognition_task_completion(t, key, event)
            )

            # Add a small delay between tasks to prevent overwhelming the system
            await asyncio.sleep(0.1)


async def process_face_search_with_visitor_logs_with_semaphore(
        rekognition_service,
        motion_event: MotionEvent,
        db_event: Any,
        session_factory: Any
) -> None:
    """Process face search with visitor logs using semaphore for concurrency control"""
    async with FACE_RECOGNITION_SEMAPHORE:
        await process_face_search_with_visitor_logs(
            rekognition_service, motion_event, db_event, session_factory
        )


async def process_face_search_with_visitor_logs(
        rekognition_service,
        motion_event: MotionEvent,
        db_event: Any,
        session_factory: Any
) -> None:
    """Process face search and create visitor log entries for found people"""
    # Process the face search
    try:
        start_time: datetime = datetime.now(get_timezone())
        face_search_results, was_skipped = await rekognition_service.start_face_search(motion_event.s3_url)
    except RekognitionError as e:
        LOGGER.error(
            "Error processing face search for event %s: %s", motion_event.event_id, e)
        LOGGER.exception("Full traceback:")
        inc_counter_metric(Metric.AWS_REKOGNITION_FACE_SEARCH_ERROR_COUNT)
        raise

    # If a rekognition task is already queued or running, skip processing
    if was_skipped:
        LOGGER.info(
            "Face search skipped for event %s - job already running", motion_event.event_id)
        return
    # Increment the duration and success count metrics
    end_time: datetime = datetime.now(get_timezone())
    add_histogram_metric(
        Metric.AWS_REKOGNITION_FACE_SEARCH_DURATION_SECONDS,
        (end_time - start_time).total_seconds()
    )
    # Increment the duration and success count metrics
    end_time: datetime = datetime.now(get_timezone())
    add_histogram_metric(
        Metric.AWS_REKOGNITION_FACE_SEARCH_DURATION_SECONDS,
        (end_time - start_time).total_seconds()
    )
    inc_counter_metric(Metric.AWS_REKOGNITION_FACE_SEARCH_SUCCESS_COUNT)

    timezone_obj = get_timezone()

    if face_search_results:
        # Consolidate results to get the max confidence score for each person
        consolidated_results: Dict[str, float] = {}
        for match in face_search_results:
            person_name = match.get('external_image_id')
            confidence_score = match.get('confidence')

            if person_name and confidence_score is not None:
                # Update with the max confidence score found for this person
                if person_name not in consolidated_results or confidence_score > consolidated_results[person_name]:
                    consolidated_results[person_name] = confidence_score

        # Use a single session for both visitor log creation and event marking
        # This ensures atomicity - if marking fails, visitor logs are rolled back
        try:
            with session_factory() as session:
                from db.repositories.visitor_log_repository import VisitorLogRepository
                visitor_log_repository = VisitorLogRepository()
                motion_event_repository = MotionEventRepository()

                # Create visitor logs (add to session but don't commit yet)
                camera_name = db_event.camera_name
                created_logs = []
                for person_name, max_confidence in consolidated_results.items():
                    visitor_log_data = {
                        "camera_name": camera_name,
                        "persons_name": person_name,
                        "confidence_score": max_confidence,
                        "visited_at": db_event.motion_detected,
                    }
                    # Create the object and add to session without committing)
                    visitor_log_repository.add_to_session(session, visitor_log_data)
                    created_logs.append((person_name, max_confidence))
                    LOGGER.info(
                        "Prepared visitor log for person '%s' at event %d with max confidence %f",
                        person_name, db_event.id, max_confidence
                    )

                # Mark the motion event as processed
                # This will commit both visitor logs and event marking atomically
                motion_event_repository.mark_as_processed(
                    session,
                    db_event.id,
                    datetime.now(timezone_obj)
                )

        except SQLAlchemyError as e:
            # Session will automatically rollback on exception
            LOGGER.error(
                "Database error processing visitor logs and marking event %s: %s",
                motion_event.event_id, e
            )
            LOGGER.exception("Full traceback:")
            # Event will be retried on next iteration, visitor logs will be rolled back
            raise

        # Log success after commit
        for person_name, max_confidence in created_logs:
            LOGGER.info(
                "Committed visitor log for person '%s' at event %d with max confidence %f",
                person_name, db_event.id, max_confidence
            )

        LOGGER.info(
            "Marked event %s as processed and created %d visitor log entries",
            motion_event.event_id, len(created_logs)
        )
    else:
        # Face search completed but found no faces - just mark as processed
        LOGGER.info(
            "Face search completed for event %s - no faces detected", motion_event.event_id)

        try:
            with session_factory() as session:
                motion_event_repository = MotionEventRepository()
                motion_event_repository.mark_as_processed(
                    session,
                    db_event.id,
                    datetime.now(timezone_obj)
                )
                LOGGER.info(
                    "Marked event %s as processed (no faces detected)",
                    motion_event.event_id
                )
        except SQLAlchemyError as e:
            LOGGER.error(
                "Database error marking event %s as processed: %s",
                motion_event.event_id, e
            )
            LOGGER.exception("Full traceback:")
            # Event will be retried on next iteration
            raise


async def create_visitor_logs_from_face_search(
        face_search_results: List[Dict[str, Any]],
        db_event: Any,
        session_factory: Any
) -> None:
    """Create visitor log entries for people found in face search results"""
    # Consolidate results to get the max confidence score for each person
    consolidated_results: Dict[str, float] = {}
    for match in face_search_results:
        person_name = match.get('external_image_id')
        confidence_score = match.get('confidence')

        if person_name and confidence_score is not None:
            # Update with the max confidence score found for this person
            if person_name not in consolidated_results or confidence_score > consolidated_results[
                    person_name]:
                consolidated_results[person_name] = confidence_score

    with session_factory() as session:
        from db.repositories.visitor_log_repository import VisitorLogRepository
        visitor_log_repository = VisitorLogRepository()

        # Get camera information
        camera_name = db_event.camera_name

        for person_name, max_confidence in consolidated_results.items():
            # Create a single visitor log entry for each person with the max
            # confidence
            visitor_log_data = {
                "camera_name": camera_name,
                "persons_name": person_name,
                "confidence_score": max_confidence,
                "visited_at": db_event.motion_detected,
            }

            visitor_log_repository.create(session, visitor_log_data)
            LOGGER.info(
                "Created consolidated visitor log for person '%s' at event %d with max confidence %f",
                person_name, db_event.id, max_confidence)


async def start_video_retrieval_tasks() -> None:
    """Start video retrieval tasks for unprocessed events"""
    _, session_factory = get_database_connection()
    with session_factory() as session:
        motion_event_repository = MotionEventRepository()
        unprocessed_events = motion_event_repository.get_unuploaded_events(session)

        for db_event in unprocessed_events:
            if db_event.id in enqueued_upload_tasks:
                # Skip if a task is already running for this event
                continue
            # Find the camera that created this event
            camera_vendor = db_event.event_metadata.get('camera_vendor')
            camera = camera_registry.get(
                PluginType(camera_vendor), db_event.camera_name)
            if camera:
                # Convert DB event to MotionEvent
                motion_event = MotionEvent(
                    event_id=str(db_event.id),
                    camera_vendor=camera_vendor,
                    camera_name=db_event.camera_name,
                    timestamp=db_event.motion_detected,
                    s3_url=db_event.s3_url if db_event.s3_url else None,
                    event_metadata=db_event.event_metadata
                )

                event_id = db_event.id

                # Create a task for this video retrieval
                task = asyncio.create_task(
                    process_video_retrieval(
                        motion_event, camera))
                enqueued_upload_tasks[event_id] = task
                task.add_done_callback(
                    lambda t, key=event_id: _handle_video_retrieval_task_completion(t, key))

                # Add a small delay between tasks to prevent overwhelming the system
                await asyncio.sleep(0.1)
