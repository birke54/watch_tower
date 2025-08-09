import json
import boto3
from aws.exceptions import ClientError, ConfigError, NoCredentialsError, SecretsManagerError
from watch_tower.config import config


def get_db_secret(secret_name: str) -> dict:
    """
    Retrieve credentials from AWS Secrets Manager.

    Args:
        secret_name (str): The name of the secret to retrieve.

    Returns:
        dict: Database connection parameters

    Raises:
        SecretsManagerError: If there are issues with AWS credentials or secret retrieval
        DatabaseConfigError: If required environment variables are missing
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
        secret = json.loads(response['SecretString'])

        return secret

    except NoCredentialsError:
        raise SecretsManagerError(
            "AWS credentials not found. Please set up your AWS credentials."
        )
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']

        raise SecretsManagerError(
            f"AWS Secrets Manager Error: {error_code} Message: {error_message}"
        )
