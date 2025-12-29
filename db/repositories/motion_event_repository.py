"""Repository for motion event database operations."""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import and_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from db.models import MotionEvent
from db.repositories.base import BaseRepository
from db.exceptions import DatabaseTransactionError
from utils.logging_config import get_logger
from utils.metric_helpers import inc_counter_metric
from utils.metrics import MetricDataPointName
from watch_tower.config import get_timezone

LOGGER = get_logger(__name__)


class MotionEventRepository(BaseRepository[MotionEvent]):
    """Repository for managing motion event database operations."""
    def __init__(self):
        super().__init__(MotionEvent)

    def get_by_camera(self, db: Session, camera_name: str) -> List[MotionEvent]:
        """Get all motion events for a specific camera"""
        return self.get_all_by_field(db, "camera_name", camera_name)

    def get_by_time_range(
            self,
            db: Session,
            start_time: datetime,
            end_time: datetime
    ) -> List[MotionEvent]:
        """Get all motion events within a time range"""
        return db.query(self.model).filter(
            and_(
                self.model.motion_detected >= start_time,
                self.model.motion_detected <= end_time
            )
        ).all()

    def get_by_camera_and_time(
            self,
            db: Session,
            camera_name: str,
            start_time: datetime,
            end_time: datetime
    ) -> List[MotionEvent]:
        """Get motion events for a specific camera within a time range"""
        return db.query(self.model).filter(
            and_(
                self.model.camera_name == camera_name,
                self.model.motion_detected >= start_time,
                self.model.motion_detected <= end_time
            )
        ).all()

    def get_unprocessed_events(self, db: Session) -> List[MotionEvent]:
        """Get all motion events that haven't been processed by facial recognition"""
        timezone_obj = get_timezone()
        now = datetime.now(timezone_obj)

        try:
            events = db.query(self.model).filter(
                and_(
                    self.model.facial_recognition_processed > now,
                    self.model.uploaded_to_s3 <= now,
                    self.model.s3_url.isnot(None)
                )
            ).all()

            return events

        except Exception as e:
            LOGGER.error("Error querying for unprocessed events: %s", e)
            LOGGER.exception("Full traceback:")
            raise

    def get_unuploaded_events(self, db: Session) -> List[MotionEvent]:
        """Get all motion events that haven't been uploaded to S3 yet"""
        timezone_obj = get_timezone()
        now = datetime.now(timezone_obj)

        try:
            events = db.query(self.model).filter(
                self.model.uploaded_to_s3 > now
            ).all()

            return events

        except Exception as e:
            LOGGER.error("Error querying for unuploaded events: %s", e)
            LOGGER.exception("Full traceback:")
            raise

    def mark_as_processed(
            self,
            db: Session,
            event_id: int,
            processed_time: datetime
    ) -> Optional[MotionEvent]:
        """Mark a motion event as processed by facial recognition"""
        table_name = self.model.__table__.name
        event = self.get(db, event_id)
        if event:
            event.facial_recognition_processed = processed_time
            try:
                db.commit()
            except SQLAlchemyError as e:
                db.rollback()
                LOGGER.error(
                    "Failed to mark event %s as processed in table %s: %s",
                    event_id,
                    table_name,
                    str(e),
                    exc_info=True
                )
                inc_counter_metric(
                    MetricDataPointName.DATABASE_TRANSACTION_FAILURE_COUNT,
                    labels={"table": table_name},
                    increment=1,
                )
                raise DatabaseTransactionError(f"Failed to mark event {event_id} as processed in table {table_name}: {str(e)}") from e
            inc_counter_metric(
                MetricDataPointName.DATABASE_TRANSACTION_SUCCESS_COUNT,
                labels={"table": table_name},
                increment=1,
            )
            try:
                db.refresh(event)
            except SQLAlchemyError as e:
                LOGGER.warning(
                    "Failed to refresh event after commit in table %s: %s. "
                    "Update was committed successfully.",
                    table_name,
                    str(e),
                    exc_info=True
                )
                raise
        return event

    def update_s3_url(
            self,
            db: Session,
            event_id: int,
            s3_url: str,
            upload_time: datetime
    ) -> Optional[MotionEvent]:
        """Update the S3 URL and upload time for a motion event"""
        table_name = self.model.__table__.name
        event = self.get(db, event_id)
        if event:
            event.s3_url = s3_url
            event.uploaded_to_s3 = upload_time
            try:
                db.commit()
            except SQLAlchemyError as e:
                db.rollback()
                LOGGER.error(
                    "Failed to update S3 URL for event %s in table %s: %s",
                    event_id,
                    table_name,
                    str(e),
                    exc_info=True
                )
                inc_counter_metric(
                    MetricDataPointName.DATABASE_TRANSACTION_FAILURE_COUNT,
                    labels={"table": table_name},
                    increment=1,
                )
                raise DatabaseTransactionError(f"Failed to update S3 URL for event {event_id} in table {table_name}: {str(e)}") from e
            inc_counter_metric(
                MetricDataPointName.DATABASE_TRANSACTION_SUCCESS_COUNT,
                labels={"table": table_name},
                increment=1,
            )
            try:
                db.refresh(event)
            except SQLAlchemyError as e:
                LOGGER.warning(
                    "Failed to refresh event after commit in table %s: %s. "
                    "Update was committed successfully.",
                    table_name,
                    str(e),
                    exc_info=True
                )
                raise
        return event
