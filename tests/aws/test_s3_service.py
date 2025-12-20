"""Tests for S3 service functionality."""
from typing import Generator
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError

from aws.exceptions import S3Error, S3ResourceNotFoundException
from aws.s3.s3_service import S3Service

# Test data
TEST_BUCKET_NAME = "test-bucket"
TEST_OBJECT_NAME = "test-object"
TEST_FILE_PATH = "test-file-path"


@pytest.fixture(name='mock_env_vars')
def _mock_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set up test environment variables."""
    monkeypatch.setenv('AWS_REGION', 'us-west-2')
    monkeypatch.setenv('AWS_ACCESS_KEY_ID', 'test-key')
    monkeypatch.setenv('AWS_SECRET_ACCESS_KEY', 'test-secret')
    monkeypatch.setenv('S3_BUCKET_NAME', TEST_BUCKET_NAME)


@pytest.fixture(name='mock_config')
def _mock_config() -> Generator[Mock, None, None]:
    """Mock the configuration to use test values."""
    with patch('aws.s3.s3_service.config') as mock_config:
        mock_config.s3_bucket_name = TEST_BUCKET_NAME
        yield mock_config


@pytest.fixture(name='mock_s3_client')
def _mock_s3_client() -> Generator[Mock, None, None]:
    """Create a mock S3 client."""
    with patch('boto3.client') as mock_client:
        yield mock_client.return_value


@pytest.fixture(name='s3_service')
def _s3_service(
        mock_env_vars: None,
        mock_config: Mock,
        mock_s3_client: Mock) -> S3Service:
    """Create an S3 service instance with mocked dependencies."""
    # Fixtures are used for their side effects (setup), not directly in the function body
    _ = mock_env_vars, mock_config, mock_s3_client
    return S3Service()


def test_init_success(
        mock_env_vars: None,
        mock_config: Mock,
        mock_s3_client: Mock) -> None:
    """Test successful initialization of S3Service."""
    # Use the fixtures to ensure proper setup
    _ = mock_env_vars, mock_config
    service = S3Service()
    assert service.client == mock_s3_client


def test_init_missing_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test initialization fails with missing environment variables."""
    # Remove all environment variables
    monkeypatch.delenv('AWS_REGION', raising=False)
    monkeypatch.delenv('AWS_ACCESS_KEY_ID', raising=False)
    monkeypatch.delenv('AWS_SECRET_ACCESS_KEY', raising=False)

    # Mock config to raise ValueError when missing required vars
    with patch('aws.s3.s3_service.config') as mock_config_patch:
        mock_config_patch.validate_s3_only.side_effect = ValueError(
            "Missing required environment variables")
        with pytest.raises(ValueError) as exc_info:
            S3Service()
        assert "Missing required environment variables" in str(exc_info.value)


def test_check_bucket_exists_success(
        s3_service: S3Service,
        mock_s3_client: Mock) -> None:
    """Test successful bucket existence check."""
    mock_s3_client.head_bucket.return_value = {}

    s3_service.check_bucket_exists(TEST_BUCKET_NAME)


def test_check_bucket_exists_not_found(
        s3_service: S3Service,
        mock_s3_client: Mock) -> None:
    """Test bucket existence check when bucket doesn't exist."""
    mock_s3_client.head_bucket.side_effect = ClientError(
        {'Error': {'Code': '404'}},
        'HeadBucket'
    )

    with pytest.raises(S3ResourceNotFoundException) as exc_info:
        s3_service.check_bucket_exists(TEST_BUCKET_NAME)
    assert str(exc_info.value) == f"Bucket {TEST_BUCKET_NAME} not found"


def test_get_files_with_prefix_success(
        s3_service: S3Service,
        mock_s3_client: Mock) -> None:
    """Test successful retrieval of files with a given prefix."""
    mock_s3_client.list_objects_v2.return_value = {
        'Contents': [
            {
                'Key': 'file1.jpg'
            },
            {
                'Key': 'file2.jpg'
            },
            {
                'Key': 'different_prefix_file.jpg'
            },
        ]
    }

    files = s3_service.get_files_with_prefix(TEST_BUCKET_NAME, 'file')
    assert len(files) == 2
    assert 's3://test-bucket/file1.jpg' in files
    assert 's3://test-bucket/file2.jpg' in files
    assert 's3://test-bucket/different_prefix_file.jpg' not in files


