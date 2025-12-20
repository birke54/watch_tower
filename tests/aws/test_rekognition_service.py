"""Tests for the RekognitionService class."""
from typing import Generator
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError

from aws.exceptions import RekognitionError, RekognitionResourceNotFoundException
from aws.rekognition.rekognition_service import RekognitionService

# Test data
TEST_COLLECTION_ID = "test-collection"
TEST_PERSON_ID = "test-person"
TEST_BUCKET_NAME = "test-bucket"
TEST_VIDEO_PATH = "test/video.mp4"
TEST_JOB_ID = "test-job-id"


@pytest.fixture
def mock_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set up test environment variables."""
    monkeypatch.setenv('AWS_REGION', 'us-west-2')
    monkeypatch.setenv('AWS_ACCESS_KEY_ID', 'test-key')
    monkeypatch.setenv('AWS_SECRET_ACCESS_KEY', 'test-secret')
    monkeypatch.setenv('REKOGNITION_COLLECTION_ID', TEST_COLLECTION_ID)
    monkeypatch.setenv('REKOGNITION_S3_KNOWN_FACES_BUCKET', TEST_BUCKET_NAME)
    monkeypatch.setenv('SNS_REKOGNITION_VIDEO_ANALYSIS_TOPIC_ARN', 'test-topic-arn')
    monkeypatch.setenv('REKOGNITION_VIDEO_SERVICE_ROLE_ARN', 'test-role-arn')


@pytest.fixture
def mock_config(monkeypatch: pytest.MonkeyPatch) -> Generator[Mock, None, None]:
    """Mock the configuration to use test values."""
    with patch('aws.rekognition.rekognition_service.config') as mock_config:
        mock_config.rekognition_collection_id = TEST_COLLECTION_ID
        mock_config.rekognition_s3_known_faces_bucket = TEST_BUCKET_NAME
        mock_config.sns_rekognition_video_analysis_topic_arn = 'test-topic-arn'
        mock_config.rekognition_video_service_role_arn = 'test-role-arn'
        mock_config.event_recordings_bucket = 'test-event-recordings-bucket'
        mock_config.video.polling_interval = 10
        yield mock_config


@pytest.fixture
def mock_rekognition_client() -> Generator[Mock, None, None]:
    """Create a mock Rekognition client."""
    with patch('boto3.client') as mock_client:
        yield mock_client.return_value


@pytest.fixture
def mock_s3_service() -> Generator[Mock, None, None]:
    """Create a mock S3 service."""
    with patch('aws.rekognition.rekognition_service.S3_SERVICE') as mock_service:
        yield mock_service


@pytest.fixture
def clean_running_jobs() -> Generator[None, None, None]:
    """Clean up RUNNING_FACE_SEARCH_JOBS before and after each test."""
    from aws.rekognition.rekognition_service import RUNNING_FACE_SEARCH_JOBS
    # Clear before test
    RUNNING_FACE_SEARCH_JOBS.clear()
    yield
    # Clear after test
    RUNNING_FACE_SEARCH_JOBS.clear()


@pytest.fixture
def rekognition_service(
    mock_env_vars: None,
    mock_config: Mock,
    mock_rekognition_client: Mock,
    mock_s3_service: Mock,
    clean_running_jobs: None
) -> RekognitionService:
    """Create a RekognitionService instance with mocked dependencies."""
    return RekognitionService()


def test_init_success(
        mock_env_vars: None,
        mock_config: Mock,
        mock_rekognition_client: Mock
) -> None:
    """Test successful initialization of RekognitionService."""
    service = RekognitionService()
    assert service.client == mock_rekognition_client
    assert service.collection_id == TEST_COLLECTION_ID
    assert service.bucket_name == TEST_BUCKET_NAME


def test_init_missing_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test initialization fails with missing environment variables."""
    # Remove all environment variables
    monkeypatch.delenv('AWS_REGION', raising=False)
    monkeypatch.delenv('AWS_ACCESS_KEY_ID', raising=False)
    monkeypatch.delenv('AWS_SECRET_ACCESS_KEY', raising=False)

    with patch('aws.rekognition.rekognition_service.config') as mock_config:
        mock_config.validate_aws_only.side_effect = ValueError(
            "Missing required environment variables")
        RekognitionService()
        with pytest.raises(ValueError) as exc_info:
            mock_config.validate_aws_only()
        assert "Missing required environment variables" in str(exc_info.value)


