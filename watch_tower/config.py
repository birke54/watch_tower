"""
Centralized configuration management for Watch Tower.

This module provides a single source of truth for all application configuration
"""

import os
from typing import Optional
from dataclasses import dataclass
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

LOGGER = logging.getLogger(__name__)


@dataclass
class DatabaseConfig:
    """Database configuration settings."""
    pool_size: int = 5
    max_overflow: int = 10
    pool_recycle: int = 3600  # 1 hour
    pool_timeout: int = 5
    connect_timeout: int = 5


@dataclass
class VideoConfig:
    """Video processing configuration."""
    max_concurrent_uploads: int = 2
    max_concurrent_face_recognition: int = 2
    ffmpeg_timeout: int = 30  # video conversion timeout
    default_preset: str = 'medium'
    default_crf: int = 20
    rekognition_preset: str = 'fast'
    rekognition_crf: int = 25
    max_width: int = 1280
    max_height: int = 720
    polling_interval: int = 10


@dataclass
class CryptographyConfig:
    """Cryptography configuration."""
    key_size: int = 32  # 256 bits
    salt_size: int = 16  # 128 bits
    iv_size: int = 16  # 128 bits
    iterations: int = 100000


@dataclass
class RingConfig:
    """Ring camera configuration."""
    motion_poll_interval: int = 60
    user_agent: str = "WatchTower API"


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = os.getenv("LOG_LEVEL", "INFO")
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_file: str = os.getenv("LOG_FILE", "")
    max_file_size: int = 10  # MB
    max_files: int = 3


@dataclass
class CLIConfig:
    """CLI-specific configuration."""
    state_file_path: str = os.getenv(
        "WATCH_TOWER_STATE_FILE",
        "/tmp/watch_tower_business_logic_state.json")


@dataclass
class ManagementConfig:
    """Management API configuration."""
    host: str = os.getenv("MANAGEMENT_API_HOST", "0.0.0.0")
    port: int = int(os.getenv("MANAGEMENT_API_PORT", "8080"))
    log_level: str = os.getenv("MANAGEMENT_API_LOG_LEVEL", "info")
    access_log: bool = os.getenv("MANAGEMENT_API_ACCESS_LOG", "false").lower() == "true"


@dataclass
class AppConfig:
    """Main application configuration."""
    # Environment
    environment: str = os.getenv("ENVIRONMENT", "")
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"

    # AWS Configuration
    aws_region: str = os.getenv("AWS_REGION", "")
    aws_access_key_id: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    aws_secret_access_key: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")

    # Database Configuration
    db_secret_name: str = os.getenv("DB_SECRET_NAME", "")
    encryption_key_secret_name: str = os.getenv("ENCRYPTION_KEY_SECRET_NAME", "")

    # S3 Configuration
    event_recordings_bucket: str = os.getenv("EVENT_RECORDINGS_BUCKET", "")

    # Rekognition Configuration
    rekognition_collection_id: str = os.getenv("REKOGNITION_COLLECTION_ID", "")
    rekognition_s3_known_faces_bucket: str = os.getenv(
        "REKOGNITION_S3_KNOWN_FACES_BUCKET", "")
    sns_rekognition_video_analysis_topic_arn: str = os.getenv(
        "SNS_REKOGNITION_VIDEO_ANALYSIS_TOPIC_ARN", "")
    rekognition_video_service_role_arn: str = os.getenv(
        "REKOGNITION_VIDEO_SERVICE_ROLE_ARN", "")

    # Sub-configurations
    database: DatabaseConfig = DatabaseConfig()
    video: VideoConfig = VideoConfig()
    cryptography: CryptographyConfig = CryptographyConfig()
    ring: RingConfig = RingConfig()
    logging: LoggingConfig = LoggingConfig()
    cli: CLIConfig = CLIConfig()
    management: ManagementConfig = ManagementConfig()

    def validate(self, required_fields: Optional[list] = None) -> None:
        """
        Validate that all required configuration is present.

        Args:
            required_fields: List of required fields to validate. If None, validates all.
        """
        if required_fields is None:
            # Default required fields for production
            required_fields = [
                "aws_region",
                "aws_access_key_id",
                "aws_secret_access_key",
                "db_secret_name",
                "encryption_key_secret_name",
                "event_recordings_bucket",
                "rekognition_collection_id",
                "rekognition_s3_known_faces_bucket",
                "sns_rekognition_video_analysis_topic_arn",
                "rekognition_video_service_role_arn"
            ]

        missing_fields = []
        for field in required_fields:
            if not getattr(self, field):
                missing_fields.append(field)

        if missing_fields:
            raise ValueError(
                f"Missing required configuration: {', '.join(missing_fields)}")

    def validate_aws_only(self) -> None:
        """Validate only AWS-related configuration."""
        self.validate([
            "aws_region",
            "aws_access_key_id",
            "aws_secret_access_key"
        ])

    def validate_database_only(self) -> None:
        """Validate only database-related configuration."""
        self.validate([
            "db_secret_name",
            "encryption_key_secret_name"
        ])

    def validate_rekognition_only(self) -> None:
        """Validate only Rekognition-related configuration."""
        self.validate_aws_only()
        self.validate([
            "rekognition_collection_id",
            "rekognition_s3_known_faces_bucket",
            "sns_rekognition_video_analysis_topic_arn",
            "rekognition_video_service_role_arn"
        ])

    def validate_s3_only(self) -> None:
        """Validate only S3-related configuration."""
        self.validate_aws_only()
        self.validate([
            "event_recordings_bucket"
        ])


# Global configuration instance
config = AppConfig()

# Note: Configuration validation is not run automatically on import
# to allow for testing environments. Use config.validate() explicitly
# when you need to validate configuration in production code.
