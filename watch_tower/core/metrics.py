"""
Prometheus metrics for Watch Tower.
"""

import enum

# Labels for Prometheus metrics
# Table names for database metrics (used as label values)
table_names = ["vendors", "motion_events", "visitor_logs"]
# Label name for database metrics
database_table_label = "table"

# Custom Histogram buckets
second_to_five_minutes_buckets = (
    1.0, 2.0, 5.0, 10.0, 15.0, 30.0, 60.0, 120.0, 300.0, 600.0, 900.0, 1200.0, 1500.0, 1800.0, 2400.0, 3000.0
)
millisecond_to_second = (
    .001, .010, .025, .05, .075, .1, .25, .5, .75, 1.0, 2.5, 5.0, 7.5, 10.0
)

from prometheus_client import Counter, Gauge, Histogram

# AWS Rekognition Face Search Metrics
aws_rekognition_face_search_success_count = Counter(
    "aws_rekognition_face_search_success_count",
    "Number of successful face search operations",
)
aws_rekognition_face_search_error_count = Counter(
    "aws_rekognition_face_search_error_count",
    "Number of failed face search operations",
)
aws_rekognition_face_search_duration_seconds = Histogram(
    "aws_rekognition_face_search_duration_seconds",
    "Duration of face search operations in seconds",
    buckets=second_to_five_minutes_buckets,
)
aws_rekognition_face_search_semaphore_job_count = Gauge(
    "aws_rekognition_face_search_semaphore_job_count",
    "Number of concurrent face search jobs being processed",
)

# AWS S3 Metrics
aws_s3_download_file_success_count = Counter(
    "aws_s3_download_file_success_count",
    "Number of successful S3 file download operations",
)
aws_s3_download_file_error_count = Counter(
    "aws_s3_download_file_error_count",
    "Number of failed S3 file download operations",
)
aws_s3_upload_file_success_count = Counter(
    "aws_s3_upload_file_success_count",
    "Number of successful S3 file upload operations",
)
aws_s3_upload_file_error_count = Counter(
    "aws_s3_upload_file_error_count",
    "Number of failed S3 file upload operations",
)
aws_s3_upload_semaphore_job_count = Gauge(
    "aws_s3_upload_semaphore_job_count",
    "Number of concurrent S3 upload jobs being processed",
)

#Ring camera Metrics
ring_retrieve_motion_events_success_count = Counter(
    "ring_retrieve_motion_events_success_count",
    "Number of successful Ring motion event retrievals",
)
ring_retrieve_motion_events_error_count = Counter(
    "ring_retrieve_motion_events_error_count",
    "Number of failed Ring motion event retrievals",
)
ring_retrieve_motion_events_duration = Histogram(
    "ring_retrieve_motion_events_duration_seconds",
    "Duration of Ring motion event retrievals in seconds",
    buckets=millisecond_to_second,
)
ring_retrieve_video_success_count = Counter(
    "ring_retrieve_video_success_count",
    "Number of successful Ring video retrievals",
)
ring_retrieve_video_error_count = Counter(
    "ring_retrieve_video_error_count",
    "Number of failed Ring video retrievals",
)
ring_retrieve_video_duration = Histogram(
    "ring_retrieve_video_duration_seconds",
    "Duration of Ring video retrievals in seconds",
    buckets=second_to_five_minutes_buckets,
)

# Ring connection manager metrics
ring_login_success_count = Counter(
    "ring_login_success_count",
    "Number of successful Ring login attempts",
)
ring_login_error_count = Counter(
    "ring_login_error_count",
    "Number of failed Ring login attempts",
)
ring_logout_success_count = Counter(
    "ring_logout_success_count",
    "Number of successful Ring logout attempts",
)
ring_logout_error_count = Counter(
    "ring_logout_error_count",
    "Number of failed Ring logout attempts",
)
ring_token_update_success_count = Counter(
    "ring_token_update_success_count",
    "Number of successful Ring token updates",
)
ring_token_update_error_count = Counter(
    "ring_token_update_error_count",
    "Number of failed Ring token updates",
)

