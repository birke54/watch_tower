from watch_tower.exceptions import (
    WatchTowerError,
    BusinessLogicError,
    ConfigurationError,
    DependencyError,
    ManagementAPIError,
    # AWS exceptions
    SecretsManagerError,
    ConfigError,
    NoCredentialsError,
    ClientError,
    S3ResourceNotFoundException,
    RekognitionResourceNotFoundException,
    # Database exceptions
    DatabaseConfigError,
    DatabaseConnectionError,
    CryptographyError,
)

class TestWatchTowerExceptions:
    def test_watch_tower_error(self):
        error = WatchTowerError("error")
        assert str(error) == "error"
        assert isinstance(error, Exception)

    def test_business_logic_error(self):
        error = BusinessLogicError("error")
        assert str(error) == "error"
        assert isinstance(error, Exception)

    def test_configuration_error(self):
        error = ConfigurationError("error")
        assert str(error) == "error"
        assert isinstance(error, Exception)

    def test_dependency_error(self):
        error = DependencyError("ffmpeg", "apt-get install ffmpeg")
        assert "ffmpeg is required" in str(error)
        assert isinstance(error, Exception)

    def test_management_api_error(self):
        error = ManagementAPIError("error")
        assert str(error) == "error"
        assert isinstance(error, Exception)


class TestAWSExceptions:
    """Test AWS-related exceptions."""

    def test_secrets_manager_error(self) -> None:
        """Test SecretsManagerError exception."""
        error_msg = "Failed to retrieve secret"
        error = SecretsManagerError(error_msg)
        assert str(error) == error_msg
        assert isinstance(error, Exception)

    def test_config_error(self) -> None:
        """Test ConfigError exception."""
        error_msg = "Missing configuration"
        error = ConfigError(error_msg)
        assert str(error) == error_msg
        assert isinstance(error, Exception)

    def test_no_credentials_error(self) -> None:
        """Test NoCredentialsError exception."""
        error_msg = "No AWS credentials found"
        error = NoCredentialsError(error_msg)
        assert str(error) == error_msg
        assert isinstance(error, Exception)

    def test_client_error(self) -> None:
        """Test ClientError exception."""
        error_msg = "AWS client error"
        error = ClientError(error_msg)
        assert str(error) == error_msg
        assert isinstance(error, Exception)

    def test_s3_resource_not_found_error(self) -> None:
        """Test S3ResourceNotFoundException exception."""
        error_msg = "S3 bucket not found"
        error = S3ResourceNotFoundException(error_msg)
        assert str(error) == error_msg
        assert isinstance(error, Exception)

    def test_rekognition_resource_not_found_error(self) -> None:
        """Test RekognitionResourceNotFoundException exception."""
        error_msg = "Rekognition collection not found"
        error = RekognitionResourceNotFoundException(error_msg)
        assert str(error) == error_msg
        assert isinstance(error, Exception)


class TestDatabaseExceptions:
    """Test database-related exceptions."""

    def test_database_config_error(self) -> None:
        """Test DatabaseConfigError exception."""
        error_msg = "Database configuration error"
        error = DatabaseConfigError(error_msg)
        assert str(error) == error_msg
        assert isinstance(error, Exception)

    def test_database_connection_error(self) -> None:
        """Test DatabaseConnectionError exception."""
        error_msg = "Database connection failed"
        error = DatabaseConnectionError(error_msg)
        assert str(error) == error_msg
        assert isinstance(error, Exception)

    def test_cryptography_error(self) -> None:
        """Test CryptographyError exception."""
        error_msg = "Encryption failed"
        error = CryptographyError(error_msg)
        assert str(error) == error_msg
        assert isinstance(error, Exception)


class TestExceptionInheritance:
    """Test exception inheritance hierarchy."""

    def test_exception_inheritance(self) -> None:
        """Test that all custom exceptions inherit from Exception."""
        custom_exceptions = [
            SecretsManagerError,
            ConfigError,
            NoCredentialsError,
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


class TestExceptionMessages:
    """Test exception message handling."""

    def test_exception_with_empty_message(self) -> None:
        """Test exception with empty message."""
        error = ConfigError("")
        assert str(error) == ""

    def test_exception_with_long_message(self) -> None:
        """Test exception with long message."""
        long_message = "This is a very long error message that contains a lot of details about what went wrong and how to fix it"
        error = ConfigError(long_message)
        assert str(error) == long_message

    def test_exception_with_special_characters(self) -> None:
        """Test exception with special characters in message."""
        special_message = "Error with special chars: !@#$%^&*()_+-=[]{}|;':\",./<>?"
        error = ConfigError(special_message)
        assert str(error) == special_message