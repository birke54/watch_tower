"""Camera registry module for managing camera instances and their state."""

import datetime
from enum import Enum
from typing import List, Dict, Tuple, Optional, ClassVar
from dataclasses import dataclass
from cameras.camera_base import CameraBase
from connection_managers.plugin_type import PluginType
from utils.logging_config import get_logger
from db.camera_state_db import save_camera_states, load_camera_states

LOGGER = get_logger(__name__)


class CameraStatus(Enum):
    """Enum representing the status of a camera in the registry."""
    ACTIVE = 1
    INACTIVE = 2


@dataclass
class CameraEntry:
    """Data class representing a camera entry in the registry."""
    camera: CameraBase
    status: CameraStatus
    last_polled: datetime.datetime
    status_last_updated: datetime.datetime


class CameraRegistry:
    """Registry for managing camera instances.

    This class implements a singleton pattern to maintain a single registry
    of all cameras in the system. It provides methods to add, remove, and
    retrieve cameras.

    Attributes:
        cameras: Dictionary mapping camera identifiers to camera entries
    """

    _instance: ClassVar[Optional['CameraRegistry']] = None
    _initialized: ClassVar[bool] = False

    def __new__(cls) -> 'CameraRegistry':
        """Get or create the singleton instance of the camera registry.

        Returns:
            CameraRegistry: The singleton instance
        """
        if cls._instance is None:
            cls._instance = super(CameraRegistry, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """Initialize the camera registry if not already initialized."""
        if self._initialized:
            return

        self.cameras: Dict[Tuple[PluginType, str], CameraEntry] = {}
        self._initialized = True
        LOGGER.debug("Camera registry initialized")

    async def add(self, camera: CameraBase) -> None:
        """Add a camera to the registry.

        Args:
            camera: The camera instance to add

        Raises:
            ValueError: If the camera is already registered
            KeyError: If required camera properties are missing
        """
        try:
            properties = await camera.get_properties()
            camera_name = properties.get("name")
            if not camera_name:
                raise KeyError("Camera name not found in properties")

            camera_id = (camera.plugin_type, camera_name)
            if camera_id in self.cameras:
                raise ValueError(f"Camera {camera_name} is already registered")

            self.cameras[camera_id] = CameraEntry(
                camera=camera,
                status=CameraStatus.ACTIVE,
                last_polled=datetime.datetime.now(datetime.timezone.utc),
                status_last_updated=datetime.datetime.now(datetime.timezone.utc)
            )
            LOGGER.debug("Added camera %s to registry", camera_name)

            # Save state to database for cross-process access
            self._save_camera_state_to_database()

        except Exception as e:
            LOGGER.error("Error adding camera to registry: %s", e)
            raise

    def remove(self, vendor: PluginType, camera_name: str) -> None:
        """Remove a camera from the registry.

        Args:
            vendor: The camera vendor
            camera_name: The name of the camera

        Raises:
            KeyError: If the camera is not found in the registry
        """
        try:
            camera_key = (vendor, camera_name)
            if camera_key not in self.cameras:
                raise KeyError(f"Camera {camera_name} not found in registry")

            del self.cameras[camera_key]
            LOGGER.debug("Removed camera %s from registry", camera_name)

            # Save state to database for cross-process access
            self._save_camera_state_to_database()

        except Exception as e:
            LOGGER.error("Error removing camera from registry: %s", e)
            raise

    def get(self, vendor: PluginType, camera_name: str) -> Optional[CameraBase]:
        """Get a camera from the registry.

        Args:
            vendor: The camera vendor
            camera_name: The name of the camera

        Returns:
            Optional[CameraBase]: The camera instance if found, None otherwise
        """
        try:
            camera_key = (vendor, camera_name)
            if camera_key not in self.cameras:
                LOGGER.warning("Camera %s not found in registry", camera_name)
                return None

            return self.cameras[camera_key].camera

        except Exception as e:
            LOGGER.error("Error getting camera from registry: %s", e)
            return None

    def get_all(self) -> List[CameraBase]:
        """Get all cameras from the registry.

        Returns:
            List[CameraBase]: List of all registered cameras
        """
        return [entry.camera for entry in self.cameras.values()]

    def get_all_by_vendor(self, vendor: PluginType) -> List[CameraBase]:
        """Get all cameras by vendor from the registry.

        Returns:
            List[CameraBase]: List of all registered cameras by vendor
        """
        return [entry.camera for entry in self.cameras.values(
        ) if entry.camera.plugin_type == vendor]

    def get_all_active(self) -> List[CameraBase]:
        """Get all active cameras from the registry.

        Returns:
            List[CameraBase]: List of all active cameras
        """
        return [
            entry.camera
            for entry in self.cameras.values()
            if entry.status == CameraStatus.ACTIVE
        ]

    def update_status(
            self,
            vendor: PluginType,
            camera_name: str,
            status: CameraStatus) -> None:
        """Update the status of a camera in the registry.

        Args:
            vendor: The camera vendor
            camera_name: The name of the camera
            status: The new status to set

        Raises:
            KeyError: If the camera is not found in the registry
        """
        try:
            camera_key = (vendor, camera_name)
            if camera_key not in self.cameras:
                raise KeyError(f"Camera {camera_name} not found in registry")

            self.cameras[camera_key].status = status
            self.cameras[camera_key].status_last_updated = datetime.datetime.now(
                datetime.timezone.utc)
            LOGGER.debug("Updated status of camera %s to %s", camera_name, status.name)

            # Save state to database for cross-process access
            self._save_camera_state_to_database()

        except Exception as e:
            LOGGER.error("Error updating camera status: %s", e)
            raise

    def _save_camera_state_to_database(self) -> None:
        """Save the current camera state to SQLite database for cross-process access."""
        try:
            camera_states = []
            for (vendor, camera_name), entry in self.cameras.items():
                camera_states.append({
                    "name": camera_name,
                    "vendor": vendor.value,
                    "status": entry.status.name,
                    "last_polled": entry.last_polled.isoformat(),
                    "status_last_updated": entry.status_last_updated.isoformat()
                })

            save_camera_states(camera_states)
            LOGGER.debug("Saved %d camera states to database", len(camera_states))

        except Exception as e:
            LOGGER.error("Failed to save camera state to database: %s", e)

    @staticmethod
    def _load_camera_state_from_database() -> Dict[Tuple[PluginType, str], CameraEntry]:
        """Load camera states from SQLite database and convert to registry format."""
        camera_states: Dict[Tuple[PluginType, str], CameraEntry] = {}
        try:
            sqlite_camera_states = load_camera_states()
            for entry in sqlite_camera_states:
                try:
                    vendor = PluginType(entry["vendor"])
                    camera_name = entry["name"]
                    status = CameraStatus[entry["status"]]
                    last_polled = (
                        datetime.datetime.fromisoformat(entry["last_polled"])
                        if entry["last_polled"]
                        else datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
                    )
                    status_last_updated = (
                        datetime.datetime.fromisoformat(entry["status_last_updated"])
                        if entry["status_last_updated"]
                        else datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
                    )

                    camera_entry = CameraEntry(
                        camera=None,  # Cannot restore CameraBase instance from DB
                        status=status,
                        last_polled=last_polled,
                        status_last_updated=status_last_updated,
                    )
                    camera_states[(vendor, camera_name)] = camera_entry
                except Exception as trans_e:
                    LOGGER.error("Error transforming db entry %s: %s", entry, trans_e)
            return camera_states
        except Exception as e:
            LOGGER.error("Failed to load camera state from database: %s", e)
            return {}


# Singleton instance of the camera registry
REGISTRY = CameraRegistry()