# AES Encryption/Decryption metrics
aes_encrypt_success_count = Counter(
    "aes_encrypt_success_count",
    "Number of successful AES encryption operations",
)
aes_encrypt_error_count = Counter(
    "aes_encrypt_error_count",
    "Number of failed AES encryption operations",
)
aes_decrypt_success_count = Counter(
    "aes_decrypt_success_count",
    "Number of successful AES decryption operations",
)
aes_decrypt_error_count = Counter(
    "aes_decrypt_error_count",
    "Number of failed AES decryption operations",
)

#Bootstrap metrics
watch_tower_bootstrap_success_count = Counter(
    "watch_tower_bootstrap_success_count",
    "Number of successful Watch Tower bootstrap operations",
)
watch_tower_bootstrap_error_count = Counter(
    "watch_tower_bootstrap_error_count",
    "Number of failed Watch Tower bootstrap operations",
)

# Business Logic Manager metrics
watch_tower_business_logic_start_success_count = Counter(
    "watch_tower_business_logic_start_success_count",
    "Number of successful Watch Tower business logic start operations",
)
watch_tower_business_logic_start_error_count = Counter(
    "watch_tower_business_logic_start_error_count",
    "Number of failed Watch Tower business logic start operations",
)
watch_tower_business_logic_stop_success_count = Counter(
    "watch_tower_business_logic_stop_success_count",
    "Number of successful Watch Tower business logic stop operations",
)
watch_tower_business_logic_stop_error_count = Counter(
    "watch_tower_business_logic_stop_error_count",
    "Number of failed Watch Tower business logic stop operations",
)

# DB operation metrics
database_insert_success_count = Counter(
    "database_insert_success_count",
    "Number of successful database insert operations",
    labelnames=[database_table_label],
)
database_insert_failure_count = Counter(
    "database_insert_failure_count",
    "Number of failed database insert operations",
    labelnames=[database_table_label],
)

# Camera registry metrics
camera_registry_add_camera_success_count = Counter(
    "camera_registry_add_camera_success_count",
    "Number of successful camera registry add camera operations",
)
camera_registry_add_camera_error_count = Counter(
    "camera_registry_add_camera_error_count",
    "Number of failed camera registry add camera operations",
)
camera_registry_remove_camera_success_count = Counter(
    "camera_registry_remove_camera_success_count",
    "Number of successful camera registry remove camera operations",
)
camera_registry_remove_camera_error_count = Counter(
    "camera_registry_remove_camera_error_count",
    "Number of failed camera registry remove camera operations",
)
camera_registry_active_camera_count = Gauge(
    "camera_registry_active_camera_count",
    "Number of active cameras in the camera registry",
)
camera_registry_inactive_camera_count = Gauge(
    "camera_registry_inactive_camera_count",
    "Number of inactive cameras in the camera registry",
)

#Connection manager metrics
connection_manager_registry_add_connection_success_count = Counter(
    "connection_manager_registry_add_connection_success_count",
    "Number of successful connection manager registry add connection operations",
)
connection_manager_registry_add_connection_error_count = Counter(
    "connection_manager_registry_add_connection_error_count",
    "Number of failed connection manager registry add connection operations",
)
connection_manager_registry_active_connection_count = Gauge(
    "connection_manager_registry_active_connection_count",
    "Number of active connections in the connection manager registry",
)
connection_manager_registry_inactive_connection_count = Gauge(
    "connection_manager_registry_inactive_connection_count",
    "Number of inactive connections in the connection manager registry",
)


