from typing import Dict, Type
from connection_managers.connection_manager_base import ConnectionManagerBase, PluginType
from connection_managers.plugin_type import PluginType
from utils.logging_config import get_logger

# Configure Logger for this file
logger = get_logger(__name__)


class ConnectionManagerFactory:
    """
    Factory for creating connection managers.
    Handles the creation of different types of connection managers based on the plugin type.
    """
    _connection_managers: Dict[PluginType, Type[ConnectionManagerBase]] = {}

    @classmethod
    def create(cls, plugin_type: PluginType) -> ConnectionManagerBase:
        """
        Create a connection manager instance for the speciFIED plugin type.

        Args:
            plugin_type: The type of plugin to create a connection manager for.

        Returns:
            ConnectionManagerBase: An instance of the appropriate connection manager.

        Raises:
            ValueError: If the plugin type is not supported.
        """
        # Import here to avoid circular imports
        if plugin_type == PluginType.RING:
            from connection_managers.ring_connection_manager import RingConnectionManager
            return RingConnectionManager()

        logger.error(f"Unsupported plugin type: {plugin_type}")
        raise ValueError(f"Unsupported plugin type: {plugin_type}")
