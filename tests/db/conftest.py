import pytest
from datetime import datetime, timedelta
from typing import Generator, Dict, Any, Union
from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from db.models import BASE, Vendors, MotionEvent, VisitorLogs
from db.repositories.vendors_repository import VendorsRepository
from db.repositories.motion_event_repository import MotionEventRepository
from db.repositories.visitor_log_repository import VisitorLogRepository

# Test database URL
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="session")
def engine() -> Generator[Engine, None, None]:
    """Create a test database engine"""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    BASE.metadata.create_all(engine)
    yield engine
    BASE.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def db_session(engine: Engine) -> Generator[Session, None, None]:
    """Create a new database session for a test"""
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def vendor_repository() -> VendorsRepository:
    """Create a vendor repository instance"""
    return VendorsRepository()


@pytest.fixture
def motion_event_repository() -> MotionEventRepository:
    """Create a motion event repository instance"""
    return MotionEventRepository()


@pytest.fixture
def visitor_log_repository() -> VisitorLogRepository:
    """Create a visitor log repository instance"""
    return VisitorLogRepository()


@pytest.fixture
def sample_vendor(db_session: Session, vendor_repository: VendorsRepository) -> Vendors:
    """Create a sample vendor for testing"""
    vendor_data: Dict[str, Union[str, bytes]] = {
        "name": "Test Vendor",
        "plugin_type": "RING",
        "username": "test_user",
        "password_enc": b"test_enc"
    }
    return vendor_repository.create(db_session, vendor_data)


@pytest.fixture
def sample_motion_event(
        db_session: Session,
        motion_event_repository: MotionEventRepository) -> MotionEvent:
    """Create a sample motion event for testing"""
    now = datetime.utcnow()
    event_data: Dict[str, Any] = {
        "camera_name": "Test Camera",
        "motion_detected": now,
        "uploaded_to_s3": now + timedelta(seconds=1),
        "facial_recognition_processed": now + timedelta(seconds=2),
        "s3_url": "s3://test-bucket/test-event.jpg"
    }
    return motion_event_repository.create(db_session, event_data)


@pytest.fixture
def sample_visitor_log(
        db_session: Session,
        visitor_log_repository: VisitorLogRepository) -> VisitorLogs:
    """Create a sample visitor log for testing"""
    log_data: Dict[str, Any] = {
        "camera_name": "Test Camera",
        "persons_name": "Test Person",
        "confidence_score": 0.95,
        "visited_at": datetime.utcnow()
    }
    return visitor_log_repository.create(db_session, log_data)
