import pytest
from datetime import datetime, timedelta, timezone
from typing import Dict, Any
from sqlalchemy.orm import Session
from db.repositories.motion_event_repository import MotionEventRepository
from db.models import MotionEvent


def test_create_motion_event(
    db_session: Session,
    motion_event_repository: MotionEventRepository
) -> None:
    """Test creating a new motion event"""
    now = datetime.utcnow()
    event_data: Dict[str, Any] = {
        "camera_name": "Test Camera",
        "motion_detected": now,
        "uploaded_to_s3": now,
        "facial_recognition_processed": now,
        "s3_url": "https://test-bucket.s3.amazonaws.com/new-event.jpg",
        "event_metadata": {"test_key": "test_value"}
    }

    event = motion_event_repository.create(db_session, event_data)

    assert event.camera_name == "Test Camera"
    assert event.motion_detected == now
    assert event.uploaded_to_s3 == now
    assert event.facial_recognition_processed == now
    assert event.s3_url == "https://test-bucket.s3.amazonaws.com/new-event.jpg"
    assert event.created_at is not None
    assert event.updated_at is not None
    assert event.event_metadata == {"test_key": "test_value"}


def test_get_motion_event(
    db_session: Session,
    motion_event_repository: MotionEventRepository,
    sample_motion_event: MotionEvent
) -> None:
    """Test retrieving a motion event by ID"""
    event = motion_event_repository.get(db_session, int(sample_motion_event.id))

    assert event is not None
    assert event.id == sample_motion_event.id
    assert event.camera_name == sample_motion_event.camera_name
    assert event.event_metadata == sample_motion_event.event_metadata


def test_get_by_camera(
    db_session: Session,
    motion_event_repository: MotionEventRepository,
    sample_motion_event: MotionEvent
) -> None:
    """Test retrieving motion events by camera"""
    events = motion_event_repository.get_by_camera(
        db_session,
        "Test Camera"
    )

    assert len(events) == 1
    assert events[0].id == sample_motion_event.id
    assert events[0].camera_name == "Test Camera"
    assert events[0].event_metadata == sample_motion_event.event_metadata


def test_get_by_time_range(
    db_session: Session,
    motion_event_repository: MotionEventRepository,
    sample_motion_event: MotionEvent
) -> None:
    """Test retrieving motion events by time range"""
    event_time = datetime.fromisoformat(str(sample_motion_event.motion_detected))
    start_time = event_time - timedelta(hours=1)
    end_time = event_time + timedelta(hours=1)

    events = motion_event_repository.get_by_time_range(
        db_session,
        start_time,
        end_time
    )

    assert len(events) == 1
    assert events[0].id == sample_motion_event.id
    assert start_time <= events[0].motion_detected <= end_time
    assert events[0].event_metadata == sample_motion_event.event_metadata


def test_get_by_camera_and_time(
    db_session: Session,
    motion_event_repository: MotionEventRepository,
    sample_motion_event: MotionEvent
) -> None:
    """Test retrieving motion events by camera and time range"""
    event_time = datetime.fromisoformat(str(sample_motion_event.motion_detected))
    start_time = event_time - timedelta(hours=1)
    end_time = event_time + timedelta(hours=1)

    events = motion_event_repository.get_by_camera_and_time(
        db_session,
        "Test Camera",
        start_time,
        end_time
    )

    assert len(events) == 1
    assert events[0].id == sample_motion_event.id
    assert events[0].camera_name == "Test Camera"
    assert start_time <= events[0].motion_detected <= end_time
    assert events[0].event_metadata == sample_motion_event.event_metadata


def test_get_unprocessed_events(
    db_session: Session,
    motion_event_repository: MotionEventRepository,
    sample_motion_event: MotionEvent
) -> None:
    """Test retrieving unprocessed motion events"""
    # Create an unprocessed event
    pacific_tz = timezone(timedelta(hours=-8))  # PST
    now = datetime.now(pacific_tz)
    future_time = now + timedelta(days=1)  # Use a future time to indicate unprocessed
    unprocessed_event_data: Dict[str, Any] = {
        "camera_name": "Test Camera",
        "motion_detected": now,
        "uploaded_to_s3": now,
        "facial_recognition_processed": future_time,  # Future time indicates unprocessed
        "s3_url": "https://test-bucket.s3.amazonaws.com/unprocessed.jpg",
        "event_metadata": {"unprocessed": True}
    }
    created_event = motion_event_repository.create(db_session, unprocessed_event_data)

    unprocessed_events = motion_event_repository.get_unprocessed_events(db_session)

    # Verify our newly created event is in the results
    assert any(event.id == created_event.id for event in unprocessed_events)
    # Verify the event has the correct data
    found_event = next(
        event for event in unprocessed_events if event.id == created_event.id)
    assert found_event.s3_url == "https://test-bucket.s3.amazonaws.com/unprocessed.jpg"
    assert found_event.event_metadata == {"unprocessed": True}


def test_mark_as_processed(
    db_session: Session,
    motion_event_repository: MotionEventRepository,
    sample_motion_event: MotionEvent
) -> None:
    """Test marking a motion event as processed"""
    processed_time = datetime.now()
    updated_event = motion_event_repository.mark_as_processed(
        db_session,
        int(sample_motion_event.id),
        processed_time
    )

    assert updated_event is not None
    assert updated_event.facial_recognition_processed == processed_time


def test_update_s3_url(
    db_session: Session,
    motion_event_repository: MotionEventRepository,
    sample_motion_event: MotionEvent
) -> None:
    """Test updating motion event S3 URL"""
    new_url = "https://test-bucket.s3.amazonaws.com/updated.jpg"
    upload_time = datetime.now()

    updated_event = motion_event_repository.update_s3_url(
        db_session,
        int(sample_motion_event.id),
        new_url,
        upload_time
    )

    assert updated_event is not None
    assert updated_event.s3_url == new_url
    assert updated_event.uploaded_to_s3 == upload_time


def test_delete_motion_event(
    db_session: Session,
    motion_event_repository: MotionEventRepository,
    sample_motion_event: MotionEvent
) -> None:
    """Test deleting a motion event"""
    result = motion_event_repository.delete(db_session, int(sample_motion_event.id))

    assert result is True
    deleted_event = motion_event_repository.get(db_session, int(sample_motion_event.id))
    assert deleted_event is None


def test_get_by_nonexistent_id(db_session, motion_event_repository):
    assert motion_event_repository.get(db_session, 999999) is None


def test_create_with_missing_required_fields(db_session, motion_event_repository):
    # Missing required fields should raise an error
    with pytest.raises(Exception):
        motion_event_repository.create(db_session, {
            # 'camera_name' is missing
            "motion_detected": "2024-01-01T00:00:00Z",
            "uploaded_to_s3": "2024-01-01T00:00:00Z",
            "facial_recognition_processed": "2024-01-01T00:00:00Z",
            "s3_url": "test"
        })
