import pytest
from connection_managers.connection_manager_factory import ConnectionManagerFactory
from connection_managers.plugin_type import PluginType
from connection_managers.ring_connection_manager import RingConnectionManager


def test_create_ring_connection_manager() -> None:
    """Test creating a Ring connection manager."""
    # Execute
    connection_manager = ConnectionManagerFactory.create(PluginType.RING)

    # Assert
    assert isinstance(connection_manager, RingConnectionManager)


def test_create_unsupported_plugin_type() -> None:
    """Test creating a connection manager for an unsupported plugin type."""
    # Execute and Assert
    with pytest.raises(ValueError) as exc_info:
        # Create a mock plugin type that doesn't exist
        class MockPluginType:
            def __init__(self, value):
                self.value = value

        unsupported_plugin_type = MockPluginType("UNSUPPORTED")
        # Now try to create a connection manager with unsupported type
        ConnectionManagerFactory.create(unsupported_plugin_type)
    assert "Unsupported plugin type" in str(exc_info.value)
