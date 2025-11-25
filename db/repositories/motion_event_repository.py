from typing import Optional, List
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_
from db.models import MotionEvent
from db.repositories.base import BaseRepository
from utils.logging_config import get_logger

logger = get_logger(__name__)


class MotionEventRepository(BaseRepository[MotionEvent]):
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
        from watch_tower.config import get_timezone
        tz = get_timezone()
        now = datetime.now(tz)
        future_date = datetime(9998, 12, 31, 23, 59, 59, tzinfo=now.tzinfo)

        try:
            # Use a single query to get all events at once
            events = db.query(self.model).filter(
                and_(
                    self.model.facial_recognition_processed > now,
                    self.model.uploaded_to_s3 <= now,
                    self.model.s3_url.isnot(None)
                )
            ).all()

            return events

        except Exception as e:
            logger.error(f"Error querying for unprocessed events: {e}")
            logger.exception("Full traceback:")
            raise

    def get_unuploaded_events(self, db: Session) -> List[MotionEvent]:
        """Get all motion events that haven't been uploaded to S3 yet"""
        from watch_tower.config import get_timezone
        tz = get_timezone()
        now = datetime.now(tz)
        future_date = datetime(9998, 12, 31, 23, 59, 59, tzinfo=now.tzinfo)

        try:
            # Use a single query to get all events at once
            events = db.query(self.model).filter(
                self.model.uploaded_to_s3 > now
            ).all()

            return events

        except Exception as e:
            logger.error(f"Error querying for unuploaded events: {e}")
            logger.exception("Full traceback:")
            raise

    def mark_as_processed(
        self,
        db: Session,
        event_id: int,
        processed_time: datetime
    ) -> Optional[MotionEvent]:
        """Mark a motion event as processed by facial recognition"""
        event = self.get(db, event_id)
        if event:
            event.facial_recognition_processed = processed_time
            db.commit()
            db.refresh(event)
        return event

    def update_s3_url(
        self,
        db: Session,
        event_id: int,
        s3_url: str,
        upload_time: datetime
    ) -> Optional[MotionEvent]:
        """Update the S3 URL and upload time for a motion event"""
        event = self.get(db, event_id)
        if event:
            event.s3_url = s3_url
            event.uploaded_to_s3 = upload_time
            db.commit()
            db.refresh(event)
        return event
