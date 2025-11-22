import pytest
from unittest.mock import Mock, AsyncMock, patch, PropertyMock
from typing import List, Generator
import importlib

bootstrap_module = importlib.import_module('watch_tower.core.bootstrap')
from watch_tower.registry.connection_manager_registry import VendorStatus
from db.models import Vendors
from connection_managers.plugin_type import PluginType


@pytest.fixture
def mock_vendors() -> List[Vendors]:
    """Create mock vendors for testing."""
    vendor1 = Mock(spec=Vendors)
    vendor1.vendor_id = 1
    vendor1.name = "Test Vendor 1"
    vendor1.plugin_type = PluginType.RING

    vendor2 = Mock(spec=Vendors)
    vendor2.vendor_id = 2
    vendor2.name = "Test Vendor 2"
    vendor2.plugin_type = PluginType.RING

    return [vendor1, vendor2]


@pytest.fixture
def mock_session_factory() -> Generator[Mock, None, None]:
    """Mock the session factory."""
    with patch.object(bootstrap_module, 'SESSION_FACTORY') as mock_factory:
        mock_session = Mock()
        mock_factory.return_value.__enter__.return_value = mock_session
        mock_factory.return_value.__exit__.return_value = None
        yield mock_factory


@pytest.fixture
def mock_camera_registry() -> Generator[Mock, None, None]:
    """Mock the camera registry."""
    with patch.object(bootstrap_module, 'camera_registry') as mock_registry:
        yield mock_registry


@pytest.fixture
def mock_connection_manager_registry() -> Generator[Mock, None, None]:
    """Mock the connection manager registry."""
    with patch.object(bootstrap_module, 'connection_manager_registry') as mock_registry:
        mock_registry.get_all_connection_managers.return_value = [
            {
                'connection_manager': Mock(),
                'status': VendorStatus.ACTIVE
            }
        ]
        yield mock_registry


