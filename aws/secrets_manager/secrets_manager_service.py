"""
AWS Secrets Manager Service

This module provides functionality for retrieving secrets from AWS Secrets Manager,
specifically for database credentials and other sensitive configuration data.
"""
import json

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from aws.exceptions import AWSCredentialsError, SecretsManagerError
from watch_tower.config import config
from utils.logging_config import get_logger

LOGGER = get_logger(__name__)


def get_db_secret(secret_name: str) -> dict:
    """
    Retrieve credentials from AWS Secrets Manager.

    Args:
        secret_name (str): The name of the secret to retrieve.

    Returns:
        dict: Secret data

    Raises:
        AWSCredentialsError: If AWS credentials are missing or invalid
        SecretsManagerError: If there are issues retrieving the secret from AWS Secrets Manager
    """
    config.validate_aws_only()

    try:
        # Create AWS session and client
        session = boto3.Session()
        client = session.client(
            service_name='secretsmanager',
            region_name=config.aws_region,
            aws_access_key_id=config.aws_access_key_id,
            aws_secret_access_key=config.aws_secret_access_key
        )

        # Get secret value
        response = client.get_secret_value(SecretId=secret_name)
        return json.loads(response['SecretString'])
    except NoCredentialsError as e:
        LOGGER.error("No AWS credentials found while creating Secrets Manager client: %s", e)
        raise AWSCredentialsError(
            f"No AWS credentials found while creating Secrets Manager client: {e}")
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', str(e))
        raise SecretsManagerError(
            f"AWS Secrets Manager Error: {error_code} Message: {error_message}"
        ) from e
    except json.JSONDecodeError as e:
        raise SecretsManagerError(
            f"Failed to parse secret JSON: {str(e)}"
        ) from e
