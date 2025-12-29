"""
AWS-specific exceptions for Watch Tower.
"""

from utils.errors import WatchTowerError


class RekognitionResourceNotFoundException(Exception):
    """Exception for AWS Rekognition related errors"""


class S3ResourceNotFoundException(Exception):
    """Exception for AWS S3 related errors"""


class SecretsManagerError(WatchTowerError):
    """Raised when there's an error with AWS Secrets Manager."""


class ConfigError(Exception):
    """Exception for AWS configuration errors"""


class ClientError(Exception):
    """Exception for AWS client errors"""


class S3Error(WatchTowerError):
    """Raised when there's an error with AWS S3 operations."""


class RekognitionError(WatchTowerError):
    """Raised when there's an error with AWS Rekognition operations."""


# AWS exceptions
class AWSCredentialsError(WatchTowerError):
    """Raised when AWS credentials are missing or invalid."""


class AWSClientInitializationError(WatchTowerError):
    """Raised when there's an error creating an AWS client."""