def test_check_collection_exists_success(
        rekognition_service: RekognitionService,
        mock_rekognition_client: Mock
) -> None:
    """Test successful collection existence check."""
    mock_rekognition_client.describe_collection.return_value = {
        'CollectionARN': 'test-arn'}

    rekognition_service.check_collection_exists(TEST_COLLECTION_ID)
    mock_rekognition_client.describe_collection.assert_called_once_with(
        CollectionId=TEST_COLLECTION_ID
    )


def test_check_collection_exists_not_found(
        rekognition_service: RekognitionService,
        mock_rekognition_client: Mock
) -> None:
    """Test collection existence check when collection doesn't exist."""
    mock_rekognition_client.describe_collection.side_effect = ClientError(
        {'Error': {'Code': 'ResourceNotFoundException'}},
        'DescribeCollection'
    )

    with pytest.raises(RekognitionResourceNotFoundException) as exc_info:
        rekognition_service.check_collection_exists(TEST_COLLECTION_ID)
    assert str(exc_info.value) == f"Collection {TEST_COLLECTION_ID} not found"


def test_index_faces_success(
        rekognition_service: RekognitionService,
        mock_rekognition_client: Mock,
        mock_s3_service: Mock
) -> None:
    """Test successful face indexing."""
    # Mock S3 files
    mock_s3_service.get_files_with_prefix.return_value = [
        'test/person1.jpg', 'test/person2.jpg']

    # Mock Rekognition response
    mock_rekognition_client.index_faces.return_value = {'JobId': TEST_JOB_ID}

    job_id = rekognition_service.index_faces(TEST_PERSON_ID)

    assert job_id == TEST_JOB_ID
    assert mock_rekognition_client.index_faces.call_count == 2
    mock_s3_service.get_files_with_prefix.assert_called_once_with(
        TEST_BUCKET_NAME, TEST_PERSON_ID)


def test_index_faces_no_files(
        rekognition_service: RekognitionService,
        mock_s3_service: Mock
) -> None:
    """Test face indexing with no matching files."""
    mock_s3_service.get_files_with_prefix.return_value = []

    with pytest.raises(ValueError) as exc_info:
        rekognition_service.index_faces(TEST_PERSON_ID)
    assert "No matching files found" in str(exc_info.value)
    mock_s3_service.get_files_with_prefix.assert_called_once_with(
        TEST_BUCKET_NAME, TEST_PERSON_ID)


@pytest.mark.asyncio
async def test_start_face_search_success(
        rekognition_service: RekognitionService,
        mock_rekognition_client: Mock
) -> None:
    """Test successful face search start."""
    # Mock Rekognition response
    mock_rekognition_client.start_face_search.return_value = {'JobId': TEST_JOB_ID}
    mock_rekognition_client.get_face_search.return_value = {
        'JobStatus': 'SUCCEEDED',
        'Persons': [
            {
                'Timestamp': 1000,
                'FaceMatches': [
                    {'Face': {'FaceId': 'face1'}},
                    {'Face': {'FaceId': 'face2'}}
                ]
            }
        ]
    }

    matches, was_skipped = await rekognition_service.start_face_search(TEST_VIDEO_PATH)

    assert len(matches) == 2
    assert was_skipped is False
    assert any(match['face_id'] == 'face1' for match in matches)
    assert any(match['face_id'] == 'face2' for match in matches)
    mock_rekognition_client.start_face_search.assert_called_once()


