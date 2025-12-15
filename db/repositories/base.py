"""Base repository class for database operations."""

from typing import Any, Dict, Generic, List, Optional, Type, TypeVar

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from db.models import BASE
from utils.logging_config import get_logger
from utils.metric_helpers import inc_counter_metric
from utils.metrics import MetricDataPointName

LOGGER = get_logger(__name__)

ModelType = TypeVar("ModelType", bound=BASE)


class BaseRepository(Generic[ModelType]):
    """Base repository providing common database operations."""
    def __init__(self, model: Type[ModelType]):
        self.model = model
        # Get the primary key column name
        self.pk_name = model.__table__.primary_key.columns.keys()[0]

    def get(self, db: Session, record_id: int) -> Optional[ModelType]:
        """Get a single record by ID"""
        return db.query(
            self.model).filter(
                getattr(
                    self.model,
                    self.pk_name) == record_id).first()

    def get_all(self, db: Session, skip: int = 0, limit: int = 100) -> List[ModelType]:
        """Get all records with pagination"""
        return db.query(self.model).offset(skip).limit(limit).all()

    def create(self, db: Session, obj_in: Dict[str, Any]) -> ModelType:
        """Create a new record"""
        table_name = self.model.__table__.name
        db_obj = self.model(**obj_in)
        db.add(db_obj)
        try:
            db.commit()
        except SQLAlchemyError as e:
            db.rollback()
            LOGGER.error(
                "Failed to create record in table %s: %s",
                table_name,
                str(e),
                exc_info=True
            )
            inc_counter_metric(
                MetricDataPointName.DATABASE_TRANSACTION_FAILURE_COUNT,
                labels={"table": table_name},
                increment=1,
            )
            raise
        inc_counter_metric(
            MetricDataPointName.DATABASE_TRANSACTION_SUCCESS_COUNT,
            labels={"table": table_name},
            increment=1,
        )
        try:
            db.refresh(db_obj)
        except SQLAlchemyError as e:
            # Refresh failed but commit succeeded, so data is persisted.
            # Log the error but don't rollback (data is already committed).
            # The session may be in an inconsistent state, but the object exists.
            LOGGER.warning(
                "Failed to refresh object after commit in table %s: %s. "
                "Data was committed successfully.",
                table_name,
                str(e),
                exc_info=True
            )
            # Don't rollback or close - let the caller handle the session
            # The object exists in DB even if refresh failed
            raise
        return db_obj

    def add_to_session(self, db: Session, obj_in: Dict[str, Any]) -> ModelType:
        """
        Create a model instance and add it to the provided session without committing.

        Useful when batching multiple operations in a single transaction and the
        caller manages commit/rollback themselves.
        """
        db_obj = self.model(**obj_in)
        try:
            db.add(db_obj)
        except SQLAlchemyError as e:
            table_name = self.model.__table__.name
            LOGGER.error(
                "Failed to add object to session for table %s: %s",
                table_name,
                str(e),
                exc_info=True
            )
            if db.in_transaction():
                db.rollback()
            raise
        return db_obj

    def update(self, db: Session, record_id: int,
               obj_in: Dict[str, Any]) -> Optional[ModelType]:
        """Update a record"""
        db_obj = self.get(db, record_id)
        if db_obj:
            for key, value in obj_in.items():
                setattr(db_obj, key, value)
            db.commit()
            db.refresh(db_obj)
        return db_obj

    def delete(self, db: Session, record_id: int) -> bool:
        """Delete a record"""
        db_obj = self.get(db, record_id)
        if db_obj:
            db.delete(db_obj)
            db.commit()
            return True
        return False

    def get_by_field(self, db: Session, field: str, value: Any) -> Optional[ModelType]:
        """Get a record by any field"""
        return db.query(self.model).filter(getattr(self.model, field) == value).first()

    def get_all_by_field(self, db: Session, field: str, value: Any) -> List[ModelType]:
        """Get all records matching a field value"""
        return db.query(self.model).filter(getattr(self.model, field) == value).all()

    def count(self, db: Session) -> int:
        """Get total count of records"""
        return db.query(self.model).count()

    def exists(self, db: Session, record_id: int) -> bool:
        """Check if a record exists by ID"""
        return db.query(
            self.model).filter(
                getattr(
                    self.model,
                    self.pk_name) == record_id).first() is not None

    def exists_by_field(self, db: Session, field: str, value: Any) -> bool:
        """Check if a record exists by field value"""
        return self.get_by_field(db, field, value) is not None
