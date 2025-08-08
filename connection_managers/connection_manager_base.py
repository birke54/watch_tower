from abc import ABC, abstractmethod
from typing import List, Optional, Any, Dict
from connection_managers.plugin_type import PluginType


class ConnectionManagerBase(ABC):
    """Base class for all connection managers."""

    def __init__(self) -> None:
        self._plugin_type: Optional[PluginType] = None

    @property
    def plugin_type(self) -> PluginType:
        if self._plugin_type is None:
            raise ValueError("Plugin type not set")
        return self._plugin_type

    @abstractmethod
    async def login(self) -> bool:
        """Connect to the service."""

    @abstractmethod
    async def logout(self) -> bool:
        """Logout from the service."""

    @abstractmethod
    async def is_healthy(self) -> bool:
        """Check if the connection is healthy."""

    @abstractmethod
    async def get_cameras(self) -> List[Dict[str, Any]]:
        """Get list of cameras."""
