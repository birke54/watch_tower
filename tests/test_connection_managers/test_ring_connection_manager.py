import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import json
from typing import Generator, Dict, Optional, List, cast

from connection_managers.ring_connection_manager import RingConnectionManager
from connection_managers.plugin_type import PluginType
from watch_tower.registry.connection_manager_registry import VendorStatus as RegistryVendorStatus
from ring_doorbell import Ring, Auth, AuthenticationError, Requires2FAError, RingDoorBell

@pytest.fixture
def mock_vendor() -> Mock:
    """Create a mock vendor object."""
    vendor = Mock()
    vendor.vendor_id = 1
    vendor.plugin_type = PluginType.RING
    vendor.username = "test_user"
    vendor.password_enc = b"encrypted_password"
    vendor.token = None
    return vendor

@pytest.fixture
def mock_auth() -> Mock:
    """Create a mock Auth object."""
    auth = Mock(spec=Auth)
    auth.fetch_token = Mock()
    return auth

@pytest.fixture
def mock_ring() -> Mock:
    """Create a mock Ring object."""
    ring = Mock(spec=Ring)
    ring.update_data = Mock()
    ring.video_devices = Mock(return_value=[])
    ring.create_session = Mock()
    return ring

@pytest.fixture
def mock_vendor_repository() -> Mock:
    """Create a mock VendorsRepository."""
    repo = Mock()
    repo.get_by_field = Mock(return_value=None)  # Default return value
    repo.update_status = Mock()
    repo.update_token = Mock()  # Make sure this is a Mock object
    return repo

@pytest.fixture
def mock_session() -> Mock:
    """Create a mock database session."""
    session = Mock()
    return session

@pytest.fixture
def mock_session_factory(mock_session: Mock) -> MagicMock:
    """Create a mock session factory."""
    factory = MagicMock()
    context = MagicMock()
    context.__enter__.return_value = mock_session
    factory.return_value = context
    return factory

@pytest.fixture
def mock_db_connection(mock_session_factory: MagicMock) -> Generator[Mock, None, None]:
    """Mock the database connection."""
    with patch('connection_managers.ring_connection_manager.get_database_connection') as mock:
        mock.return_value = (None, mock_session_factory)
        yield mock

@pytest.fixture
def mock_registry() -> Generator[Mock, None, None]:
    """Mock the connection manager registry."""
    with patch('connection_managers.ring_connection_manager.registry') as mock:
        mock.connection_managers = {
            PluginType.RING: {
                'status': None,
                'token': None,
                'expires_at': None
            }
        }
        yield mock

@pytest.fixture
def ring_connection_manager(mock_vendor_repository: Mock) -> RingConnectionManager:
    """Create a RingConnectionManager instance with mocked dependencies."""
    with patch('connection_managers.ring_connection_manager.VendorsRepository') as mock:
        mock.return_value = mock_vendor_repository
        manager = RingConnectionManager()
        manager._vendor_repository = mock_vendor_repository  # Explicitly set the repository
        return manager

