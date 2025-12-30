"""Tests for API health check functions."""

from unittest.mock import Mock, patch

import pytest

from api.health_checks import (
    check_aws_rekognition_health,
    check_aws_s3_health,
    check_database_health,
    get_business_logic_status,
    get_camera_health,
)
from api.schemas import ComponentHealth
from aws.exceptions import ClientError, ConfigError, RekognitionError, S3Error
from db.exceptions import DatabaseConnectionError
from watch_tower.exceptions import BusinessLogicError


class TestCheckDatabaseHealth:
    """Test database health check function."""

    @patch('api.health_checks.get_database_connection')
    def test_check_database_health_success(self, mock_get_connection: Mock) -> None:
        """Test successful database health check."""
        # Setup
        mock_session = Mock()
        mock_session.execute.return_value = None
        mock_session_factory = Mock()
        mock_session_factory.return_value.__enter__ = Mock(return_value=mock_session)
        mock_session_factory.return_value.__exit__ = Mock(return_value=None)
        mock_get_connection.return_value = (None, mock_session_factory)

        # Execute
        result = check_database_health()

        # Verify
        assert result.healthy is True
        assert result.error is None

    @patch('api.health_checks.get_database_connection')
    def test_check_database_health_connection_error(
        self, mock_get_connection: Mock
    ) -> None:
        """Test database health check with connection error."""
        # Setup
        mock_get_connection.side_effect = DatabaseConnectionError("Connection failed")

        # Execute
        result = check_database_health()

        # Verify
        assert result.healthy is False
        assert "Database connection error" in result.error

    @patch('api.health_checks.get_database_connection')
    def test_check_database_health_generic_error(
        self, mock_get_connection: Mock
    ) -> None:
        """Test database health check with generic error."""
        # Setup
        mock_get_connection.side_effect = Exception("Unexpected error")

        # Execute
        result = check_database_health()

        # Verify
        assert result.healthy is False
        assert "Database health check failed" in result.error


class TestCheckAWSS3Health:
    """Test AWS S3 health check function."""

    @patch('api.health_checks.S3_SERVICE')
    @patch('api.health_checks.config')
    def test_check_aws_s3_health_success(
        self, mock_config: Mock, mock_s3_service: Mock
    ) -> None:
        """Test successful AWS S3 health check."""
        # Setup
        mock_config.event_recordings_bucket = "test-bucket"
        mock_s3_service.check_bucket_exists.return_value = True

        # Execute
        result = check_aws_s3_health()

        # Verify
        assert result.healthy is True
        assert result.error is None
        mock_s3_service.check_bucket_exists.assert_called_once_with("test-bucket")

    @patch('api.health_checks.S3_SERVICE')
    @patch('api.health_checks.config')
    def test_check_aws_s3_health_config_error(
        self, mock_config: Mock, mock_s3_service: Mock
    ) -> None:
        """Test AWS S3 health check with configuration error."""
        # Setup
        mock_config.event_recordings_bucket = "test-bucket"
        mock_s3_service.check_bucket_exists.side_effect = ConfigError("Config error")

        # Execute
        result = check_aws_s3_health()

        # Verify
        assert result.healthy is False
        assert "AWS configuration error" in result.error

    @patch('api.health_checks.S3_SERVICE')
    @patch('api.health_checks.config')
    def test_check_aws_s3_health_client_error(
        self, mock_config: Mock, mock_s3_service: Mock
    ) -> None:
        """Test AWS S3 health check with client error."""
        # Setup
        mock_config.event_recordings_bucket = "test-bucket"
        mock_s3_service.check_bucket_exists.side_effect = ClientError(
            {}, "Operation"
        )

        # Execute
        result = check_aws_s3_health()

        # Verify
        assert result.healthy is False
        assert "AWS client error" in result.error

    @patch('api.health_checks.S3_SERVICE')
    @patch('api.health_checks.config')
    def test_check_aws_s3_health_s3_error(
        self, mock_config: Mock, mock_s3_service: Mock
    ) -> None:
        """Test AWS S3 health check with S3 error."""
        # Setup
        mock_config.event_recordings_bucket = "test-bucket"
        mock_s3_service.check_bucket_exists.side_effect = S3Error("S3 error")

        # Execute
        result = check_aws_s3_health()

        # Verify
        assert result.healthy is False
        assert "AWS S3 health check failed" in result.error


