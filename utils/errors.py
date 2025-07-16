"""
Watch Tower Error Classes (General/Shared)

This module defines general custom exceptions used throughout the Watch Tower system.
"""

from typing import Optional


class WatchTowerError(Exception):
    """Base exception for Watch Tower system errors."""


class ManagementAPIError(WatchTowerError):
    """Raised when there's an error with the management API."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, original_error: Optional[Exception] = None):
        super().__init__(message)
        self.status_code = status_code
        self.original_error = original_error


class DependencyError(WatchTowerError):
    """Raised when a required dependency is missing."""
    
    def __init__(self, dependency: str, install_command: str):
        message = f"{dependency} is required. Install with: {install_command}"
        super().__init__(message)
        self.dependency = dependency
        self.install_command = install_command


class ConfigurationError(WatchTowerError):
    """Raised when there's a configuration error."""


class BusinessLogicError(WatchTowerError):
    """Raised when there's an error with the business logic loop."""