@pytest.mark.asyncio
async def test_start_face_search_failed_job(
        rekognition_service: RekognitionService,
        mock_rekognition_client: Mock
) -> None:
    """Test face search with failed job."""
    mock_rekognition_client.start_face_search.return_value = {'JobId': TEST_JOB_ID}
    mock_rekognition_client.get_face_search.return_value = {
        'JobStatus': 'FAILED'
    }

    with pytest.raises(RekognitionError) as exc_info:
        await rekognition_service.start_face_search(TEST_VIDEO_PATH)

    assert "Face search job test-job-id failed with status: FAILED" in str(exc_info.value)
    mock_rekognition_client.start_face_search.assert_called_once()


@pytest.mark.asyncio
async def test_get_face_search_results_success(
        rekognition_service: RekognitionService,
        mock_rekognition_client: Mock
) -> None:
    """Test successful face search results retrieval."""
    mock_rekognition_client.get_face_search.return_value = {
        'JobStatus': 'SUCCEEDED',
        'Persons': [
            {
                'Timestamp': 1000,
                'FaceMatches': [
                    {'Face': {'FaceId': 'face1'}},
                    {'Face': {'FaceId': 'face2'}}
                ]
            }
        ]
    }

    matches = await rekognition_service.get_face_search_results(TEST_JOB_ID)

    assert len(matches) == 2
    assert any(match['face_id'] == 'face1' for match in matches)
    assert any(match['face_id'] == 'face2' for match in matches)


@pytest.mark.asyncio
async def test_get_face_search_results_polling(
        rekognition_service: RekognitionService,
        mock_rekognition_client: Mock
) -> None:
    """Test face search results polling behavior."""
    # First call returns IN_PROGRESS, second call returns SUCCEEDED
    mock_rekognition_client.get_face_search.side_effect = [
        {'JobStatus': 'IN_PROGRESS'},
        {
            'JobStatus': 'SUCCEEDED',
            'Persons': [
                {
                    'Timestamp': 1000,
                    'FaceMatches': [
                        {'Face': {'FaceId': 'face1'}}
                    ]
                }
            ]
        }
    ]

    matches = await rekognition_service.get_face_search_results(TEST_JOB_ID)

    assert len(matches) == 1
    assert any(match['face_id'] == 'face1' for match in matches)
    assert mock_rekognition_client.get_face_search.call_count == 2

@pytest.mark.asyncio
async def test_start_face_search_job_already_running(
        rekognition_service: RekognitionService,
        mock_rekognition_client: Mock
) -> None:
    """Test face search skips when job is already running."""
    from aws.rekognition.rekognition_service import RUNNING_FACE_SEARCH_JOBS
    
    # Add video to running jobs set
    RUNNING_FACE_SEARCH_JOBS.add(TEST_VIDEO_PATH)

    try:
        matches, was_skipped = await rekognition_service.start_face_search(TEST_VIDEO_PATH)

        assert len(matches) == 0
        assert was_skipped is True
        mock_rekognition_client.start_face_search.assert_not_called()
    finally:
        # Clean up
        RUNNING_FACE_SEARCH_JOBS.discard(TEST_VIDEO_PATH)


@pytest.mark.asyncio
async def test_start_face_search_s3_url_format(
    rekognition_service: RekognitionService,
    mock_rekognition_client: Mock,
    mock_config: Mock
) -> None:
    """Test face search with s3:// URL format."""
    s3_url = "s3://my-bucket/path/to/video.mp4"
    mock_rekognition_client.start_face_search.return_value = {'JobId': TEST_JOB_ID}
    mock_rekognition_client.get_face_search.return_value = {
        'JobStatus': 'SUCCEEDED',
        'Persons': []
    }
    
    matches, was_skipped = await rekognition_service.start_face_search(s3_url)
    
    assert was_skipped is False
    mock_rekognition_client.start_face_search.assert_called_once()
    call_args = mock_rekognition_client.start_face_search.call_args
    assert call_args[1]['Video']['S3Object']['Bucket'] == 'my-bucket'
    assert call_args[1]['Video']['S3Object']['Name'] == 'path/to/video.mp4'