class TestCheckAWSRekognitionHealth:
    """Test AWS Rekognition health check function."""

    @patch('api.health_checks.REKOGNITION_SERVICE')
    @patch('api.health_checks.config')
    def test_check_aws_rekognition_health_success(
        self, mock_config: Mock, mock_rekognition_service: Mock
    ) -> None:
        """Test successful AWS Rekognition health check."""
        # Setup
        mock_config.rekognition_collection_id = "test-collection"
        mock_rekognition_service.check_collection_exists.return_value = None

        # Execute
        result = check_aws_rekognition_health()

        # Verify
        assert result.healthy is True
        assert result.error is None
        mock_rekognition_service.check_collection_exists.assert_called_once_with(
            "test-collection"
        )

    @patch('api.health_checks.REKOGNITION_SERVICE')
    @patch('api.health_checks.config')
    def test_check_aws_rekognition_health_config_error(
        self, mock_config: Mock, mock_rekognition_service: Mock
    ) -> None:
        """Test AWS Rekognition health check with configuration error."""
        # Setup
        mock_config.rekognition_collection_id = "test-collection"
        mock_rekognition_service.check_collection_exists.side_effect = ConfigError(
            "Config error"
        )

        # Execute
        result = check_aws_rekognition_health()

        # Verify
        assert result.healthy is False
        assert "AWS Rekognition health check failed" in result.error
        assert "Config error" in result.error

    @patch('api.health_checks.REKOGNITION_SERVICE')
    @patch('api.health_checks.config')
    def test_check_aws_rekognition_health_client_error(
        self, mock_config: Mock, mock_rekognition_service: Mock
    ) -> None:
        """Test AWS Rekognition health check with client error."""
        # Setup
        mock_config.rekognition_collection_id = "test-collection"
        mock_rekognition_service.check_collection_exists.side_effect = ClientError(
            {'Error': {'Code': 'SomeOtherError', 'Message': 'Some error'}}, "Operation"
        )

        # Execute
        result = check_aws_rekognition_health()

        # Verify
        assert result.healthy is False
        assert "AWS Rekognition health check failed" in result.error

    @patch('api.health_checks.REKOGNITION_SERVICE')
    @patch('api.health_checks.config')
    def test_check_aws_rekognition_health_rekognition_error(
        self, mock_config: Mock, mock_rekognition_service: Mock
    ) -> None:
        """Test AWS Rekognition health check with Rekognition error."""
        # Setup
        mock_config.rekognition_collection_id = "test-collection"
        mock_rekognition_service.check_collection_exists.side_effect = RekognitionError(
            "Rekognition error"
        )

        # Execute
        result = check_aws_rekognition_health()

        # Verify
        assert result.healthy is False
        assert "AWS Rekognition error" in result.error

    @patch('api.health_checks.REKOGNITION_SERVICE')
    @patch('api.health_checks.config')
    def test_check_aws_rekognition_health_generic_error(
        self, mock_config: Mock, mock_rekognition_service: Mock
    ) -> None:
        """Test AWS Rekognition health check with generic error."""
        # Setup
        mock_config.rekognition_collection_id = "test-collection"
        mock_rekognition_service.check_collection_exists.side_effect = Exception(
            "Unexpected error"
        )

        # Execute
        result = check_aws_rekognition_health()

        # Verify
        assert result.healthy is False
        assert "AWS Rekognition health check failed" in result.error

    def test_check_aws_rekognition_health_imports_available(self) -> None:
        """Test that REKOGNITION_SERVICE and RekognitionError are properly imported.
        
        This test specifically catches the NameError that occurred when stopping
        the business logic via API.
        """
        # This test verifies that the imports are available at module level
        from api.health_checks import REKOGNITION_SERVICE  # noqa: F401
        from aws.exceptions import RekognitionError  # noqa: F401

        # If we get here without NameError, the imports are correct
        assert True


class TestGetBusinessLogicStatus:
    """Test business logic status function."""

    @patch('api.health_checks.business_logic_manager')
    def test_get_business_logic_status_success(
        self, mock_business_logic_manager: Mock
    ) -> None:
        """Test successful business logic status retrieval."""
        # Setup
        mock_business_logic_manager.get_status.return_value = {
            'running': True,
            'uptime': '1h 30m',
            'start_time': '2024-01-01T00:00:00'
        }

        # Execute
        result = get_business_logic_status()

        # Verify
        assert result.running is True
        assert result.uptime == '1h 30m'
        assert result.start_time == '2024-01-01T00:00:00'
        assert result.error is None

    @patch('api.health_checks.business_logic_manager')
    def test_get_business_logic_status_error(
        self, mock_business_logic_manager: Mock
    ) -> None:
        """Test business logic status with error."""
        # Setup
        mock_business_logic_manager.get_status.side_effect = BusinessLogicError(
            "Business logic error"
        )

        # Execute
        result = get_business_logic_status()

        # Verify
        assert result.running is False
        assert result.uptime == 'Unknown'
        assert result.start_time == 'Unknown'
        assert "Business logic error" in result.error


class TestGetCameraHealth:
    """Test camera health function."""

    @patch('api.health_checks.camera_registry')
    def test_get_camera_health_success(self, mock_camera_registry: Mock) -> None:
        """Test successful camera health retrieval."""
        # Setup
        from watch_tower.registry.camera_registry import CameraStatus

        mock_entry = Mock()
        mock_entry.camera = Mock()
        mock_entry.camera.name = "Test Camera"
        mock_entry.camera.plugin_type = "RING"
        mock_entry.status = Mock()
        mock_entry.status.name = "ACTIVE"
        mock_entry.last_polled = "2024-01-01T00:00:00"
        mock_entry.status_last_updated = "2024-01-01T00:00:00"

        mock_camera_registry.cameras = {
            ("RING", "Test Camera"): mock_entry
        }

        # Execute
        cameras, error = get_camera_health()

        # Verify
        assert len(cameras) == 1
        assert cameras[0].name == "Test Camera"
        assert cameras[0].healthy is True
        assert error is None

    @patch('api.health_checks.camera_registry')
    def test_get_camera_health_error(self, mock_camera_registry: Mock) -> None:
        """Test camera health with error."""
        # Setup
        mock_camera_registry.cameras.values.side_effect = Exception("Registry error")

        # Execute
        cameras, error = get_camera_health()

        # Verify
        assert len(cameras) == 0
        assert "Camera registry health check failed" in error

