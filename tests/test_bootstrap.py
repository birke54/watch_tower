"""Tests for bootstrap module functionality."""
import importlib
from typing import Generator, List
from unittest.mock import AsyncMock, Mock, patch, PropertyMock

import pytest

from connection_managers.plugin_type import PluginType
from db.models import Vendors
from watch_tower.registry.connection_manager_registry import VendorStatus
from watch_tower.exceptions import RingConnectionManagerError

BOOTSTRAP_MODULE = importlib.import_module('watch_tower.core.bootstrap')


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
    with patch.object(BOOTSTRAP_MODULE, 'SESSION_FACTORY') as mock_factory:
        mock_session = Mock()
        mock_factory.return_value.__enter__.return_value = mock_session
        mock_factory.return_value.__exit__.return_value = None
        yield mock_factory


@pytest.fixture
def mock_camera_registry() -> Generator[Mock, None, None]:
    """Mock the camera registry."""
    with patch.object(BOOTSTRAP_MODULE, 'camera_registry') as mock_registry:
        yield mock_registry


@pytest.fixture
def mock_connection_manager_registry() -> Generator[Mock, None, None]:
    """Mock the connection manager registry."""
    with patch.object(BOOTSTRAP_MODULE, 'connection_manager_registry') as mock_registry:
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
        mock_query = Mock()
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_vendors
        mock_session.query.return_value = mock_query

        # Execute
        result = BOOTSTRAP_MODULE.retrieve_vendors()

        # Verify
        assert result == mock_vendors
        mock_session.query.assert_called_once()

    def test_retrieve_vendors_empty(
            self,
            mock_session_factory: Mock
    ) -> None:
        """Test vendor retrieval with no vendors."""
        # Setup
        mock_session = mock_session_factory.return_value.__enter__.return_value
        mock_query = Mock()
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        mock_session.query.return_value = mock_query

        # Execute
        result = BOOTSTRAP_MODULE.retrieve_vendors()

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
        BOOTSTRAP_MODULE.register_connection_managers(mock_vendors)

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
        await BOOTSTRAP_MODULE.login_to_vendors()

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
        mock_connection_manager.login = AsyncMock(side_effect=RingConnectionManagerError("Login failed"))
        type(mock_connection_manager).plugin_type = PropertyMock(return_value=PluginType.RING)

        mock_connection_manager_registry.get_all_connection_managers.return_value = [
            {
                'connection_manager': mock_connection_manager,
                'status': VendorStatus.INACTIVE
            }
        ]

        # Execute
        await BOOTSTRAP_MODULE.login_to_vendors()

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
        result = await BOOTSTRAP_MODULE.retrieve_cameras()

        # Verify
        assert len(result) == 2
        assert all(isinstance(camera, tuple) for camera in result)
        assert all(camera[0] == PluginType.RING for camera in result)

    @pytest.mark.asyncio
    @patch.object(BOOTSTRAP_MODULE, 'camera_registry')
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
        await BOOTSTRAP_MODULE.add_cameras_to_registry(cameras)

        # Verify
        mock_registry.add.assert_awaited()

    @pytest.mark.asyncio
    @patch.object(BOOTSTRAP_MODULE, 'camera_registry')
    @patch.object(BOOTSTRAP_MODULE, 'retrieve_vendors')
    @patch.object(BOOTSTRAP_MODULE, 'register_connection_managers')
    @patch.object(BOOTSTRAP_MODULE, 'login_to_vendors')
    @patch.object(BOOTSTRAP_MODULE, 'retrieve_cameras')
    @patch.object(BOOTSTRAP_MODULE, 'add_cameras_to_registry')
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
        await BOOTSTRAP_MODULE.bootstrap()

        # Verify
        mock_retrieve_vendors.assert_called_once()
        mock_register_connection_managers.assert_called_once_with(mock_vendors)
        mock_login_to_vendors.assert_awaited_once()
        mock_retrieve_cameras.assert_awaited_once_with()
        mock_add_cameras.assert_awaited_once()
