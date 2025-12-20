"""
Centralized exceptions for the watch tower application.

This module re-exports all exceptions from their respective modules
to provide a single import point for all application exceptions.
"""

# AWS exceptions
from aws.exceptions import (
    RekognitionResourceNotFoundException,
    S3ResourceNotFoundException,
    SecretsManagerError,
    ConfigError,
    NoCredentialsError,
    ClientError,
    S3Error,
    RekognitionError,
)

# Database exceptions
from db.exceptions import (
    DatabaseConfigError,
    DatabaseConnectionError,
    CryptographyError,
    DatabaseEventNotFoundError,
)

# General domain-specific errors
from utils.errors import WatchTowerError, ConfigurationError, BusinessLogicError, DependencyError, ManagementAPIError


class VideoProcessingError(WatchTowerError):
    """Raised when there's an error with video processing operations."""


class CameraError(WatchTowerError):
    """Raised when there's an error with camera operations."""


class ConnectionManagerError(WatchTowerError):
    """Raised when there's an error with connection manager operations."""


class RingConnectionManagerError(ConnectionManagerError):
    """Raised when there's an error with Ring connection manager operations."""

# Re-export all exceptions
__all__ = [
    # AWS exceptions
    'RekognitionResourceNotFoundException',
    'S3ResourceNotFoundException',
    'SecretsManagerError',
    'ConfigError',
    'NoCredentialsError',
    'ClientError',
    'S3Error',
    'RekognitionError',

    # Database exceptions
    'DatabaseConfigError',
    'DatabaseConnectionError',
    'CryptographyError',
    'DatabaseEventNotFoundError',
    # General domain-specific errors
    'WatchTowerError',
    'ConfigurationError',
    'BusinessLogicError',
    'DependencyError',
    'ManagementAPIError',
    'VideoProcessingError',
    'CameraError',
    'ConnectionManagerError',
    'RingConnectionManagerError',
]
