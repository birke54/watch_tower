"""
Watch Tower Registry Package

This package contains registry components for managing cameras and connection managers.
"""

from .camera_registry import registry as camera_registry
from .connection_manager_registry import registry as connection_manager_registry

__all__ = [
    "camera_registry",
    "connection_manager_registry",
]
