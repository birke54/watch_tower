"""
DB models package initialization.
"""

from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, Enum, JSON, DateTime, func, Index, Float, LargeBinary
import enum

from connection_managers.plugin_type import PluginType

Base = declarative_base()


class VendorStatus(enum.Enum):
    """Vendor status enumeration."""
    ACTIVE = 1
    INACTIVE = 2


class Vendors(Base):
    __tablename__ = 'vendors'

    vendor_id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    plugin_type = Column(Enum(PluginType), nullable=True)
    username = Column(String, nullable=False)
    password_enc = Column(String, nullable=False)
    token = Column(LargeBinary)  # bytea type in PostgreSQL
    token_expires = Column(DateTime(timezone=True))
    status = Column(Enum(VendorStatus), nullable=True)
    auth_data = Column(JSON, nullable=False, default={})
    created_at = Column(
        DateTime(
            timezone=True),
        server_default=func.now(),
        nullable=False)
    updated_at = Column(
        DateTime(
            timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False)


class MotionEvent(Base):
    __tablename__ = 'motion_events'

    id = Column(Integer, primary_key=True)
    camera_name = Column(String, nullable=False)
    motion_detected = Column(DateTime(timezone=True), nullable=False)
    uploaded_to_s3 = Column(DateTime(timezone=True), nullable=False)
    facial_recognition_processed = Column(DateTime(timezone=True), nullable=False)
    # Can be null as shown in database screenshot
    s3_url = Column(String, nullable=True)
    created_at = Column(
        DateTime(
            timezone=True),
        server_default=func.now(),
        nullable=False)
    updated_at = Column(
        DateTime(
            timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False)
    event_metadata = Column(JSON, nullable=False, default={})

    # Indexes
    __table_args__ = (
        Index('idx_motion_events_camera_time', 'camera_name', 'motion_detected'),
    )


class VisitorLogs(Base):
    __tablename__ = 'visitor_logs'

    visitor_log_id = Column(Integer, primary_key=True)
    camera_name = Column(String, nullable=False)
    persons_name = Column(String, nullable=False)
    confidence_score = Column(Float, nullable=False)
    visited_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(
        DateTime(
            timezone=True),
        server_default=func.now(),
        nullable=False)
