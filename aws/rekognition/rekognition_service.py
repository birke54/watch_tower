from typing import Dict, Any, Tuple, List
import boto3
from botocore.exceptions import ClientError
from urllib.parse import urlparse
import asyncio

from aws.exceptions import ClientInitializationError, RekognitionError, RekognitionResourceNotFoundException
from aws.s3.s3_service import s3_service
from watch_tower.config import config
from utils.logging_config import get_logger
from utils.aws_client_factory import AWSClientFactory

LOGGER = get_logger(__name__)

# Constants
JOB_STATUS_SUCCEEDED = 'SUCCEEDED'
JOB_STATUS_FAILED = 'FAILED'

# Module-level tracking of running face search jobs to prevent duplicates
_running_face_search_jobs = set()


class RekognitionService:
    def __init__(self):
        """Initialize the Rekognition service with AWS credentials."""
        self._validate_environment_variables()
        self.client = self._initialize_rekognition_client()

    def _validate_environment_variables(self) -> None:
        """
        Validate that all required environment variables are present.

        Raises:
            ValueError: If any required environment variables are missing.
        """
        # Validate AWS and Rekognition configuration
        config.validate([
            "aws_region",
            "aws_access_key_id",
            "aws_secret_access_key",
            "rekognition_collection_id",
            "rekognition_s3_known_faces_bucket",
            "sns_rekognition_video_analysis_topic_arn",
            "rekognition_video_service_role_arn"
        ])

        self.region = config.aws_region
        self.access_key = config.aws_access_key_id
        self.secret_key = config.aws_secret_access_key
        self.collection_id = config.rekognition_collection_id
        self.bucket_name = config.rekognition_s3_known_faces_bucket
        self.sns_topic_arn = config.sns_rekognition_video_analysis_topic_arn
        self.role_arn = config.rekognition_video_service_role_arn

    def _initialize_rekognition_client(self) -> boto3.client:
        """
        Initialize the Rekognition client with AWS credentials.

        Returns:
            boto3.client: Initialized Rekognition client.

        Raises:
            ValueError: If client initialization fails.
        """
        try:
            return AWSClientFactory.create_rekognition_client()
        except Exception as e:
            LOGGER.error("Failed to initialize Rekognition client: %s", e)
            raise ClientInitializationError(
                f"Error initializing Rekognition client: {e}")

    def check_collection_exists(self, collection_id: str) -> None:
        """
        Check if a Rekognition collection exists.

        Args:
            collection_id (str): The ID of the collection to check.

        Raises:
            RekognitionResourceNotFoundException: If the collection doesn't exist.
            ClientError: If there's an AWS service error.
        """
        try:
            self.client.describe_collection(CollectionId=collection_id)
            LOGGER.info("Collection %d exists", collection_id)
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                raise RekognitionResourceNotFoundException(
                    f"Collection {collection_id} not found")
            raise RekognitionError(
                f"Collection {collection_id} not found: {e}")

    def index_faces(self, person_id: str) -> str:
        """
        Index faces of one or more images for a specific person.

        Args:
            person_id (str): The ID of the person to index faces for.
                This id needs to match the file name prefix of the images in the S3 bucket.

        Returns:
            str: The job ID of the face indexing job.

        Raises:
            ValueError: If no matching files are found or if face indexing fails.
            ClientError: If there's an AWS service error.
        """
        matching_s3_files = s3_service.get_files_with_prefix(
            self.bucket_name, person_id)

        if not matching_s3_files:
            raise ValueError(
                f"No matching files found for person ID: {person_id}")

        self.check_collection_exists(self.collection_id)

        try:
            returned_job_ids = []
            for file_path in matching_s3_files:
                response = self.client.index_faces(
                    CollectionId=self.collection_id,
                    ExternalImageId=person_id,
                    Image={
                        'S3Object': {
                            'Bucket': self.bucket_name,
                            'Name': file_path
                        }
                    }
                )
                returned_job_ids.append(response['JobId'])
                LOGGER.info("Indexed faces for %s from %s", person_id, file_path)
        except ClientError as e:
            LOGGER.error("Error indexing faces: %s", e)
            raise RekognitionError("Error indexing faces: %s", e)

        return response['JobId']

    async def start_face_search(
            self, source_video_path: str) -> Tuple[List[Dict[str, Any]], bool]:
        """
        Start a face search job on a video.

        Args:
            source_video_path (str): The S3 URL or object key of the video to search for faces in.

        Returns:
            Tuple[List[Dict[str, Any]], bool]: A tuple containing:
                - List of dictionaries containing face match details:
                    - external_image_id: The external image ID (person identifier)
                    - face_id: The Rekognition face ID
                    - confidence: The confidence score of the match
                    - timestamp: When in the video the person was detected
                - Boolean indicating if the job was skipped due to already running
                    - True if job was skipped (already running)
                    - False if job was executed (either found faces or completed with no faces)

        Raises:
            ClientError: If there's an AWS service error.
        """
        # Check if a job is already running for this video
        if source_video_path in _running_face_search_jobs:
            LOGGER.warning(
                "Face search job already running for video: %s", source_video_path)
            return [], True  # Return empty list and flag indicating job was skipped

        try:
            # Add to running jobs set
            _running_face_search_jobs.add(source_video_path)

            # Parse the S3 URL to extract bucket and object key
            if source_video_path.startswith('s3://'):
                # Extract bucket and key from s3:// URL
                path_without_protocol = source_video_path[5:]  # Remove 's3://'
                parts = path_without_protocol.split('/', 1)
                if len(parts) >= 2:
                    bucket_name = parts[0]
                    object_key = parts[1]
                else:
                    raise ValueError(
                        f"Invalid S3 URL format: {source_video_path}")
            elif source_video_path.startswith('http'):
                # Extract bucket and key from S3 URL
                parsed_url = urlparse(source_video_path)
                # URL format: https://bucket.s3.region.amazonaws.com/key
                path_parts = parsed_url.path.lstrip('/').split('/', 1)
                if len(path_parts) >= 2:
                    bucket_name = path_parts[0]
                    object_key = path_parts[1]
                else:
                    raise ValueError(
                        f"Invalid S3 URL format: {source_video_path}")
            else:
                # Assume it's just an object key, use the video recordings bucket
                bucket_name = config.event_recordings_bucket
                object_key = source_video_path

            LOGGER.info(
                "Starting face search for bucket: %s, object: %s", bucket_name, object_key)

            response = self.client.start_face_search(
                CollectionId=self.collection_id,
                Video={
                    'S3Object': {
                        'Bucket': bucket_name,
                        'Name': object_key
                    }
                },
                NotificationChannel={
                    'SNSTopicArn': self.sns_topic_arn,
                    'RoleArn': self.role_arn
                }
            )
            LOGGER.info(
                "Started face search job {response['JobId']} for video %s", source_video_path)
            face_search_results = await self.get_face_search_results(response['JobId'])

            # Return results and flag indicating job was executed
            return face_search_results, False
        except ClientError as e:
            LOGGER.error("Error starting face search: %s", e)
            raise RekognitionError(f"Error starting face search: {e}")
        finally:
            # Always remove from running jobs set
            _running_face_search_jobs.discard(source_video_path)

    async def get_face_search_results(self, job_id: str) -> List[Dict[str, Any]]:
        """
        Get the results of a face search job.

        Args:
            job_id (str): The ID of the face search job to get results for.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries containing face match details:
                - external_image_id: The external image ID (person identifier)
                - face_id: The Rekognition face ID
                - confidence: The confidence score of the match
                - timestamp: When in the video the person was detected

        Raises:
            ClientError: If there's an AWS service error.
            TimeoutError: If the job takes too long to complete.
        """
        polling_interval: int = config.video.polling_interval
        while True:
            try:
                result = self.client.get_face_search(JobId=job_id)
                LOGGER.info("Job %s status: {result['JobStatus']}", job_id)

                if result['JobStatus'] in [JOB_STATUS_SUCCEEDED, JOB_STATUS_FAILED]:
                    break

                LOGGER.info("Waiting for job %s to complete...", job_id)
                await asyncio.sleep(polling_interval)

            except ClientError as e:
                LOGGER.error(
                    "Error getting face search results for job %s: %s", job_id, e)
                raise RekognitionError(
                    "Error getting face search results for job %s: %s", job_id, e)

        matches: List[Dict[str, Any]] = []
        if result['JobStatus'] == JOB_STATUS_SUCCEEDED:
            LOGGER.info("Face search job %s succeeded", job_id)

            for person in result.get('Persons', []):
                timestamp = person.get('Timestamp', 0)
                if 'FaceMatches' in person:
                    for match in person['FaceMatches']:
                        face = match['Face']
                        external_image_id = face.get(
                            'ExternalImageId', 'Unknown')
                        face_id = face.get('FaceId', 'Unknown')
                        # Convert percentage to decimal
                        confidence = match.get('Similarity', 0.0) / 100.0

                        matches.append({
                            'external_image_id': external_image_id,
                            'face_id': face_id,
                            'confidence': confidence,
                            'timestamp': timestamp
                        })
        else:
            LOGGER.error(
                "Face search job %s failed with status: %s", job_id, result['JobStatus'])
            LOGGER.error(f"Full failure response: {result}")
            if 'StatusMessage' in result:
                LOGGER.error("Failure reason: %s", result['StatusMessage'])

        return matches


# Create a singleton instance
rekognition_service = RekognitionService()
