"""Base repository class for database operations."""

from typing import Any, Dict, Generic, List, Optional, Type, TypeVar

from sqlalchemy.orm import Session

from db.models import BASE

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
        db_obj = self.model(**obj_in)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
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
