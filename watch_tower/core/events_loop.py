"""
Events Loop

This module contains the main events loop that polls cameras for motion events,
processes them, and manages the business logic flow.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Set
from watch_tower.registry.camera_registry import CameraStatus, registry as camera_registry
from cameras.camera_base import CameraBase
from watch_tower.registry.connection_manager_registry import VendorStatus, registry as connection_manager_registry
from data_models.motion_event import MotionEvent
from db.connection import get_database_connection
from db.repositories.motion_event_repository import MotionEventRepository
from cameras.camera_base import PluginType
from watch_tower.config import config
from utils.error_handler import handle_async_errors

logger = logging.getLogger(__name__)

# Keep track of running tasks
running_upload_tasks: Set[asyncio.Task] = set()
running_facial_recognition_tasks: Set[asyncio.Task] = set()

# Semaphores to limit concurrent operations using config
upload_semaphore = asyncio.Semaphore(config.video.max_concurrent_uploads)
face_recognition_semaphore = asyncio.Semaphore(config.video.max_concurrent_face_recognition)

@handle_async_errors(log_error=True, reraise=False)
async def handle_camera_error(camera: CameraBase) -> None:
    try:
        if not connection_manager_registry.get_connection_manager(camera.plugin_type).is_healthy():
            connection_manager_registry.update_status(camera.plugin_type, VendorStatus.INACTIVE)
            for camera in camera_registry.get_all_by_vendor(camera.plugin_type):
                camera_registry.update_status(camera.plugin_type, camera.camera_name, CameraStatus.INACTIVE)
        else:
            properties = await camera.get_properties()
            camera_registry.update_status(camera.plugin_type, properties["name"], CameraStatus.INACTIVE)

    except Exception as e:
        logger.error(f"Error handling camera error: {e}")
        logger.exception("Full traceback:")

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
            camera_entry.last_polled = current_time
        except Exception as e:
            logger.error(f"Error retrieving motion videos: {e}")
            logger.exception("Full traceback:")
            await handle_camera_error(camera)

def insert_events_into_db(events: List[MotionEvent]) -> None:
    if not events:
        return
        
    engine, session_factory = get_database_connection()
    motion_event_repository = MotionEventRepository()
    
    with session_factory() as session:
        now = datetime.now(timezone.utc)
        future_date = datetime(9999, 12, 31, 23, 59, 59, tzinfo=now.tzinfo)
        
        for event in events:
            event_data: Dict[str, Any] = {
                "event_metadata": {"event_id": event.event_id, "camera_vendor": event.camera_vendor.value},  # Store enum value
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
            # Directly await the coroutine since it's not doing heavy I/O
            await camera.retrieve_video_from_event_and_upload_to_s3(event)
        except Exception as e:
            logger.error(f"Error processing video for event {event.event_id}: {e}")
            logger.exception("Full traceback:")

async def start_facial_recognition_tasks() -> None:
    """Start facial recognition tasks for unprocessed events"""
    try:
        from aws.rekognition.rekognition_service import RekognitionService
        rekognition_service = RekognitionService()
        engine, session_factory = get_database_connection()
        with session_factory() as session:
            motion_event_repository = MotionEventRepository()
            unprocessed_events = motion_event_repository.get_unprocessed_events(session)
            
            for db_event in unprocessed_events:
                # Convert DB event to MotionEvent
                motion_event = MotionEvent(
                    event_id=str(db_event.id),
                    camera_vendor=db_event.event_metadata.get('camera_vendor'),
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
                running_facial_recognition_tasks.add(task)
                task.add_done_callback(running_facial_recognition_tasks.discard)
                
                # Add a small delay between tasks to prevent overwhelming the system
                await asyncio.sleep(0.1)
    except Exception as e:
        logger.error(f"Error starting facial recognition tasks: {e}")
        logger.exception("Full traceback:")


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
    try:
        # Start face search
        face_search_results, was_skipped = await rekognition_service.start_face_search(motion_event.s3_url)
        
        if was_skipped:
            # Job was skipped because it's already running
            logger.info(f"Face search skipped for event {motion_event.event_id} - job already running")
            return
        
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
                    datetime.now(timezone.utc)
                )
        else:
            # Face search completed but found no faces
            logger.info(f"Face search completed for event {motion_event.event_id} - no faces detected")
            
            # Mark the motion event as processed since the search completed
            with session_factory() as session:
                motion_event_repository = MotionEventRepository()
                motion_event_repository.mark_as_processed(
                    session, 
                    db_event.id, 
                    datetime.now(timezone.utc)
                )
            
    except Exception as e:
        logger.error(f"Error processing face search for event {motion_event.event_id}: {e}")
        logger.exception("Full traceback:")


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
                if person_name not in consolidated_results or confidence_score > consolidated_results[person_name]:
                    consolidated_results[person_name] = confidence_score

        with session_factory() as session:
            from db.repositories.visitor_log_repository import VisitorLogRepository
            
            visitor_log_repository = VisitorLogRepository()
            
            # Get camera information
            camera_name = db_event.camera_name
            
            for person_name, max_confidence in consolidated_results.items():
                # Create a single visitor log entry for each person with the max confidence
                visitor_log_data = {
                    "camera_name": camera_name,
                    "persons_name": person_name,
                    "confidence_score": max_confidence,
                    "visited_at": db_event.motion_detected,
                }
                
                visitor_log_repository.create(session, visitor_log_data)
                logger.info(f"Created consolidated visitor log for person '{person_name}' at event {db_event.id} with max confidence {max_confidence}")
                
    except Exception as e:
        logger.error(f"Error creating visitor logs from face search results: {e}")
        logger.exception("Full traceback:")

async def start_video_retrieval_tasks() -> None:
    """Start video retrieval tasks for unprocessed events"""
    try:
        engine, session_factory = get_database_connection()
        with session_factory() as session:
            motion_event_repository = MotionEventRepository()
            unprocessed_events = motion_event_repository.get_unuploaded_events(session)
            
            for db_event in unprocessed_events:
                # Find the camera that created this event
                camera_vendor = db_event.event_metadata.get('camera_vendor')
                camera = camera_registry.get(PluginType(camera_vendor), db_event.camera_name)
                if camera:
                    # Convert DB event to MotionEvent
                    motion_event = MotionEvent(
                        event_id=str(db_event.id),
                        camera_vendor=camera_vendor,
                        camera_name=db_event.camera_name,
                        timestamp=db_event.motion_detected,
                        s3_url=db_event.s3_url if db_event.s3_url else None,
                        event_metadata=db_event.event_metadata  # Copy the event metadata
                    )
                    
                    # Create a task for this video retrieval
                    task = asyncio.create_task(process_video_retrieval(motion_event, camera))
                    running_upload_tasks.add(task)
                    task.add_done_callback(running_upload_tasks.discard)
                    
                    # Add a small delay between tasks to prevent overwhelming the system
                    await asyncio.sleep(0.1)
    except Exception as e:
        logger.error(f"Error starting video retrieval tasks: {e}")
        logger.exception("Full traceback:")

async def events_loop() -> None:
    """Main event loop for processing camera events"""
    while True:
        active_cameras = camera_registry.get_all_active()
        current_time = datetime.now(timezone.utc)
        new_events: List[MotionEvent] = []
        for camera in active_cameras:
            await poll_for_events(camera, current_time, new_events)
        insert_events_into_db(new_events)
        await start_video_retrieval_tasks()
        await start_facial_recognition_tasks()
        await asyncio.sleep(5)