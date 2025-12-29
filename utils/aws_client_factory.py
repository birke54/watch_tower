"""
AWS client factory for Watch Tower.

This module provides a centralized factory for creating AWS clients,
reducing code duplication across S3 and Rekognition services.
"""

from typing import Any, Optional

import boto3
from botocore.exceptions import ClientError

from watch_tower.config import config
from utils.logging_config import get_logger
from utils.error_handler import handle_errors

LOGGER = get_logger(__name__)


class AWSClientFactory:
    """Factory for creating AWS clients with consistent configuration."""

    @staticmethod
    def create_client(
            service_name: str,
            region_name: Optional[str] = None,
            **kwargs: Any
    ) -> boto3.client:
        """
        Create an AWS client with consistent configuration.

        Args:
            service_name: AWS service name (e.g., 's3', 'rekognition')
            region_name: AWS region (defaults to config)
            **kwargs: Additional client configuration

        Returns:
            Configured boto3 client

        Raises:
            ClientError: If client creation fails
        """
        region = region_name or config.aws_region

        client_config = {
            'service_name': service_name,
            'region_name': region,
            'aws_access_key_id': config.aws_access_key_id,
            'aws_secret_access_key': config.aws_secret_access_key,
            **kwargs
        }

        LOGGER.debug("Creating AWS %s client for region %s", service_name, region)
        return boto3.client(**client_config)

    @staticmethod
    def create_s3_client(**kwargs: Any) -> boto3.client:
        """Create an S3 client."""
        return AWSClientFactory.create_client('s3', **kwargs)

    @staticmethod
    def create_rekognition_client(**kwargs: Any) -> boto3.client:
        """Create a Rekognition client."""
        return AWSClientFactory.create_client('rekognition', **kwargs)

    @staticmethod
    def create_secrets_manager_client(**kwargs: Any) -> boto3.client:
        """Create a Secrets Manager client."""
        return AWSClientFactory.create_client('secretsmanager', **kwargs)


def handle_aws_error(
        error: ClientError,
        operation: str,
        resource: str = ""
) -> None:
    """
    Handle AWS errors consistently.

    Args:
        error: The AWS ClientError
        operation: Description of the operation being performed
        resource: Optional resource name

    Raises:
        The original error with enhanced context
    """
    error_code = error.response['Error']['Code']
    error_message = error.response['Error']['Message']

    LOGGER.error(
        "AWS %s failed for %s: %s - %s",
        operation,
        resource,
        error_code,
        error_message
    )

    # Re-raise with enhanced context
    raise error
