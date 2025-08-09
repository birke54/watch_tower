import pytest
from datetime import datetime, timedelta
from typing import Dict, Any
from sqlalchemy.orm import Session
from db.models import VendorStatus, PluginType, Vendors
from db.repositories.vendors_repository import VendorsRepository


def test_create_vendor(
    db_session: Session,
    vendor_repository: VendorsRepository
) -> None:
    """Test creating a new vendor"""
    vendor_data: Dict[str, Any] = {
        "name": "New Vendor",
        "plugin_type": "RING",
        "username": "new_user",
        "password_enc": b"new_enc"
    }

    vendor = vendor_repository.create(db_session, vendor_data)

    assert vendor.name == vendor_data["name"]
    assert vendor.plugin_type == PluginType.RING
    assert vendor.username == vendor_data["username"]
    assert vendor.password_enc == vendor_data["password_enc"]
    assert vendor.created_at is not None
    assert vendor.updated_at is not None


def test_get_vendor(
    db_session: Session,
    vendor_repository: VendorsRepository,
    sample_vendor: Vendors
) -> None:
    """Test retrieving a vendor by ID"""
    vendor = vendor_repository.get(db_session, int(sample_vendor.vendor_id))

    assert vendor is not None
    assert vendor.vendor_id == sample_vendor.vendor_id
    assert vendor.name == sample_vendor.name


def test_get_by_name(
    db_session: Session,
    vendor_repository: VendorsRepository,
    sample_vendor: Vendors
) -> None:
    """Test retrieving a vendor by name"""
    vendor = vendor_repository.get_by_name(db_session, str(sample_vendor.name))

    assert vendor is not None
    assert vendor.vendor_id == sample_vendor.vendor_id
    assert vendor.name == sample_vendor.name


def test_get_active_vendors(
    db_session: Session,
    vendor_repository: VendorsRepository,
    sample_vendor: Vendors
) -> None:
    """Test retrieving active vendors"""
    # Create another vendor
    other_vendor_data: Dict[str, Any] = {
        "name": "Other Vendor",
        "plugin_type": "RING",
        "username": "other_user",
        "password_enc": b"test_enc"
    }
    vendor_repository.create(db_session, other_vendor_data)

    vendors = vendor_repository.get_active_vendors(db_session)

    assert len(vendors) == 2
    vendor_ids = [v.vendor_id for v in vendors]
    assert sample_vendor.vendor_id in vendor_ids


def test_get_vendors_by_plugin_type(
    db_session: Session,
    vendor_repository: VendorsRepository,
    sample_vendor: Vendors
) -> None:
    """Test retrieving vendors by plugin type"""
    # Create a vendor with different plugin type
    other_vendor_data: Dict[str, Any] = {
        "name": "Other Vendor",
        "plugin_type": "RING",  # Using RING since it's the only valid enum value
        "username": "other_user",
        "password_enc": b"test_enc"
    }
    vendor_repository.create(db_session, other_vendor_data)

    ring_vendors = vendor_repository.get_vendors_by_plugin_type(db_session, "RING")

    assert len(ring_vendors) == 2  # Now expecting 2 vendors
    vendor_ids = [v.vendor_id for v in ring_vendors]
    assert sample_vendor.vendor_id in vendor_ids


def test_update_token(
    db_session: Session,
    vendor_repository: VendorsRepository,
    sample_vendor: Vendors
) -> None:
    """Test updating vendor token"""
    new_token = "new_token"
    new_expires = datetime.utcnow() + timedelta(hours=1)

    updated_vendor = vendor_repository.update_token(
        db_session,
        int(sample_vendor.vendor_id),
        new_token,
        new_expires
    )

    assert updated_vendor is not None
    assert updated_vendor.token == new_token
    assert updated_vendor.token_expires == new_expires


def test_update_status(
    db_session: Session,
    vendor_repository: VendorsRepository,
    sample_vendor: Vendors
) -> None:
    """Test updating vendor status"""
    updated_vendor = vendor_repository.update_status(
        db_session,
        int(sample_vendor.vendor_id),
        VendorStatus.INACTIVE
    )

    assert updated_vendor is not None
    assert updated_vendor.status == VendorStatus.INACTIVE


def test_delete_vendor(
    db_session: Session,
    vendor_repository: VendorsRepository,
    sample_vendor: Vendors
) -> None:
    """Test deleting a vendor"""
    vendor_repository.delete(db_session, int(sample_vendor.vendor_id))

    deleted_vendor = vendor_repository.get(db_session, int(sample_vendor.vendor_id))
    assert deleted_vendor is None


def test_get_by_nonexistent_vendor_id(db_session, vendor_repository):
    assert vendor_repository.get(db_session, 999999) is None


def test_create_with_missing_required_fields(db_session, vendor_repository):
    # Missing required fields should raise an error
    with pytest.raises(Exception):
        vendor_repository.create(db_session, {
            # 'name' is missing
            "plugin_type": "RING",
            "username": "user",
            "password_enc": "pass"
        })
