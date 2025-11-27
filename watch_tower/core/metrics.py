"""
Prometheus metrics for Watch Tower.
"""

import enum

# Labels for Prometheus metrics
table_names = ["vendors", "motion_events", "visitor_logs"]

from prometheus_client import Counter, Guage, Histogram

rekognition_face_search_success_count = Counter(
    "face_search_success_count",
    "Number of successful face search operations",
)

rekognition_face_search_error_count = Counter(
    "face_search_error_count",
    "Number of errors encountered during face search operations",
)

rekognition_face_search_duration_seconds = Histogram(
    "face_search_duration_seconds",
    "Duration of face search operations in seconds",
)

s3_motion_video_upload_success_count = Counter(
    "s3_motion_video_upload_success_count",
    "Number of successful motion video uploads to S3",
)

s3_motion_video_upload_error_count = Counter(
    "s3_motion_video_upload_error_count",
    "Number of errors encountered during motion video uploads to S3",
)

s3_motion_video_upload_duration_seconds = Histogram(
    "s3_motion_video_upload_duration_seconds",
    "Duration of motion video uploads to S3 in seconds",
)

postgres_insert_success_count = Counter(
    "postgres_insert_success_count",
    "Number of successful inserts into PostgreSQL",
    table_names
)

postgres_insert_error_count = Counter(
    "postgres_insert_error_count",
    "Number of errors encountered during inserts into PostgreSQL",
    table_names
)

postgres_insert_duration_milliseconds = Histogram(
    "postgres_insert_duration_milliseconds",
    "Duration of inserts into PostgreSQL in milliseconds",
    table_names
)