def test_get_files_with_prefix_no_files(
        s3_service: S3Service,
        mock_s3_client: Mock) -> None:
    """Test retrieval of files with a given prefix when no files match."""
    mock_s3_client.list_objects_v2.return_value = {
        'Contents': []
    }

    files = s3_service.get_files_with_prefix(TEST_BUCKET_NAME, 'non_existent_prefix')
    assert len(files) == 0
    assert mock_s3_client.list_objects_v2.call_count == 1


def test_get_files_with_prefix_error(
        s3_service: S3Service,
        mock_s3_client: Mock) -> None:
    """Test retrieval of files with a given prefix when an error occurs."""
    mock_s3_client.list_objects_v2.side_effect = ClientError(
        {'Error': {'Code': '404'}},
        'ListObjectsV2'
    )

    with pytest.raises(S3ResourceNotFoundException) as exc_info:
        s3_service.get_files_with_prefix(TEST_BUCKET_NAME, 'file')
    assert str(exc_info.value) == f"Bucket {TEST_BUCKET_NAME} not found"
    assert mock_s3_client.list_objects_v2.call_count == 1


def test_download_file_success(
        s3_service: S3Service,
        mock_s3_client: Mock,
        tmp_path: pytest.TempPathFactory) -> None:
    """Test successful file download from S3."""
    # Setup
    test_object_key = "test/object.jpg"
    local_path = tmp_path / "downloaded" / "object.jpg"

    # Mock the head_bucket call in check_bucket_exists
    mock_s3_client.head_bucket.return_value = {}

    # Test
    s3_service.download_file(TEST_BUCKET_NAME, test_object_key, str(local_path))

    # Verify
    mock_s3_client.download_file.assert_called_once_with(
        TEST_BUCKET_NAME,
        test_object_key,
        str(local_path)
    )
    assert local_path.parent.exists()


def test_download_file_bucket_not_found(
        s3_service: S3Service,
        mock_s3_client: Mock,
        tmp_path: pytest.TempPathFactory) -> None:
    """Test file download when bucket doesn't exist."""
    # Setup
    test_object_key = "test/object.jpg"
    local_path = tmp_path / "downloaded" / "object.jpg"

    # Mock the head_bucket call to simulate bucket not found
    mock_s3_client.head_bucket.side_effect = ClientError(
        {'Error': {'Code': '404'}},
        'HeadBucket'
    )

    # Test and verify
    with pytest.raises(S3Error) as exc_info:
        s3_service.download_file(TEST_BUCKET_NAME, test_object_key, str(local_path))
    assert "error downloading file" in str(exc_info.value).lower()
    mock_s3_client.download_file.assert_not_called()


def test_download_file_object_not_found(
        s3_service: S3Service,
        mock_s3_client: Mock,
        tmp_path: pytest.TempPathFactory) -> None:
    """Test file download when object doesn't exist."""
    # Setup
    test_object_key = "test/object.jpg"
    local_path = tmp_path / "downloaded" / "object.jpg"

    # Mock the head_bucket call in check_bucket_exists
    mock_s3_client.head_bucket.return_value = {}

    # Mock the download_file call to simulate object not found
    mock_s3_client.download_file.side_effect = ClientError(
        {'Error': {'Code': '404'}},
        'GetObject'
    )

    # Test and verify
    with pytest.raises(S3Error) as exc_info:
        s3_service.download_file(TEST_BUCKET_NAME, test_object_key, str(local_path))
    assert "error downloading file" in str(exc_info.value).lower()
    mock_s3_client.download_file.assert_called_once()


def test_download_file_creates_directory(
        s3_service: S3Service,
        mock_s3_client: Mock,
        tmp_path: pytest.TempPathFactory) -> None:
    """Test that download_file creates the target directory if it doesn't exist."""
    # Setup
    test_object_key = "test/object.jpg"
    local_path = tmp_path / "new" / "directory" / "object.jpg"

    # Mock the head_bucket call in check_bucket_exists
    mock_s3_client.head_bucket.return_value = {}

    # Test
    s3_service.download_file(TEST_BUCKET_NAME, test_object_key, str(local_path))

    # Verify
    assert local_path.parent.exists()
    mock_s3_client.download_file.assert_called_once()