@pytest.mark.asyncio
async def test_start_face_search_http_url_format(
    rekognition_service: RekognitionService,
    mock_rekognition_client: Mock,
    mock_config: Mock
) -> None:
    """Test face search with http/https URL format (path-style: bucket in path)."""
    # Path-style URL: https://s3.region.amazonaws.com/bucket-name/key
    http_url = "https://s3.us-west-2.amazonaws.com/my-bucket/path/to/video.mp4"
    mock_rekognition_client.start_face_search.return_value = {'JobId': TEST_JOB_ID}
    mock_rekognition_client.get_face_search.return_value = {
        'JobStatus': 'SUCCEEDED',
        'Persons': []
    }

    matches, was_skipped = await rekognition_service.start_face_search(http_url)

    assert was_skipped is False
    mock_rekognition_client.start_face_search.assert_called_once()
    call_args = mock_rekognition_client.start_face_search.call_args
    assert call_args[1]['Video']['S3Object']['Bucket'] == 'my-bucket'
    assert call_args[1]['Video']['S3Object']['Name'] == 'path/to/video.mp4'


@pytest.mark.asyncio
async def test_start_face_search_invalid_s3_url_format(
        rekognition_service: RekognitionService,
        mock_rekognition_client: Mock
) -> None:
    """Test face search with invalid s3:// URL format."""
    invalid_url = "s3://bucket-only"

    with pytest.raises(ValueError) as exc_info:
        await rekognition_service.start_face_search(invalid_url)

    assert "Invalid S3 URL format" in str(exc_info.value)
    mock_rekognition_client.start_face_search.assert_not_called()


@pytest.mark.asyncio
async def test_start_face_search_invalid_http_url_format(
        rekognition_service: RekognitionService,
        mock_rekognition_client: Mock
) -> None:
    """Test face search with invalid http URL format."""
    invalid_url = "https://bucket.s3.region.amazonaws.com"

    with pytest.raises(ValueError) as exc_info:
        await rekognition_service.start_face_search(invalid_url)

    assert "Invalid S3 URL format" in str(exc_info.value)
    mock_rekognition_client.start_face_search.assert_not_called()


@pytest.mark.asyncio
async def test_start_face_search_client_error_during_start(
        rekognition_service: RekognitionService,
        mock_rekognition_client: Mock
) -> None:
    """Test face search handles ClientError during start_face_search."""
    mock_rekognition_client.start_face_search.side_effect = ClientError(
        {'Error': {'Code': 'InvalidParameterException'}},
        'StartFaceSearch'
    )

    with pytest.raises(RekognitionError) as exc_info:
        await rekognition_service.start_face_search(TEST_VIDEO_PATH)

    assert "Error starting face search" in str(exc_info.value)
    # Verify cleanup happens (job removed from set)
    from aws.rekognition.rekognition_service import RUNNING_FACE_SEARCH_JOBS
    assert TEST_VIDEO_PATH not in RUNNING_FACE_SEARCH_JOBS


@pytest.mark.asyncio
async def test_start_face_search_client_error_during_get_results(
        rekognition_service: RekognitionService,
        mock_rekognition_client: Mock
) -> None:
    """Test face search handles ClientError during get_face_search_results."""
    mock_rekognition_client.start_face_search.return_value = {'JobId': TEST_JOB_ID}
    mock_rekognition_client.get_face_search.side_effect = ClientError(
        {'Error': {'Code': 'ResourceNotFoundException'}},
        'GetFaceSearch'
    )

    with pytest.raises(RekognitionError) as exc_info:
        await rekognition_service.start_face_search(TEST_VIDEO_PATH)

    assert "Error getting face search results" in str(exc_info.value)
    # Verify cleanup happens (job removed from set)
    from aws.rekognition.rekognition_service import RUNNING_FACE_SEARCH_JOBS
    assert TEST_VIDEO_PATH not in RUNNING_FACE_SEARCH_JOBS


