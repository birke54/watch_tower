"""
AWS S3 Service

This module provides functionality for interacting with AWS S3 service,
including file uploads, downloads, bucket operations, and object listing.
"""
import os
from typing import List

import boto3
import botocore
from botocore.exceptions import ClientError

from aws.exceptions import AWSCredentialsError, AWSClientInitializationError, S3Error, S3ResourceNotFoundException
from watch_tower.config import config
from utils.logging_config import get_logger
from utils.aws_client_factory import AWSClientFactory
from utils.metrics import MetricDataPointName
from utils.metric_helpers import inc_counter_metric

LOGGER = get_logger(__name__)


class S3Service:
    """
    Service for interacting with AWS S3 API.

    This service provides methods for:
    - Checking bucket existence
    - Uploading and downloading files
    - Listing objects with prefixes
    - Managing S3 bucket operations
    """
    def __init__(self) -> None:
        """Initialize the S3 service with AWS credentials."""
        self._validate_environment_variables()
        self.client = S3Service._initialize_s3_client()

    def _validate_environment_variables(self) -> None:
        """
        Validate that all required environment variables are present.

        Raises:
            ValueError: If any required environment variables are missing.
        """
        # Only validate AWS/S3 configuration
        config.validate_s3_only()

        self.region = config.aws_region
        self.access_key = config.aws_access_key_id
        self.secret_key = config.aws_secret_access_key

    @staticmethod
    def _initialize_s3_client() -> boto3.client:
        """
        Initialize the S3 client with AWS credentials.

        Returns:
            boto3.client: Initialized S3 client.

        Raises:
            AWSCredentialsError: If AWS credentials are missing or invalid.
            AWSClientInitializationError: If client initialization fails.
        """
        try:
            return AWSClientFactory.create_s3_client()
        except botocore.exceptions.NoCredentialsError as e:
            LOGGER.error("No AWS credentials found while creating S3 client: %s", e)
            raise AWSCredentialsError(
                f"No AWS credentials found while creating S3 client: {e}")
        except botocore.exceptions.ClientError as e:
            LOGGER.error("Error creating S3 client: %s", e)
            raise AWSClientInitializationError(
                f"Error creating S3 client: {e}")

    def check_bucket_exists(self, bucket_name: str) -> bool:
        """
        Check if an S3 bucket exists.

        Args:
            bucket_name (str): The name of the S3 bucket to check.

        Returns:
            bool: True if the bucket exists.

        Raises:
            S3ResourceNotFoundException: If the bucket doesn't exist.
            ClientError: If there's an AWS service error.
        """
        try:
            self.client.head_bucket(Bucket=bucket_name)
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                LOGGER.warning("Bucket %s does not exist", bucket_name)
                raise S3ResourceNotFoundException(
                    f"Bucket {bucket_name} not found") from e
            LOGGER.error("Error checking bucket %s: %s", bucket_name, e)
            raise S3Error(f"Error checking bucket {bucket_name}: {e}") from e

    def get_files_with_prefix(self, bucket_name: str, prefix: str) -> List[str]:
        """
        Get all files in the S3 bucket that match the prefix.

        Args:
            bucket_name (str): The name of the S3 bucket to search in.
            prefix (str): The prefix of the files to search for.

        Returns:
            List[str]: A list of file paths that match the prefix.

        Raises:
            S3ResourceNotFoundException: If the bucket doesn't exist.
            ClientError: If there's an AWS service error.
        """
        self.check_bucket_exists(bucket_name)

        try:
            response = self.client.list_objects_v2(
                Bucket=bucket_name,
                Prefix=prefix
            )

            file_paths = [
                f"s3://{bucket_name}/{obj['Key']}"
                for obj in response.get('Contents', [])
                if obj['Key'].startswith(prefix)
            ]

            LOGGER.info(
                "Found %d files with prefix %s in bucket %s", len(file_paths), prefix, bucket_name)
            return file_paths

        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                LOGGER.error("Bucket %s not found", bucket_name)
                raise S3ResourceNotFoundException(
                    f"Bucket {bucket_name} not found")
            LOGGER.error("Error listing objects in bucket %s: %s", bucket_name, e)
            raise S3Error(
                f"Error listing objects in bucket {bucket_name}: {e}")

    def download_file(self, bucket_name: str, object_key: str, local_path: str) -> None:
        """
        Download a file from S3 to a local path.

        Args:
            bucket_name (str): The name of the S3 bucket.
            object_key (str): The key (path) of the object in S3.
            local_path (str): The local path where the file should be saved.

        Raises:
            S3ResourceNotFoundException: If the bucket or object doesn't exist.
            S3Error: If there's an AWS service error.
            OSError: If there's a filesystem error.
        """
        success = False
        try:
            self.check_bucket_exists(bucket_name)

            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            # Download the file
            self.client.download_file(bucket_name, object_key, local_path)
            success = True
            LOGGER.info(
                "Successfully downloaded s3://%s/%s to %s", bucket_name, object_key, local_path)

        except OSError as e:
            LOGGER.error(
                "Filesystem error downloading file from s3://%s/%s to %s: %s",
                bucket_name, object_key, local_path, e)
            raise
        except (S3ResourceNotFoundException, ClientError) as e:
            LOGGER.warning(
                "Bucket %s does not exist or error downloading file from s3://%s/%s: %s",
                bucket_name, bucket_name, object_key, e)
            raise S3Error(
                f"Bucket {bucket_name} does not exist or error downloading file "
                f"from s3://{bucket_name}/{object_key}: {e}") from e
        finally:
            if success:
                inc_counter_metric(MetricDataPointName.AWS_S3_DOWNLOAD_FILE_SUCCESS_COUNT)
            else:
                inc_counter_metric(MetricDataPointName.AWS_S3_DOWNLOAD_FILE_ERROR_COUNT)

    def upload_file(self, local_path: str, bucket_name: str, object_key: str) -> None:
        """
        Upload a file to S3.

        Args:
            local_path (str): The local file path to upload.
            bucket_name (str): The name of the S3 bucket.
            object_key (str): The key (path) for the object in S3.

        Raises:
            S3ResourceNotFoundException: If the bucket doesn't exist.
            S3Error: If there's an AWS service error.
            FileNotFoundError: If the local file does not exist.
            OSError: If there's a filesystem error.
        """
        success = False
        try:
            if not os.path.isfile(local_path):
                raise FileNotFoundError(f"Local file {local_path} does not exist.")

            self.check_bucket_exists(bucket_name)
            self.client.upload_file(local_path, bucket_name, object_key)
            success = True
            LOGGER.info(
                "Successfully uploaded %s to s3://%s/%s", local_path, bucket_name, object_key)

        except FileNotFoundError as e:
            LOGGER.warning("Local file %s does not exist.", local_path)
            raise
        except (S3ResourceNotFoundException, ClientError) as e:
            LOGGER.warning(
                "Bucket %s does not exist or error uploading file %s to s3://%s/%s: %s",
                bucket_name, local_path, bucket_name, object_key, e)
            raise S3Error(
                f"Bucket {bucket_name} does not exist or error uploading file "
                f"{local_path} to s3://{bucket_name}/{object_key}: {e}") from e
        finally:
            if success:
                inc_counter_metric(MetricDataPointName.AWS_S3_UPLOAD_FILE_SUCCESS_COUNT)
            else:
                inc_counter_metric(MetricDataPointName.AWS_S3_UPLOAD_FILE_ERROR_COUNT)

# Create a singleton instance
S3_SERVICE = S3Service()
