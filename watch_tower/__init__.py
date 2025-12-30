"""
Watch Tower - Video Surveillance System

A comprehensive video surveillance system with facial recognition capabilities,
featuring centralized configuration management, comprehensive logging, and
a powerful CLI for system management.
"""

__version__ = "3.0.0"
__author__ = "Watch Tower Team"

# Core exports
from .core.business_logic_manager import BUSINESS_LOGIC_MANAGER as business_logic_manager
from .core.bootstrap import bootstrap
# Note: create_management_app is now in the api package at the project root

# Registry exports
from .registry.camera_registry import REGISTRY as camera_registry
from .registry.connection_manager_registry import REGISTRY as connection_manager_registry

# Configuration and exceptions
from .config import config
from .exceptions import (
    WatchTowerError,
    BusinessLogicError,
    ConfigurationError,
    DependencyError,
    ManagementAPIError,
)

__all__ = [
    # Core components
    "business_logic_manager",
    "bootstrap",

    # Registries
    "camera_registry",
    "connection_manager_registry",

    # Configuration and exceptions
    "config",
    "WatchTowerError",
    "BusinessLogicError",
    "ConfigurationError",
    "DependencyError",
    "ManagementAPIError",
]