@pytest.mark.asyncio
async def test_start_face_search_success_no_matches(
        rekognition_service: RekognitionService,
        mock_rekognition_client: Mock
) -> None:
    """Test face search succeeds with no matches."""
    mock_rekognition_client.start_face_search.return_value = {'JobId': TEST_JOB_ID}
    mock_rekognition_client.get_face_search.return_value = {
        'JobStatus': 'SUCCEEDED',
        'Persons': []
    }

    matches, was_skipped = await rekognition_service.start_face_search(TEST_VIDEO_PATH)

    assert len(matches) == 0
    assert was_skipped is False
    mock_rekognition_client.start_face_search.assert_called_once()


@pytest.mark.asyncio
async def test_get_face_search_results_failed_job(
        rekognition_service: RekognitionService,
        mock_rekognition_client: Mock
) -> None:
    """Test get_face_search_results with failed job."""
    mock_rekognition_client.get_face_search.return_value = {
        'JobStatus': 'FAILED'
    }

    with pytest.raises(RekognitionError) as exc_info:
        await rekognition_service.get_face_search_results(TEST_JOB_ID)

    assert f"Face search job {TEST_JOB_ID} failed with status: FAILED" in str(exc_info.value)


@pytest.mark.asyncio
async def test_get_face_search_results_client_error(
        rekognition_service: RekognitionService,
        mock_rekognition_client: Mock
) -> None:
    """Test get_face_search_results handles ClientError during polling."""
    mock_rekognition_client.get_face_search.side_effect = ClientError(
        {'Error': {'Code': 'ResourceNotFoundException'}},
        'GetFaceSearch'
    )

    with pytest.raises(RekognitionError) as exc_info:
        await rekognition_service.get_face_search_results(TEST_JOB_ID)

    assert f"Error getting face search results for job {TEST_JOB_ID}" in str(exc_info.value)


@pytest.mark.asyncio
async def test_get_face_search_results_no_persons(
        rekognition_service: RekognitionService,
        mock_rekognition_client: Mock
) -> None:
    """Test get_face_search_results with no Persons in result."""
    mock_rekognition_client.get_face_search.return_value = {
        'JobStatus': 'SUCCEEDED',
        'Persons': []
    }

    matches = await rekognition_service.get_face_search_results(TEST_JOB_ID)

    assert len(matches) == 0


@pytest.mark.asyncio
async def test_get_face_search_results_persons_no_face_matches(
        rekognition_service: RekognitionService,
        mock_rekognition_client: Mock
) -> None:
    """Test get_face_search_results with Persons but no FaceMatches."""
    mock_rekognition_client.get_face_search.return_value = {
        'JobStatus': 'SUCCEEDED',
        'Persons': [
            {
                'Timestamp': 1000
                # No FaceMatches key
            },
            {
                'Timestamp': 2000,
                'FaceMatches': []  # Empty FaceMatches
            }
        ]
    }

    matches = await rekognition_service.get_face_search_results(TEST_JOB_ID)

    assert len(matches) == 0


@pytest.mark.asyncio
async def test_get_face_search_results_multiple_persons(
        rekognition_service: RekognitionService,
        mock_rekognition_client: Mock
) -> None:
    """Test get_face_search_results with multiple persons."""
    mock_rekognition_client.get_face_search.return_value = {
        'JobStatus': 'SUCCEEDED',
        'Persons': [
            {
                'Timestamp': 1000,
                'FaceMatches': [
                    {
                        'Face': {
                            'ExternalImageId': 'person1',
                            'FaceId': 'face1'
                        },
                        'Similarity': 90.0
                    }
                ]
            },
            {
                'Timestamp': 2000,
                'FaceMatches': [
                    {
                        'Face': {
                            'ExternalImageId': 'person2',
                            'FaceId': 'face2'
                        },
                        'Similarity': 85.0
                    }
                ]
            }
        ]
    }

    matches = await rekognition_service.get_face_search_results(TEST_JOB_ID)

    assert len(matches) == 2
    assert any(m['external_image_id'] == 'person1' and m['timestamp'] == 1000 for m in matches)
    assert any(m['external_image_id'] == 'person2' and m['timestamp'] == 2000 for m in matches)
