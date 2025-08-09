from typing import Optional, List
from sqlalchemy.orm import Session
from db.models import Vendors, VendorStatus
from db.repositories.base import BaseRepository


class VendorsRepository(BaseRepository[Vendors]):
    def __init__(self):
        super().__init__(Vendors)

    def get_by_name(self, db: Session, name: str) -> Optional[Vendors]:
        """Get a vendor by name"""
        return self.get_by_field(db, "name", name)

    def get_active_vendors(self, db: Session) -> List[Vendors]:
        """Get all vendors since status is no longer used"""
        return self.get_all(db)

    def get_vendors_by_plugin_type(
            self,
            db: Session,
            plugin_type: str) -> List[Vendors]:
        """Get all vendors of a specific plugin type"""
        return self.get_all_by_field(db, "plugin_type", plugin_type)

    def update_token(self, db: Session, vendor_id: int, token: str,
                     token_expires: str) -> Optional[Vendors]:
        """Update vendor's token and expiration"""
        return self.update(db, vendor_id, {
            "token": token,
            "token_expires": token_expires
        })

    def update_status(self, db: Session, vendor_id: int,
                      status: VendorStatus) -> Optional[Vendors]:
        """Update vendor's status"""
        return self.update(db, vendor_id, {"status": status})
