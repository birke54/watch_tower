from datetime import datetime
from typing import Dict, Any
from sqlalchemy.orm import Session
from db.models import VisitorLogs
from db.repositories.visitor_log_repository import VisitorLogRepository
import datetime


def test_create_visitor_log(
    db_session: Session,
    visitor_log_repository: VisitorLogRepository
) -> None:
    """Test creating a new visitor log"""
    now = datetime.datetime.utcnow()
    log_data: Dict[str, Any] = {
        "camera_name": "Test Camera",
        "persons_name": "Test Person",
        "confidence_score": 0.98,
        "visited_at": now
    }

    log = visitor_log_repository.create(db_session, log_data)

    assert log.camera_name == "Test Camera"
    assert log.persons_name == "Test Person"
    assert log.confidence_score == 0.98
    assert log.visited_at == now
    assert log.created_at is not None


def test_get_visitor_log(
    db_session: Session,
    visitor_log_repository: VisitorLogRepository,
    sample_visitor_log: VisitorLogs
) -> None:
    """Test retrieving a visitor log by ID"""
    log = visitor_log_repository.get(db_session, int(sample_visitor_log.visitor_log_id))

    assert log is not None
    assert log.visitor_log_id == sample_visitor_log.visitor_log_id
    assert log.camera_name == sample_visitor_log.camera_name


def test_get_by_persons_name(
    db_session: Session,
    visitor_log_repository: VisitorLogRepository,
    sample_visitor_log: VisitorLogs
) -> None:
    """Test retrieving visitor logs by person"""
    logs = visitor_log_repository.get_by_persons_name(
        db_session,
        "Test Person"
    )

    assert len(logs) == 1
    assert logs[0].visitor_log_id == sample_visitor_log.visitor_log_id
    assert logs[0].persons_name == "Test Person"
    assert logs[0].camera_name == sample_visitor_log.camera_name


def test_get_by_camera_name(
    db_session: Session,
    visitor_log_repository: VisitorLogRepository,
    sample_visitor_log: VisitorLogs
) -> None:
    """Test retrieving visitor logs by camera"""
    logs = visitor_log_repository.get_by_camera_name(
        db_session,
        "Test Camera"
    )

    assert len(logs) == 1
    assert logs[0].visitor_log_id == sample_visitor_log.visitor_log_id
    assert logs[0].camera_name == "Test Camera"


def test_get_by_time_range(
    db_session: Session,
    visitor_log_repository: VisitorLogRepository,
    sample_visitor_log: VisitorLogs
) -> None:
    """Test retrieving visitor logs by time range"""
    event_time = datetime.datetime.fromisoformat(str(sample_visitor_log.visited_at))
    start_time = event_time - datetime.timedelta(hours=1)
    end_time = event_time + datetime.timedelta(hours=1)

    logs = visitor_log_repository.get_by_time_range(
        db_session,
        start_time,
        end_time
    )

    assert len(logs) == 1
    assert logs[0].visitor_log_id == sample_visitor_log.visitor_log_id
    assert start_time <= logs[0].visited_at <= end_time
    assert logs[0].camera_name == sample_visitor_log.camera_name


def test_get_visitor_stats(
    db_session: Session,
    visitor_log_repository: VisitorLogRepository,
    sample_visitor_log: VisitorLogs
) -> None:
    """Test retrieving visitor statistics"""
    event_time = datetime.datetime.fromisoformat(str(sample_visitor_log.visited_at))
    start_time = event_time - datetime.timedelta(hours=1)
    end_time = event_time + datetime.timedelta(hours=1)

    stats = visitor_log_repository.get_visitor_stats(
        db_session,
        start_time,
        end_time
    )

    assert len(stats) == 1
    # Access the result as a tuple (name, visit_count, avg_confidence)
    assert stats[0][0] == 'Test Person'  # name
    assert stats[0][1] == 1  # visit_count
    assert stats[0][2] == sample_visitor_log.confidence_score  # avg_confidence


def test_get_camera_stats(
    db_session: Session,
    visitor_log_repository: VisitorLogRepository,
    sample_visitor_log: VisitorLogs
) -> None:
    """Test retrieving camera statistics"""
    event_time = datetime.datetime.fromisoformat(str(sample_visitor_log.visited_at))
    start_time = event_time - datetime.timedelta(hours=1)
    end_time = event_time + datetime.timedelta(hours=1)

    stats = visitor_log_repository.get_camera_stats(
        db_session,
        start_time,
        end_time
    )

    assert len(stats) == 1
    # Access the result as a tuple (name, visitor_count, avg_confidence)
    assert stats[0][0] == 'Test Camera'  # name
    assert stats[0][1] == 1  # visitor_count
    assert stats[0][2] == sample_visitor_log.confidence_score  # avg_confidence


def test_get_high_confidence_visits(
    db_session: Session,
    visitor_log_repository: VisitorLogRepository,
    sample_visitor_log: VisitorLogs
) -> None:
    """Test retrieving high confidence visits"""
    # Create a low confidence visit
    low_confidence_log_data: Dict[str, Any] = {
        "camera_name": sample_visitor_log.camera_name,
        "persons_name": sample_visitor_log.persons_name,
        "confidence_score": 0.5,
        "visited_at": datetime.datetime.now()
    }
    visitor_log_repository.create(db_session, low_confidence_log_data)

    high_confidence_logs = visitor_log_repository.get_high_confidence_visits(
        db_session,
        0.8
    )

    assert len(high_confidence_logs) == 1
    assert high_confidence_logs[0].visitor_log_id == sample_visitor_log.visitor_log_id
    assert high_confidence_logs[0].confidence_score > 0.8
    assert high_confidence_logs[0].camera_name == sample_visitor_log.camera_name


def test_delete_visitor_log(
    db_session: Session,
    visitor_log_repository: VisitorLogRepository,
    sample_visitor_log: VisitorLogs
) -> None:
    """Test deleting a visitor log"""
    result = visitor_log_repository.delete(
        db_session, int(sample_visitor_log.visitor_log_id))

    assert result is True
    deleted_log = visitor_log_repository.get(
        db_session, int(sample_visitor_log.visitor_log_id))
    assert deleted_log is None


def test_get_by_nonexistent_visitor_log_id(db_session, visitor_log_repository):
    assert visitor_log_repository.get(db_session, 999999) is None
