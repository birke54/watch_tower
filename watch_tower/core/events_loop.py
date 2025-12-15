"""
Events Loop

This module contains the main events loop that polls cameras for motion events,
processes them, and manages the business logic flow.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Set
from watch_tower.registry.camera_registry import CameraStatus, REGISTRY as camera_registry
from cameras.camera_base import CameraBase
from watch_tower.registry.connection_manager_registry import VendorStatus, REGISTRY as connection_manager_registry
from data_models.motion_event import MotionEvent
from db.connection import get_database_connection
from db.repositories.motion_event_repository import MotionEventRepository
from cameras.camera_base import PluginType
from watch_tower.config import config, get_timezone
from utils.error_handler import handle_async_errors
from utils.metrics import MetricDataPointName as Metric
from utils.metric_helpers import inc_counter_metric

LOGGER = logging.getLogger(__name__)

# Keep track of running tasks
enqueued_upload_tasks: Dict[int, asyncio.Task] = {}
enqueued_facial_recognition_tasks: Dict[str, asyncio.Task] = {}

# Semaphores to limit concurrent operations using config
upload_semaphore = asyncio.Semaphore(config.video.max_concurrent_uploads)
face_recognition_semaphore = asyncio.Semaphore(
    config.video.max_concurrent_face_recognition)


@handle_async_errors(log_error=True, reraise=False)
async def handle_camera_error(camera: CameraBase) -> None:
    try:
        if not connection_manager_registry.get_connection_manager(
                camera.plugin_type).is_healthy():
            connection_manager_registry.update_status(
                camera.plugin_type, VendorStatus.INACTIVE)
            for camera in camera_registry.get_all_by_vendor(camera.plugin_type):
                camera_registry.update_status(
                    camera.plugin_type, camera.camera_name, CameraStatus.INACTIVE)
        else:
            properties = await camera.get_properties()
            camera_registry.update_status(
                camera.plugin_type,
                properties["name"],
                CameraStatus.INACTIVE)

    except Exception as e:
        LOGGER.error("Error handling camera error: %s", e)
        LOGGER.exception("Full traceback:")


async def poll_for_events(
    camera: CameraBase,
    current_time: datetime,
    new_events: List[MotionEvent]
) -> None:
    properties = await camera.get_properties()
    camera_entry = camera_registry.cameras[(camera.plugin_type, properties["name"])]
    time_since_last_polled = current_time - camera_entry.last_polled
    if time_since_last_polled > timedelta(seconds=camera.motion_poll_interval):
        try:
            from_time = camera_entry.last_polled
            new_events.extend(await camera.retrieve_motion_events(from_time, current_time))
            camera_registry.update_last_polled(camera.plugin_type, properties["name"], current_time)
        except Exception as e:
            LOGGER.error("Error retrieving motion videos: %s", e)
            LOGGER.exception("Full traceback:")
            await handle_camera_error(camera)


def insert_events_into_db(events: List[MotionEvent]) -> None:
    if not events:
        return

    engine, session_factory = get_database_connection()
    motion_event_repository = MotionEventRepository()

    with session_factory() as session:
        tz = get_timezone()
        now = datetime.now(tz)
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
            existing_events = session.query(motion_event_repository.model).filter(
                motion_event_repository.model.event_metadata.op('->>')('event_id') == str(ring_event_id),
                motion_event_repository.model.camera_name == event.camera_name
            ).all()
            
            if existing_events:
                # Event already exists, skip insertion
                LOGGER.debug(
                    "Skipping duplicate event: Ring event ID %s for camera %s already exists in database (found %d existing events)",
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
    async with upload_semaphore:
        try:
            await camera.retrieve_video_from_event_and_upload_to_s3(event)
        except Exception as e:
            LOGGER.error("Error processing video for event %s: %s", event.event_id, e)
            LOGGER.exception("Full traceback:")


async def start_facial_recognition_tasks() -> None:
    """Start facial recognition tasks for unprocessed events"""
    try:
        from aws.rekognition.rekognition_service import RekognitionService
        rekognition_service = RekognitionService()
        _, session_factory = get_database_connection()
        with session_factory() as session:
            motion_event_repository = MotionEventRepository()
            unprocessed_events = motion_event_repository.get_unprocessed_events(session)

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

                # Create a task for this facial recognition with result processing
                task = asyncio.create_task(
                    process_face_search_with_visitor_logs_with_semaphore(
                        rekognition_service,
                        motion_event,
                        db_event,
                        session_factory
                    )
                )
                enqueued_facial_recognition_tasks[motion_event.s3_url] = task
                task.add_done_callback(lambda t, key=motion_event.s3_url: enqueued_facial_recognition_tasks.pop(key, None))

                # Add a small delay between tasks to prevent overwhelming the system
                await asyncio.sleep(0.1)
    except Exception as e:
        LOGGER.error("Error starting facial recognition tasks: %s", e)
        LOGGER.exception("Full traceback:")


async def process_face_search_with_visitor_logs_with_semaphore(
    rekognition_service,
    motion_event: MotionEvent,
    db_event: Any,
    session_factory: Any
) -> None:
    """Process face search with visitor logs using semaphore for concurrency control"""
    async with face_recognition_semaphore:
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
    # Process the face search - the check on line 144 already prevents duplicate tasks
    try:
        face_search_results, was_skipped = await rekognition_service.start_face_search(motion_event.s3_url)
        inc_counter_metric(Metric.AWS_REKOGNITION_FACE_SEARCH_SUCCESS_COUNT)
    except Exception as e:
        LOGGER.error(
            "Error processing face search for event %s: %s", motion_event.event_id, e)
        LOGGER.exception("Full traceback:")
        inc_counter_metric(Metric.AWS_REKOGNITION_FACE_SEARCH_ERROR_COUNT)
        return

    # If a rekognition task is already queued or running, skip processing
    if was_skipped:
        LOGGER.info(
            "Face search skipped for event %s - job already running", motion_event.event_id)
        return

    tz = get_timezone()
    if face_search_results:
        # Process the results and create visitor log entries
        await create_visitor_logs_from_face_search(
            face_search_results,
            db_event,
            session_factory
        )

        # Mark the motion event as processed only if we got results
        with session_factory() as session:
            motion_event_repository = MotionEventRepository()
            motion_event_repository.mark_as_processed(
                session,
                db_event.id,
                datetime.now(tz)
            )
    else:
        # Face search completed but found no faces
        LOGGER.info(
            "Face search completed for event %s - no faces detected", motion_event.event_id)

        # Mark the motion event as processed since the search completed
        with session_factory() as session:
            motion_event_repository = MotionEventRepository()
            motion_event_repository.mark_as_processed(
                session,
                db_event.id,
                datetime.now(tz)
            )


async def create_visitor_logs_from_face_search(
    face_search_results: List[Dict[str, Any]],
    db_event: Any,
    session_factory: Any
) -> None:
    """Create visitor log entries for people found in face search results"""
    try:
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
                    "Created consolidated visitor log for person '%s' at event %d with max confidence %f", person_name, db_event.id, max_confidence)

    except Exception as e:
        LOGGER.error("Error creating visitor logs from face search results: %s", e)
        LOGGER.exception("Full traceback:")


async def start_video_retrieval_tasks() -> None:
    """Start video retrieval tasks for unprocessed events"""
    try:
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

                    # Create a task for this video retrieval
                    task = asyncio.create_task(
                        process_video_retrieval(
                            motion_event, camera))
                    enqueued_upload_tasks[db_event.id] = task
                    task.add_done_callback(lambda t, key=db_event.id: enqueued_upload_tasks.pop(key, None))

                    # Add a small delay between tasks to prevent overwhelming the system
                    await asyncio.sleep(0.1)
    except Exception as e:
        LOGGER.error(f"Error starting video retrieval tasks: %s", e)
        LOGGER.exception("Full traceback:")