class TestRingConnectionManager:
    """Test cases for RingConnectionManager."""

    @pytest.mark.asyncio
    async def test_login_success_with_existing_token(
        self,
        ring_connection_manager: RingConnectionManager,
        mock_vendor: Mock,
        mock_auth: Mock,
        mock_ring: Mock,
        mock_db_connection: Mock,
        mock_registry: Mock
    ) -> None:
        """Test successful login with existing valid token."""
        # Setup
        token: Dict[str, float] = {
            'expires_at': (datetime.now() + timedelta(hours=1)).timestamp()
        }
        token_bytes = json.dumps(token).encode('utf-8')
        mock_vendor.token = memoryview(token_bytes)
        ring_connection_manager._vendor_repository.get_by_field = Mock(return_value=mock_vendor)
        
        with patch('connection_managers.ring_connection_manager.Auth', return_value=mock_auth), \
             patch('connection_managers.ring_connection_manager.Ring', return_value=mock_ring):
            
            # Execute
            await ring_connection_manager.login()
            
            # Verify
            assert ring_connection_manager._is_authenticated
            assert ring_connection_manager._ring == mock_ring
            assert ring_connection_manager._auth == mock_auth
            mock_ring.create_session.assert_called_once()
            assert mock_registry.connection_managers[PluginType.RING]['status'] == RegistryVendorStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_login_success_with_credentials(
        self,
        ring_connection_manager: RingConnectionManager,
        mock_vendor: Mock,
        mock_auth: Mock,
        mock_ring: Mock,
        mock_db_connection: Mock,
        mock_registry: Mock
    ) -> None:
        """Test successful login with credentials when no valid token exists."""
        # Setup
        mock_vendor.token = None
        ring_connection_manager._vendor_repository.get_by_field = Mock(return_value=mock_vendor)
        
        with patch('connection_managers.ring_connection_manager.Auth', return_value=mock_auth), \
             patch('connection_managers.ring_connection_manager.Ring', return_value=mock_ring), \
             patch('connection_managers.ring_connection_manager.decrypt', return_value="decrypted_password"):
            
            # Execute
            await ring_connection_manager.login()
            
            # Verify
            assert ring_connection_manager._is_authenticated
            assert ring_connection_manager._ring == mock_ring
            assert ring_connection_manager._auth == mock_auth
            mock_auth.fetch_token.assert_called_once_with("test_user", "decrypted_password")
            assert mock_registry.connection_managers[PluginType.RING]['status'] == RegistryVendorStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_login_with_2fa(
        self,
        ring_connection_manager: RingConnectionManager,
        mock_vendor: Mock,
        mock_auth: Mock,
        mock_ring: Mock,
        mock_db_connection: Mock,
        mock_registry: Mock
    ) -> None:
        """Test login with 2FA requirement."""
        # Setup
        mock_vendor.token = None
        ring_connection_manager._vendor_repository.get_by_field = Mock(return_value=mock_vendor)
        mock_auth.fetch_token.side_effect = [Requires2FAError(), None]
        
        with patch('connection_managers.ring_connection_manager.Auth', return_value=mock_auth), \
             patch('connection_managers.ring_connection_manager.Ring', return_value=mock_ring), \
             patch('connection_managers.ring_connection_manager.decrypt', return_value="decrypted_password"), \
             patch('builtins.input', return_value="123456"):
            
            # Execute
            await ring_connection_manager.login()
            
            # Verify
            assert mock_auth.fetch_token.call_count == 2
            mock_auth.fetch_token.assert_called_with("test_user", "decrypted_password", "123456")

    @pytest.mark.asyncio
    async def test_login_failure(
        self,
        ring_connection_manager: RingConnectionManager,
        mock_vendor: Mock,
        mock_auth: Mock,
        mock_db_connection: Mock
    ) -> None:
        """Test login failure."""
        # Setup
        mock_vendor.token = None
        ring_connection_manager._vendor_repository.get_by_field = Mock(return_value=mock_vendor)
        mock_auth.fetch_token.side_effect = AuthenticationError("Invalid credentials")
        
        with patch('connection_managers.ring_connection_manager.Auth', return_value=mock_auth), \
             patch('connection_managers.ring_connection_manager.decrypt', return_value="decrypted_password"):
            
            # Execute and Verify
            with pytest.raises(Exception):
                await ring_connection_manager.login()

    @pytest.mark.asyncio
    async def test_logout(
        self,
        ring_connection_manager: RingConnectionManager,
        mock_ring: Mock
    ) -> None:
        """Test successful logout."""
        # Setup
        ring_connection_manager._ring = mock_ring
        ring_connection_manager._auth = Mock()
        ring_connection_manager._is_authenticated = True
        
        # Execute
        result = await ring_connection_manager.logout()
        
        # Verify
        assert result
        assert ring_connection_manager._ring is None
        assert ring_connection_manager._auth is None
        assert not ring_connection_manager._is_authenticated

    def test_is_healthy(
        self,
        ring_connection_manager: RingConnectionManager,
        mock_ring: Mock
    ) -> None:
        """Test health check."""
        # Setup
        ring_connection_manager._ring = mock_ring
        ring_connection_manager._is_authenticated = True
        
        # Execute
        result = ring_connection_manager.is_healthy()
        
        # Verify
        assert result
        mock_ring.update_data.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_cameras_success(
        self,
        ring_connection_manager: RingConnectionManager,
        mock_ring: Mock
    ) -> Optional[List[RingDoorBell]]:
        """Test successful camera retrieval."""
        # Setup
        mock_cameras = [Mock(spec=RingDoorBell), Mock(spec=RingDoorBell)]
        mock_ring.video_devices.return_value = mock_cameras
        ring_connection_manager._ring = mock_ring
        ring_connection_manager._is_authenticated = True
        
        # Execute
        result = await ring_connection_manager.get_cameras()
        
        # Verify
        assert result == mock_cameras
        mock_ring.update_data.assert_called_once()
        mock_ring.video_devices.assert_called_once()
        return cast(Optional[List[RingDoorBell]], result)

    @pytest.mark.asyncio
    async def test_get_cameras_not_authenticated(
        self,
        ring_connection_manager: RingConnectionManager
    ) -> None:
        """Test camera retrieval when not authenticated."""
        # Setup
        ring_connection_manager._is_authenticated = False
        
        # Execute
        result = await ring_connection_manager.get_cameras()
        
        # Verify
        assert result is None

    def test_token_updated(
        self,
        ring_connection_manager: RingConnectionManager,
        mock_vendor_repository: Mock,
        mock_db_connection: Mock,
        mock_registry: Mock
    ) -> None:
        """Test token update callback."""
        # Setup
        token: Dict[str, float] = {
            'expires_at': (datetime.now() + timedelta(hours=1)).timestamp()
        }
        vendor_id = 1
        mock_session = Mock()
        
        # Execute
        ring_connection_manager.token_updated(token, vendor_id)
        
        # Verify
        mock_vendor_repository.update_token.assert_called_once()
        call_args = mock_vendor_repository.update_token.call_args[0]
        assert len(call_args) == 4  # session, vendor_id, token_str, expires_at
        assert call_args[1] == vendor_id
        assert json.loads(call_args[2]) == token
        assert mock_registry.connection_managers[PluginType.RING]['token'] == token
        assert mock_registry.connection_managers[PluginType.RING]['expires_at'] == datetime.fromtimestamp(token['expires_at']) 