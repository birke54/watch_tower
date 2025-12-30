"""Tests for watch_tower exception classes."""

from watch_tower.exceptions import (
    WatchTowerError,
    BusinessLogicError,
    ConfigurationError,
    DependencyError,
    ManagementAPIError,
    # AWS exceptions
    SecretsManagerError,
    ConfigError,
    AWSCredentialsError,
    ClientError,
    S3ResourceNotFoundException,
    RekognitionResourceNotFoundException,
    # Database exceptions
    DatabaseConfigError,
    DatabaseConnectionError,
    CryptographyError,
)


def test_watch_tower_error():
    """Test WatchTowerError exception."""
    error = WatchTowerError("error")
    assert str(error) == "error"
    assert isinstance(error, Exception)


def test_business_logic_error():
    """Test BusinessLogicError exception."""
    error = BusinessLogicError("error")
    assert str(error) == "error"
    assert isinstance(error, Exception)


def test_configuration_error():
    """Test ConfigurationError exception."""
    error = ConfigurationError("error")
    assert str(error) == "error"
    assert isinstance(error, Exception)


def test_dependency_error():
    """Test DependencyError exception."""
    error = DependencyError("ffmpeg", "apt-get install ffmpeg")
    assert "ffmpeg is required" in str(error)
    assert isinstance(error, Exception)


def test_management_api_error():
    """Test ManagementAPIError exception."""
    error = ManagementAPIError("error")
    assert str(error) == "error"
    assert isinstance(error, Exception)


def test_secrets_manager_error() -> None:
    """Test SecretsManagerError exception."""
    error_msg = "Failed to retrieve secret"
    error = SecretsManagerError(error_msg)
    assert str(error) == error_msg
    assert isinstance(error, Exception)


def test_config_error() -> None:
    """Test ConfigError exception."""
    error_msg = "Missing configuration"
    error = ConfigError(error_msg)
    assert str(error) == error_msg
    assert isinstance(error, Exception)


def test_aws_credentials_error() -> None:
    """Test AWSCredentialsError exception."""
    error_msg = "No AWS credentials found"
    error = AWSCredentialsError(error_msg)
    assert str(error) == error_msg
    assert isinstance(error, Exception)


def test_s3_resource_not_found_error() -> None:
    """Test S3ResourceNotFoundException exception."""
    error_msg = "S3 bucket not found"
    error = S3ResourceNotFoundException(error_msg)
    assert str(error) == error_msg
    assert isinstance(error, Exception)


def test_rekognition_resource_not_found_error() -> None:
    """Test RekognitionResourceNotFoundException exception."""
    error_msg = "Rekognition collection not found"
    error = RekognitionResourceNotFoundException(error_msg)
    assert str(error) == error_msg
    assert isinstance(error, Exception)


def test_database_config_error() -> None:
    """Test DatabaseConfigError exception."""
    error_msg = "Database configuration error"
    error = DatabaseConfigError(error_msg)
    assert str(error) == error_msg
    assert isinstance(error, Exception)


def test_database_connection_error() -> None:
    """Test DatabaseConnectionError exception."""
    error_msg = "Database connection failed"
    error = DatabaseConnectionError(error_msg)
    assert str(error) == error_msg
    assert isinstance(error, Exception)


def test_cryptography_error() -> None:
    """Test CryptographyError exception."""
    error_msg = "Encryption failed"
    error = CryptographyError(error_msg)
    assert str(error) == error_msg
    assert isinstance(error, Exception)


def test_exception_inheritance() -> None:
    """Test that all custom exceptions inherit from Exception."""
    custom_exceptions = [
        SecretsManagerError,
        ConfigError,
        AWSCredentialsError,
        ClientError,
        S3ResourceNotFoundException,
        RekognitionResourceNotFoundException,
        DatabaseConfigError,
        DatabaseConnectionError,
        CryptographyError,
    ]

    for exception_class in custom_exceptions:
        error = exception_class("test message")
        assert isinstance(error, Exception)
        assert isinstance(error, exception_class)


def test_exception_with_empty_message() -> None:
    """Test exception with empty message."""
    error = ConfigError("")
    assert str(error) == ""


def test_exception_with_long_message() -> None:
    """Test exception with long message."""
    long_message = (
        "This is a very long error message that contains a lot of details "
        "about what went wrong and how to fix it"
    )
    error = ConfigError(long_message)
    assert str(error) == long_message


def test_exception_with_special_characters() -> None:
    """Test exception with special characters in message."""
    special_message = "Error with special chars: !@#$%^&*()_+-=[]{}|;':\",./<>?"
    error = ConfigError(special_message)
    assert str(error) == special_message
