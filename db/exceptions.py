"""
Database-specific exceptions for Watch Tower.
"""

from utils.errors import WatchTowerError


class DatabaseConfigError(Exception):
    """Exception for database configuration errors"""


class DatabaseConnectionError(Exception):
    """Exception for database connection errors"""


class CryptographyError(WatchTowerError):
    """Raised when there's an encryption/decryption error."""


class DatabaseEventNotFoundError(WatchTowerError):
    """Raised when a database event is not found."""