class MetricNames(enum.Enum):
    AWS_REKOGNITION_FACE_SEARCH_SUCCESS_COUNT = "aws_rekognition_face_search_success_count"
    AWS_REKOGNITION_FACE_SEARCH_ERROR_COUNT = "aws_rekognition_face_search_error_count"
    AWS_REKOGNITION_FACE_SEARCH_DURATION_SECONDS = "aws_rekognition_face_search_duration_seconds"
    AWS_REKOGNITION_FACE_SEARCH_SEMAPHORE_JOB_COUNT = "aws_rekognition_face_search_semaphore_job_count"
    AWS_S3_DOWNLOAD_FILE_SUCCESS_COUNT = "aws_s3_download_file_success_count"
    AWS_S3_DOWNLOAD_FILE_ERROR_COUNT = "aws_s3_download_file_error_count"
    AWS_S3_UPLOAD_FILE_SUCCESS_COUNT = "aws_s3_upload_file_success_count"
    AWS_S3_UPLOAD_FILE_ERROR_COUNT = "aws_s3_upload_file_error_count"
    AWS_S3_UPLOAD_SEMAPHORE_JOB_COUNT = "aws_s3_upload_semaphore_job_count"
    RING_RETRIEVE_MOTION_EVENTS_SUCCESS_COUNT = "ring_retrieve_motion_events_success_count"
    RING_RETRIEVE_MOTION_EVENTS_ERROR_COUNT = "ring_retrieve_motion_events_error_count"
    RING_RETRIEVE_MOTION_EVENTS_DURATION_SECONDS = "ring_retrieve_motion_events_duration_seconds"
    RING_RETRIEVE_VIDEO_SUCCESS_COUNT = "ring_retrieve_video_success_count"
    RING_RETRIEVE_VIDEO_ERROR_COUNT = "ring_retrieve_video_error_count"
    RING_RETRIEVE_VIDEO_DURATION_SECONDS = "ring_retrieve_video_duration_seconds"
    RING_LOGIN_SUCCESS_COUNT = "ring_login_success_count"
    RING_LOGIN_ERROR_COUNT = "ring_login_error_count"
    RING_LOGOUT_SUCCESS_COUNT = "ring_logout_success_count"
    RING_LOGOUT_ERROR_COUNT = "ring_logout_error_count"
    RING_TOKEN_UPDATE_SUCCESS_COUNT = "ring_token_update_success_count"
    RING_TOKEN_UPDATE_ERROR_COUNT = "ring_token_update_error_count"
    AES_ENCRYPT_SUCCESS_COUNT = "aes_encrypt_success_count"
    AES_ENCRYPT_ERROR_COUNT = "aes_encrypt_error_count"
    AES_DECRYPT_SUCCESS_COUNT = "aes_decrypt_success_count"
    AES_DECRYPT_ERROR_COUNT = "aes_decrypt_error_count"
    WATCH_TOWER_BOOTSTRAP_SUCCESS_COUNT = "watch_tower_bootstrap_success_count"
    WATCH_TOWER_BOOTSTRAP_ERROR_COUNT = "watch_tower_bootstrap_error_count"
    WATCH_TOWER_BUSINESS_LOGIC_START_SUCCESS_COUNT = "watch_tower_business_logic_start_success_count"
    WATCH_TOWER_BUSINESS_LOGIC_START_ERROR_COUNT = "watch_tower_business_logic_start_error_count"
    WATCH_TOWER_BUSINESS_LOGIC_STOP_SUCCESS_COUNT = "watch_tower_business_logic_stop_success_count"
    WATCH_TOWER_BUSINESS_LOGIC_STOP_ERROR_COUNT = "watch_tower_business_logic_stop_error_count"
    DATABASE_INSERT_SUCCESS_COUNT = "database_insert_success_count"
    DATABASE_INSERT_FAILURE_COUNT = "database_insert_failure_count"
    CAMERA_REGISTRY_ADD_CAMERA_SUCCESS_COUNT = "camera_registry_add_camera_success_count"
    CAMERA_REGISTRY_ADD_CAMERA_ERROR_COUNT = "camera_registry_add_camera_error_count"
    CAMERA_REGISTRY_REMOVE_CAMERA_SUCCESS_COUNT = "camera_registry_remove_camera_success_count"
    CAMERA_REGISTRY_REMOVE_CAMERA_ERROR_COUNT = "camera_registry_remove_camera_error_count"
    CAMERA_REGISTRY_ACTIVE_CAMERA_COUNT = "camera_registry_active_camera_count"
    CAMERA_REGISTRY_INACTIVE_CAMERA_COUNT = "camera_registry_inactive_camera_count"
    CONNECTION_MANAGER_REGISTRY_ADD_CONNECTION_SUCCESS_COUNT = "connection_manager_registry_add_connection_success_count"
    CONNECTION_MANAGER_REGISTRY_ADD_CONNECTION_ERROR_COUNT = "connection_manager_registry_add_connection_error_count"
    CONNECTION_MANAGER_REGISTRY_ACTIVE_CONNECTION_COUNT = "connection_manager_registry_active_connection_count"
    CONNECTION_MANAGER_REGISTRY_INACTIVE_CONNECTION_COUNT = "connection_manager_registry_inactive_connection_count"