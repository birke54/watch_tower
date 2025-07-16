import pytest
from unittest.mock import Mock
from datetime import datetime, timezone, timedelta

from watch_tower.registry.connection_manager_registry import ConnectionManagerRegistry, VendorStatus
from connection_managers.plugin_type import PluginType
from connection_managers.connection_manager_base import ConnectionManagerBase

@pytest.fixture
def mock_connection_manager() -> Mock:
    """Create a mock connection manager instance."""
    manager = Mock(spec=ConnectionManagerBase)
    return manager

@pytest.fixture
def registry() -> ConnectionManagerRegistry:
    """Create a fresh registry instance for each test."""
    # Clear the singleton instance
    if hasattr(ConnectionManagerRegistry, 'instance'):
        delattr(ConnectionManagerRegistry, 'instance')
    return ConnectionManagerRegistry()

class TestConnectionManagerRegistry:
    """Test cases for ConnectionManagerRegistry."""

    def test_singleton_pattern(self) -> None:
        """Test that the registry follows the singleton pattern."""
        registry1 = ConnectionManagerRegistry()
        registry2 = ConnectionManagerRegistry()
        assert registry1 is registry2

    def test_register_connection_manager(self, registry: ConnectionManagerRegistry, mock_connection_manager: Mock) -> None:
        """Test registering a connection manager."""
        registry.register_connection_manager(PluginType.RING, mock_connection_manager)
        
        # Verify the connection manager was registered correctly
        assert PluginType.RING in registry.connection_managers
        entry = registry.connection_managers[PluginType.RING]
        assert entry['connection_manager'] == mock_connection_manager
        assert entry['status'] == VendorStatus.INACTIVE
        assert entry['token'] is None
        assert entry['expires_at'] is None

    def test_register_connection_manager_overwrite(self, registry: ConnectionManagerRegistry, mock_connection_manager: Mock) -> None:
        """Test overwriting an existing connection manager."""
        # Register first manager
        registry.register_connection_manager(PluginType.RING, mock_connection_manager)
        
        # Create and register a new manager
        new_manager = Mock(spec=ConnectionManagerBase)
        registry.register_connection_manager(PluginType.RING, new_manager)
        
        # Verify the new manager replaced the old one
        assert registry.connection_managers[PluginType.RING]['connection_manager'] == new_manager

    def test_get_connection_manager_success(self, registry: ConnectionManagerRegistry, mock_connection_manager: Mock) -> None:
        """Test successful retrieval of a connection manager."""
        registry.register_connection_manager(PluginType.RING, mock_connection_manager)
        manager = registry.get_connection_manager(PluginType.RING)
        assert manager == mock_connection_manager

    def test_get_connection_manager_not_found(self, registry: ConnectionManagerRegistry) -> None:
        """Test retrieving a non-existent connection manager."""
        with pytest.raises(KeyError):
            registry.get_connection_manager(PluginType.RING)

    def test_get_all_connection_managers(self, registry: ConnectionManagerRegistry, mock_connection_manager: Mock) -> None:
        """Test retrieving all connection managers."""
        # Register managers for different plugin types
        registry.register_connection_manager(PluginType.RING, mock_connection_manager)
        
        # Create and register another manager with the same plugin type
        other_manager = Mock(spec=ConnectionManagerBase)
        registry.register_connection_manager(PluginType.RING, other_manager)
        
        # Get all managers
        managers = registry.get_all_connection_managers()
        
        # Verify results
        assert len(managers) == 1  # Should only have one entry since we overwrote the first one
        assert managers[0]['connection_manager'] == other_manager  # Should be the second manager we registered

    def test_connection_manager_status(self, registry: ConnectionManagerRegistry, mock_connection_manager: Mock) -> None:
        """Test connection manager status tracking."""
        registry.register_connection_manager(PluginType.RING, mock_connection_manager)
        
        # Verify initial status
        assert registry.connection_managers[PluginType.RING]['status'] == VendorStatus.INACTIVE
        
        # Update status
        registry.connection_managers[PluginType.RING]['status'] = VendorStatus.ACTIVE
        
        # Verify updated status
        assert registry.connection_managers[PluginType.RING]['status'] == VendorStatus.ACTIVE

    def test_connection_manager_token(self, registry: ConnectionManagerRegistry, mock_connection_manager: Mock) -> None:
        """Test connection manager token tracking."""
        registry.register_connection_manager(PluginType.RING, mock_connection_manager)
        
        # Set token and expiration
        token = "test_token"
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        
        registry.connection_managers[PluginType.RING]['token'] = token
        registry.connection_managers[PluginType.RING]['expires_at'] = expires_at
        
        # Verify token and expiration were set
        assert registry.connection_managers[PluginType.RING]['token'] == token
        assert registry.connection_managers[PluginType.RING]['expires_at'] == expires_at 