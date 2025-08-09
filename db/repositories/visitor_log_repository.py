from typing import List, Dict
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from db.models import VisitorLogs
from db.repositories.base import BaseRepository


class VisitorLogRepository(BaseRepository[VisitorLogs]):
    def __init__(self):
        super().__init__(VisitorLogs)

    def get_by_persons_name(self, db: Session, persons_name: str) -> List[VisitorLogs]:
        """Get all visitor logs for a specific person"""
        return self.get_all_by_field(db, "persons_name", persons_name)

    def get_by_camera_name(self, db: Session, camera_name: str) -> List[VisitorLogs]:
        """Get all visitor logs for a specific camera"""
        return self.get_all_by_field(db, "camera_name", camera_name)

    def get_by_time_range(
        self,
        db: Session,
        start_time: datetime,
        end_time: datetime
    ) -> List[VisitorLogs]:
        """Get all visitor logs within a time range"""
        return db.query(self.model).filter(
            and_(
                self.model.visited_at >= start_time,
                self.model.visited_at <= end_time
            )
        ).all()

    def get_visitor_stats(
        self,
        db: Session,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict]:
        """Get visitor statistics within a time range"""
        return db.query(
            VisitorLogs.persons_name,
            func.count(VisitorLogs.visitor_log_id).label('visit_count'),
            func.avg(VisitorLogs.confidence_score).label('avg_confidence')
        ).filter(
            and_(
                VisitorLogs.visited_at >= start_time,
                VisitorLogs.visited_at <= end_time
            )
        ).group_by(
            VisitorLogs.persons_name
        ).all()

    def get_camera_stats(
        self,
        db: Session,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict]:
        """Get camera statistics within a time range"""
        return db.query(
            VisitorLogs.camera_name,
            func.count(VisitorLogs.visitor_log_id).label('visitor_count'),
            func.avg(VisitorLogs.confidence_score).label('avg_confidence')
        ).filter(
            and_(
                VisitorLogs.visited_at >= start_time,
                VisitorLogs.visited_at <= end_time
            )
        ).group_by(
            VisitorLogs.camera_name
        ).all()

    def get_high_confidence_visits(
        self,
        db: Session,
        confidence_threshold: float
    ) -> List[VisitorLogs]:
        """Get all visitor logs with confidence score above threshold"""
        return db.query(self.model).filter(
            self.model.confidence_score >= confidence_threshold
        ).all()

    def get_recent_entries(self, db: Session, limit: int = 10) -> List[VisitorLogs]:
        """Get the most recent visitor log entries"""
        return db.query(self.model).order_by(
            self.model.visited_at.desc()
        ).limit(limit).all()
