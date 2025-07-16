"""
CLI Configuration Validation Utilities

This module contains functions for validating various configuration sections
and returning structured validation results.
"""

from typing import Any, Dict, List

from cli.utils.errors import create_validation_result
from watch_tower.config import config


def validate_aws_config() -> List[Dict[str, Any]]:
    """Validate AWS configuration and return detailed results."""
    
    results = []
    
    # AWS Region
    if config.aws_region:
        results.append(create_validation_result('✅', 'aws_region', config.aws_region))
    else:
        results.append(create_validation_result('❌', 'aws_region', None, "Set AWS_REGION environment variable"))
    
    # AWS Access Key ID
    if config.aws_access_key_id:
        masked_key = config.aws_access_key_id[:4] + '*' * (len(config.aws_access_key_id) - 8) + config.aws_access_key_id[-4:]
        results.append(create_validation_result('✅', 'aws_access_key_id', '***'))
    else:
        results.append(create_validation_result('❌', 'aws_access_key_id', None, "Set AWS_ACCESS_KEY_ID environment variable"))
    
    # AWS Secret Access Key
    if config.aws_secret_access_key:
        results.append(create_validation_result('✅', 'aws_secret_access_key', '***'))
    else:
        results.append(create_validation_result('❌', 'aws_secret_access_key', None, "Set AWS_SECRET_ACCESS_KEY environment variable"))
    
    return results


def validate_database_config() -> List[Dict[str, Any]]:
    """Validate database configuration and return detailed results."""
    
    results = []
    
    # Database Secret Name
    if config.db_secret_name:
        results.append(create_validation_result('✅', 'db_secret_name', config.db_secret_name))
    else:
        results.append(create_validation_result('❌', 'db_secret_name', None, "Set DB_SECRET_NAME environment variable"))
    
    # Encryption Key Secret Name
    if config.encryption_key_secret_name:
        results.append(create_validation_result('✅', 'encryption_key_secret_name', config.encryption_key_secret_name))
    else:
        results.append(create_validation_result('❌', 'encryption_key_secret_name', None, "Set ENCRYPTION_KEY_SECRET_NAME environment variable"))
    
    return results


def validate_ring_config() -> List[Dict[str, Any]]:
    """Validate Ring configuration and return detailed results."""
    results = []
    
    # Ring credentials are stored in database, which is the correct approach
    results.append(create_validation_result('✅', 'ring_credentials', 'database_stored', "Ring authentication is handled via the vendors database table"))
    
    return results


def validate_app_config() -> List[Dict[str, Any]]:
    """Validate application configuration and return detailed results."""
    
    results = []
    
    # S3 Event Recordings Bucket
    if config.event_recordings_bucket:
        results.append(create_validation_result('✅', 'event_recordings_bucket', config.event_recordings_bucket))
    else:
        results.append(create_validation_result('❌', 'event_recordings_bucket', None, "Set EVENT_RECORDINGS_BUCKET environment variable"))
    
    # Rekognition Collection ID
    if config.rekognition_collection_id:
        results.append(create_validation_result('✅', 'rekognition_collection_id', config.rekognition_collection_id))
    else:
        results.append(create_validation_result('❌', 'rekognition_collection_id', None, "Set REKOGNITION_COLLECTION_ID environment variable"))
    
    # Rekognition Known Faces Bucket
    if config.rekognition_s3_known_faces_bucket:
        results.append(create_validation_result('✅', 'rekognition_s3_known_faces_bucket', config.rekognition_s3_known_faces_bucket))
    else:
        results.append(create_validation_result('❌', 'rekognition_s3_known_faces_bucket', None, "Set REKOGNITION_S3_KNOWN_FACES_BUCKET environment variable"))
    
    # SNS Topic ARN
    if config.sns_rekognition_video_analysis_topic_arn:
        results.append(create_validation_result('✅', 'sns_rekognition_video_analysis_topic_arn', config.sns_rekognition_video_analysis_topic_arn))
    else:
        results.append(create_validation_result('❌', 'sns_rekognition_video_analysis_topic_arn', None, "Set SNS_REKOGNITION_VIDEO_ANALYSIS_TOPIC_ARN environment variable"))
    
    # Rekognition Service Role ARN
    if config.rekognition_video_service_role_arn:
        results.append(create_validation_result('✅', 'rekognition_video_service_role_arn', config.rekognition_video_service_role_arn))
    else:
        results.append(create_validation_result('❌', 'rekognition_video_service_role_arn', None, "Set REKOGNITION_VIDEO_SERVICE_ROLE_ARN environment variable"))
    
    # Environment
    results.append(create_validation_result('ℹ️', 'environment', config.environment))
    
    # Debug Mode
    debug_status = "Enabled" if config.debug else "Disabled"
    results.append(create_validation_result('ℹ️', 'debug', config.debug))
    
    return results 