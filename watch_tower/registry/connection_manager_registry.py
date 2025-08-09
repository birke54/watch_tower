from enum import Enum
from typing import List, Dict, Optional, TypedDict, cast
from datetime import datetime
from connection_managers.connection_manager_base import ConnectionManagerBase
from connection_managers.plugin_type import PluginType


class VendorStatus(Enum):
    ACTIVE = 1
    INACTIVE = 2


class ConnectionManagerInfo(TypedDict):
    connection_manager: ConnectionManagerBase
    status: VendorStatus
    token: Optional[str]
    expires_at: Optional[datetime]


class ConnectionManagerRegistry:
    """
    Registry for connection managers.
    """
    connection_managers: Dict[PluginType, ConnectionManagerInfo]

    def __new__(cls) -> 'ConnectionManagerRegistry':
        """
        Singleton instance of the registry.
        """
        if not hasattr(cls, 'instance'):
            cls.instance = super(ConnectionManagerRegistry, cls).__new__(cls)
            cls.instance.connection_managers = {}
        return cls.instance

    def register_connection_manager(
            self,
            plugin_type: PluginType,
            connection_manager: ConnectionManagerBase) -> None:
        """
        Register a connection manager for a plugin type.
        """
        self.connection_managers[plugin_type] = {
            'connection_manager': connection_manager,
            'status': VendorStatus.INACTIVE,
            'token': None,
            'expires_at': None
        }

    def get_connection_manager(self, plugin_type: PluginType) -> ConnectionManagerBase:
        """
        Get a connection manager for a plugin type.
        """
        return cast(
            ConnectionManagerBase,
            self.connection_managers[plugin_type]['connection_manager'])

    def get_all_connection_managers(self) -> List[ConnectionManagerInfo]:
        """
        Get all connection managers.
        """
        return list(self.connection_managers.values())

    def get_all_active_connection_managers(self) -> List[ConnectionManagerInfo]:
        """
        Get all active connection managers.
        """
        return [manager for manager in self.connection_managers.values(
        ) if manager['status'] == VendorStatus.ACTIVE]

    def update_status(self, plugin_type: PluginType, status: VendorStatus) -> bool:
        """
        Update the status of a connection manager.
        """
        self.connection_managers[plugin_type]['status'] = status
        return True


# Singleton instance of the registry
registry = ConnectionManagerRegistry()
