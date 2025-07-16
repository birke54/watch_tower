import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime, timezone

from watch_tower.registry.camera_registry import CameraRegistry, CameraStatus, CameraEntry
from cameras.camera_base import CameraBase
from connection_managers.plugin_type import PluginType

@pytest.fixture
def mock_camera() -> Mock:
    """Create a mock camera instance."""
    camera = Mock(spec=CameraBase)
    camera.plugin_type = PluginType.RING
    camera.get_properties = AsyncMock(return_value={"name": "Test Camera"})
    return camera

@pytest.fixture
def registry() -> CameraRegistry:
    """Create a fresh registry instance for each test."""
    # Clear the singleton instance
    CameraRegistry._instance = None
    return CameraRegistry()

class TestCameraRegistry:
    """Test cases for CameraRegistry."""

    def test_singleton_pattern(self) -> None:
        """Test that the registry follows the singleton pattern."""
        registry1 = CameraRegistry()
        registry2 = CameraRegistry()
        assert registry1 is registry2

    @pytest.mark.asyncio
    async def test_add_camera_success(self, registry: CameraRegistry, mock_camera: Mock) -> None:
        """Test successful camera addition."""
        await registry.add(mock_camera)
        assert len(registry.cameras) == 1
        camera_entry = registry.cameras[(PluginType.RING, "Test Camera")]
        assert camera_entry.camera == mock_camera
        assert camera_entry.status == CameraStatus.ACTIVE
        assert isinstance(camera_entry.last_polled, datetime)
        assert isinstance(camera_entry.status_last_updated, datetime)

    @pytest.mark.asyncio
    async def test_add_camera_duplicate(self, registry: CameraRegistry, mock_camera: Mock) -> None:
        """Test adding a duplicate camera."""
        await registry.add(mock_camera)
        with pytest.raises(ValueError, match="Camera Test Camera is already registered"):
            await registry.add(mock_camera)

    @pytest.mark.asyncio
    async def test_add_camera_missing_name(self, registry: CameraRegistry, mock_camera: Mock) -> None:
        """Test adding a camera with missing name property."""
        mock_camera.get_properties.return_value = {}
        with pytest.raises(KeyError, match="Camera name not found in properties"):
            await registry.add(mock_camera)

    def test_remove_camera_success(self, registry: CameraRegistry, mock_camera: Mock) -> None:
        """Test successful camera removal."""
        registry.cameras[(PluginType.RING, "Test Camera")] = CameraEntry(
            camera=mock_camera,
            status=CameraStatus.ACTIVE,
            last_polled=datetime.now(timezone.utc),
            status_last_updated=datetime.now(timezone.utc)
        )
        registry.remove(PluginType.RING, "Test Camera")
        assert len(registry.cameras) == 0

    def test_remove_camera_not_found(self, registry: CameraRegistry) -> None:
        """Test removing a non-existent camera."""
        with pytest.raises(KeyError, match="Camera Test Camera not found in registry"):
            registry.remove(PluginType.RING, "Test Camera")

    def test_get_camera_success(self, registry: CameraRegistry, mock_camera: Mock) -> None:
        """Test successful camera retrieval."""
        registry.cameras[(PluginType.RING, "Test Camera")] = CameraEntry(
            camera=mock_camera,
            status=CameraStatus.ACTIVE,
            last_polled=datetime.now(timezone.utc),
            status_last_updated=datetime.now(timezone.utc)
        )
        camera = registry.get(PluginType.RING, "Test Camera")
        assert camera == mock_camera

    def test_get_camera_not_found(self, registry: CameraRegistry) -> None:
        """Test retrieving a non-existent camera."""
        camera = registry.get(PluginType.RING, "Test Camera")
        assert camera is None

    def test_get_all_cameras(self, registry: CameraRegistry, mock_camera: Mock) -> None:
        """Test retrieving all cameras."""
        registry.cameras[(PluginType.RING, "Test Camera")] = CameraEntry(
            camera=mock_camera,
            status=CameraStatus.ACTIVE,
            last_polled=datetime.now(timezone.utc),
            status_last_updated=datetime.now(timezone.utc)
        )
        cameras = registry.get_all()
        assert len(cameras) == 1
        assert cameras[0] == mock_camera

    def test_get_all_active_cameras(self, registry: CameraRegistry, mock_camera: Mock) -> None:
        """Test retrieving all active cameras."""
        # Add an active camera
        registry.cameras[(PluginType.RING, "Active Camera")] = CameraEntry(
            camera=mock_camera,
            status=CameraStatus.ACTIVE,
            last_polled=datetime.now(timezone.utc),
            status_last_updated=datetime.now(timezone.utc)
        )
        # Add an inactive camera
        inactive_camera = Mock(spec=CameraBase)
        inactive_camera.plugin_type = PluginType.RING
        registry.cameras[(PluginType.RING, "Inactive Camera")] = CameraEntry(
            camera=inactive_camera,
            status=CameraStatus.INACTIVE,
            last_polled=datetime.now(timezone.utc),
            status_last_updated=datetime.now(timezone.utc)
        )
        active_cameras = registry.get_all_active()
        assert len(active_cameras) == 1
        assert active_cameras[0] == mock_camera

    def test_update_status_success(self, registry: CameraRegistry, mock_camera: Mock) -> None:
        """Test successful status update."""
        registry.cameras[(PluginType.RING, "Test Camera")] = CameraEntry(
            camera=mock_camera,
            status=CameraStatus.ACTIVE,
            last_polled=datetime.now(timezone.utc),
            status_last_updated=datetime.now(timezone.utc)
        )
        registry.update_status(PluginType.RING, "Test Camera", CameraStatus.INACTIVE)
        assert registry.cameras[(PluginType.RING, "Test Camera")].status == CameraStatus.INACTIVE

    def test_update_status_not_found(self, registry: CameraRegistry) -> None:
        """Test updating status of non-existent camera."""
        with pytest.raises(KeyError, match="Camera Test Camera not found in registry"):
            registry.update_status(PluginType.RING, "Test Camera", CameraStatus.INACTIVE) 