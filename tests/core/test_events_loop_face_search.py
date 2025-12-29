"""Tests for face search functionality in the events loop."""
from datetime import datetime, timedelta
from typing import Callable, Tuple
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from data_models.motion_event import MotionEvent
from watch_tower.core.events_loop import process_face_search_with_visitor_logs
from db.models import BASE
from db.exceptions import DatabaseTransactionError
from db.repositories.motion_event_repository import MotionEventRepository
from db.repositories.visitor_log_repository import VisitorLogRepository
from db.exceptions import DatabaseTransactionError
from cameras.camera_base import PluginType
from utils.metrics import MetricDataPointName as Metric
from aws.exceptions import RekognitionError


@pytest.fixture(scope="module")
def engine():
    """Create a test database engine."""
    db_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    BASE.metadata.create_all(db_engine)
    yield db_engine
    BASE.metadata.drop_all(db_engine)


@pytest.fixture
def session_factory(engine) -> Callable[[], Session]:
    """Return a session factory bound to the test engine."""
    return sessionmaker(bind=engine)


def _seed_motion_event(factory) -> Tuple[MotionEvent, any, datetime]:
    """Create and return a DB event plus its corresponding domain object."""
    repo = MotionEventRepository()
    now = datetime.utcnow()
    future = now + timedelta(hours=1)
    event_data = {
        "camera_name": "Test Camera",
        "motion_detected": now,
        "uploaded_to_s3": now,
        "facial_recognition_processed": future,
        "s3_url": "s3://test-bucket/test-event.mp4",
        "event_metadata": {"camera_vendor": "RING"},
    }
    with factory() as session:
        db_event = repo.create(session, event_data)
        # Detach for use outside session scope
        session.expunge(db_event)
    motion_event = MotionEvent(
        event_id=str(db_event.id),
        camera_vendor=PluginType.RING,
        camera_name=db_event.camera_name,
        timestamp=db_event.motion_detected,
        s3_url=db_event.s3_url,
        event_metadata=db_event.event_metadata,
    )
    return motion_event, db_event, future


@pytest.mark.asyncio
async def test_face_search_rollback_on_rekognition_error(session_factory, monkeypatch):
    """Ensure no DB changes when Rekognition face search raises."""
    motion_event, db_event, original_processed = _seed_motion_event(session_factory)

    inc_mock = Mock()
    monkeypatch.setattr("watch_tower.core.events_loop.inc_counter_metric", inc_mock)

    rekognition_service = Mock()
    rekognition_service.start_face_search = AsyncMock(side_effect=RekognitionError("rekognition failed"))

    with pytest.raises(RekognitionError):
        await process_face_search_with_visitor_logs(
            rekognition_service, motion_event, db_event, session_factory
        )

    inc_mock.assert_any_call(Metric.AWS_REKOGNITION_FACE_SEARCH_ERROR_COUNT)

    # Validate no visitor logs persisted and event not marked processed
    with session_factory() as session:
        visitor_count = session.query(VisitorLogRepository().model).count()
        refreshed = MotionEventRepository().get(session, db_event.id)
        assert visitor_count == 0
        assert refreshed.facial_recognition_processed == original_processed


@pytest.mark.asyncio
async def test_face_search_rollback_on_db_error(session_factory, monkeypatch):
    """Ensure visitor logs and processed flag are rolled back on DB failure."""
    motion_event, db_event, original_processed = _seed_motion_event(session_factory)

    inc_mock = Mock()
    # Patch both event loop and repository inc helper since commit lives there
    monkeypatch.setattr("watch_tower.core.events_loop.inc_counter_metric", inc_mock)
    monkeypatch.setattr("db.repositories.motion_event_repository.inc_counter_metric", inc_mock)

    rekognition_service = Mock()
    rekognition_service.start_face_search = AsyncMock(
        return_value=([{"external_image_id": "Alice", "confidence": 99.0}], False)
    )

    # Force commit to fail
    monkeypatch.setattr(Session, "commit", Mock(side_effect=SQLAlchemyError("db failure")))

    with pytest.raises(DatabaseTransactionError):
        await process_face_search_with_visitor_logs(
            rekognition_service, motion_event, db_event, session_factory
        )

    # Failure metric emitted (labels may vary; check first arg)
    assert any(
        call_args[0][0] == Metric.DATABASE_TRANSACTION_FAILURE_COUNT
        for call_args in inc_mock.call_args_list
    )

    # Validate rollback: no visitor logs and processed flag unchanged
    with session_factory() as session:
        visitor_count = session.query(VisitorLogRepository().model).count()
        refreshed = MotionEventRepository().get(session, db_event.id)
        assert visitor_count == 0
        assert refreshed.facial_recognition_processed == original_processed


@pytest.mark.asyncio
async def test_face_search_success_emits_metrics_and_commits(session_factory, monkeypatch):
    """Happy path emits metrics, creates visitor logs, and marks processed."""
    motion_event, db_event, original_processed = _seed_motion_event(session_factory)

    inc_mock = Mock()
    monkeypatch.setattr("watch_tower.core.events_loop.inc_counter_metric", inc_mock)
    monkeypatch.setattr("db.repositories.motion_event_repository.inc_counter_metric", inc_mock)

    rekognition_service = Mock()
    rekognition_service.start_face_search = AsyncMock(
        return_value=(
            [
                {"external_image_id": "Alice", "confidence": 90.0},
                {"external_image_id": "Bob", "confidence": 80.0},
                {"external_image_id": "Alice", "confidence": 95.0},
            ],
            False,
        )
    )

    await process_face_search_with_visitor_logs(
        rekognition_service, motion_event, db_event, session_factory
    )

    # Metrics: success count and DB transaction success observed
    assert any(
        call_args[0][0] == Metric.AWS_REKOGNITION_FACE_SEARCH_SUCCESS_COUNT
        for call_args in inc_mock.call_args_list
    )
    assert any(
        call_args[0][0] == Metric.DATABASE_TRANSACTION_SUCCESS_COUNT
        for call_args in inc_mock.call_args_list
    )

    with session_factory() as session:
        visitor_entries = session.query(VisitorLogRepository().model).all()
        refreshed = MotionEventRepository().get(session, db_event.id)

        assert len(visitor_entries) == 2  # Alice and Bob
        alice = next(v for v in visitor_entries if v.persons_name == "Alice")
        bob = next(v for v in visitor_entries if v.persons_name == "Bob")
        assert alice.confidence_score == 95.0  # max confidence for Alice
        assert bob.confidence_score == 80.0
        assert refreshed.facial_recognition_processed != original_processed