class TestBootstrap:
    """Test the bootstrap module."""

    def test_retrieve_vendors_success(
        self,
        mock_session_factory: Mock,
        mock_vendors: List[Vendors]
    ) -> None:
        """Test successful vendor retrieval."""
        # Setup
        mock_session = mock_session_factory.return_value.__enter__.return_value
        mock_session.query.return_value.all.return_value = mock_vendors

        # Execute
        result = bootstrap_module.retrieve_vendors()

        # Verify
        assert result == mock_vendors
        mock_session.query.assert_called_once_with(Vendors)

    def test_retrieve_vendors_empty(self, mock_session_factory: Mock) -> None:
        """Test vendor retrieval with no vendors."""
        # Setup
        mock_session = mock_session_factory.return_value.__enter__.return_value
        mock_session.query.return_value.all.return_value = []

        # Execute
        result = bootstrap_module.retrieve_vendors()

        # Verify
        assert result == []

    @patch('connection_managers.connection_manager_factory.ConnectionManagerFactory')
    def test_register_connection_managers(
        self,
        mock_factory: Mock,
        mock_vendors: List[Vendors]
    ) -> None:
        """Test connection manager registration."""
        # Setup
        mock_factory_instance = Mock()
        mock_factory.create.return_value = mock_factory_instance
        mock_factory.return_value = mock_factory_instance

        # Execute
        bootstrap_module.register_connection_managers(mock_vendors)

        # Verify
        assert mock_factory.create.call_count == len(mock_vendors)

    @pytest.mark.asyncio
    async def test_login_to_vendors_success(
        self,
        mock_connection_manager_registry: Mock
    ) -> None:
        """Test successful vendor login."""
        # Setup
        mock_connection_manager = Mock()
        mock_connection_manager.login = AsyncMock()
        type(mock_connection_manager).plugin_type = PropertyMock(return_value=PluginType.RING)

        mock_connection_manager_registry.get_all_connection_managers.return_value = [
            {
                'connection_manager': mock_connection_manager,
                'status': VendorStatus.ACTIVE
            }
        ]

        # Execute
        # vendors list not used in current implementation
        await bootstrap_module.login_to_vendors()

        # Verify
        mock_connection_manager.login.assert_called_once()

    @pytest.mark.asyncio
    async def test_login_to_vendors_failure(
        self,
        mock_connection_manager_registry: Mock
    ) -> None:
        """Test vendor login with failure."""
        # Setup
        mock_connection_manager = Mock()
        mock_connection_manager.login = AsyncMock(side_effect=Exception("Login failed"))
        type(mock_connection_manager).plugin_type = PropertyMock(return_value=PluginType.RING)

        mock_connection_manager_registry.get_all_connection_managers.return_value = [
            {
                'connection_manager': mock_connection_manager,
                'status': VendorStatus.INACTIVE
            }
        ]

        # Execute
        await bootstrap_module.login_to_vendors()

        # Verify
        mock_connection_manager.login.assert_called_once()
        # Status should remain INACTIVE (default), no update_status call needed
        mock_connection_manager_registry.update_status.assert_not_called()

    @pytest.mark.asyncio
    async def test_retrieve_cameras_success(
        self,
        mock_connection_manager_registry: Mock
    ) -> None:
        """Test successful camera retrieval."""
        # Setup
        mock_connection_manager = Mock()
        mock_connection_manager.get_cameras = AsyncMock(return_value=[Mock(), Mock()])
        type(mock_connection_manager).plugin_type = PropertyMock(return_value=PluginType.RING)

        mock_connection_manager_registry.get_all_connection_managers.return_value = [
            {
                'connection_manager': mock_connection_manager,
                'status': VendorStatus.ACTIVE
            }
        ]

        # Execute
        result = await bootstrap_module.retrieve_cameras()

        # Verify
        assert len(result) == 2
        assert all(isinstance(camera, tuple) for camera in result)
        assert all(camera[0] == PluginType.RING for camera in result)

    @pytest.mark.asyncio
    @patch.object(bootstrap_module, 'camera_registry')
    async def test_add_cameras_to_registry(
        self,
        mock_registry,
        mock_camera_registry: Mock
    ) -> None:
        """Test adding cameras to registry."""
        # Setup
        mock_camera = Mock()
        mock_registry.add = AsyncMock()
        cameras = [(PluginType.RING, mock_camera)]

        # Execute
        await bootstrap_module.add_cameras_to_registry(cameras)

        # Verify
        mock_registry.add.assert_awaited()

    @pytest.mark.asyncio
    @patch.object(bootstrap_module, 'camera_registry')
    @patch.object(bootstrap_module, 'retrieve_vendors')
    @patch.object(bootstrap_module, 'register_connection_managers')
    @patch.object(bootstrap_module, 'login_to_vendors')
    @patch.object(bootstrap_module, 'retrieve_cameras')
    @patch.object(bootstrap_module, 'add_cameras_to_registry')
    async def test_bootstrap_integration(
        self,
        mock_add_cameras,
        mock_retrieve_cameras,
        mock_login_to_vendors,
        mock_register_connection_managers,
        mock_retrieve_vendors,
        mock_registry,
        mock_session_factory: Mock,
        mock_vendors: List[Vendors],
        mock_connection_manager_registry: Mock,
        mock_camera_registry: Mock
    ) -> None:
        """Test bootstrap integration."""
        # Setup
        mock_retrieve_vendors.return_value = mock_vendors
        mock_retrieve_cameras.return_value = [(PluginType.RING, Mock())]
        mock_login_to_vendors.return_value = None
        mock_register_connection_managers.return_value = None
        mock_add_cameras.return_value = None

        # Execute
        await bootstrap_module.bootstrap()

        # Verify
        mock_retrieve_vendors.assert_called_once()
        mock_register_connection_managers.assert_called_once_with(mock_vendors)
        mock_login_to_vendors.assert_awaited_once()
        mock_retrieve_cameras.assert_awaited_once_with()
        mock_add_cameras.assert_awaited_once()
