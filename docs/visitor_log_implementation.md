# Visitor Log Creation from Face Search Results

## Overview

This document explains how the system processes Rekognition face search results and creates visitor log entries in the database. **Person names are taken directly from the Rekognition service** using the `external_image_id` as the person identifier.

## Flow Diagram

```
Motion Event Detected
         ↓
   Video Uploaded to S3
         ↓
   Face Search Started
         ↓
   Face Search Completed
         ↓
   Process Results & Create Visitor Logs
         ↓
   Mark Event as Processed
```

## Implementation Details

### 1. Face Search Processing

The face search process is handled in `events_loop.py` in the `start_facial_recognition_tasks()` function:

- **Location**: `events_loop.py`
- **Function**: `start_facial_recognition_tasks()`
- **Purpose**: Processes unprocessed motion events and starts face search tasks
- **Concurrency Control**: Uses `face_recognition_semaphore` to limit concurrent face recognition operations
- **Task Management**: Tracks running tasks in `running_facial_recognition_tasks` set

### 2. Enhanced Face Search Results

The Rekognition service has been enhanced to return detailed face search results:

- **File**: `aws/rekognition/rekognition_service.py`
- **Method**: `get_face_search_results()`
- **Returns**: List of dictionaries containing:
  - `external_image_id`: Person identifier
  - `face_id`: Rekognition face ID
  - `confidence`: Confidence score (0.0-1.0)
  - `timestamp`: When in video the person was detected

### 3. Visitor Log Creation

Visitor logs are created in the `create_visitor_logs_from_face_search()` function:

- **Location**: `events_loop.py` 
- **Process**:
  1. Consolidate face search results to get the maximum confidence score for each person
  2. For each unique person found:
     - Create visitor log entry with:
       - `camera_name`: Camera name from the motion event
       - `persons_name`: Person name from `external_image_id`
       - `confidence_score`: Maximum confidence score for that person
       - `visited_at`: Motion detection timestamp

### 4. Database Schema

The visitor logs are stored in the `visitor_logs` table:

```sql
CREATE TABLE visitor_logs (
    visitor_log_id SERIAL PRIMARY KEY,
    camera_name TEXT NOT NULL,
    persons_name TEXT NOT NULL,
    confidence_score FLOAT8 NOT NULL,
    visited_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL
);
```

## Key Components

### Repositories Used

1. **MotionEventRepository**: Manages motion events and marks them as processed
2. **VisitorLogRepository**: Creates visitor log entries

### Business Logic Management

The events loop is managed by `BusinessLogicManager` which:
- Runs the main business logic loop with shutdown handling
- Provides heartbeat logging every 5 minutes
- Handles graceful shutdown and error recovery

### Concurrency Control

- **Upload Semaphore**: Limits concurrent video uploads (`upload_semaphore`)
- **Face Recognition Semaphore**: Limits concurrent face recognition operations (`face_recognition_semaphore`)
- **Task Tracking**: Maintains sets of running tasks for proper cleanup

### Error Handling

- Missing cameras are logged as errors
- Database errors are caught and logged with full tracebacks
- Face search failures are handled gracefully
- Task exceptions are logged and tasks are properly cleaned up

## Testing

Test scripts are available in the `scripts/` directory:

- `test_face_search_results.py` - Tests face search functionality
- `test_rekognition_person_names.py` - Tests person name resolution
- `resolve_face_names.py` - Utility for resolving face names

## Configuration

The following environment variables are required:

### AWS Configuration
- `AWS_ACCESS_KEY_ID`: AWS access key
- `AWS_SECRET_ACCESS_KEY`: AWS secret key
- `AWS_REGION`: AWS region

### Database Configuration
- `DB_SECRET_NAME`: AWS Secrets Manager secret name for database credentials
- `ENCRYPTION_KEY_SECRET_NAME`: AWS Secrets Manager secret name for encryption key

### Rekognition Configuration
- `REKOGNITION_COLLECTION_ID`: Face collection ID
- `REKOGNITION_S3_KNOWN_FACES_BUCKET`: S3 bucket for known face images
- `EVENT_RECORDINGS_BUCKET`: S3 bucket for video recordings
- `SNS_REKOGNITION_VIDEO_ANALYSIS_TOPIC_ARN`: SNS topic for job notifications
- `REKOGNITION_VIDEO_SERVICE_ROLE_ARN`: IAM role for Rekognition video analysis

### Video Processing Configuration
- `max_concurrent_face_recognition`: Maximum concurrent face recognition operations (default: 2)
- `max_concurrent_uploads`: Maximum concurrent video uploads (default: 2)

## Monitoring

The system logs:
- Face search start/completion
- Visitor log creation with person details and confidence scores
- Errors and warnings for missing data
- Processing status updates
- Heartbeat messages every 5 minutes when running in Docker

## Key Implementation Notes

### Consolidation Logic

The system consolidates multiple face detections of the same person in a single video by:
1. Grouping results by `external_image_id` (person name)
2. Taking the maximum confidence score for each person
3. Creating a single visitor log entry per person per event

### Simplified Schema

The current implementation uses a simplified schema that stores:
- `camera_name` as a string (not a foreign key)
- `persons_name` as a string (not a foreign key)
- Direct confidence scores and timestamps

This approach simplifies the implementation while still providing the necessary functionality.

### Task Lifecycle Management

- Tasks are created using `asyncio.create_task()`
- Running tasks are tracked in sets for proper cleanup
- Task completion callbacks remove tasks from tracking sets
- Small delays (0.1s) between task creation prevent system overload

## Future Enhancements

1. **Confidence Threshold**: Add configurable confidence threshold for visitor log creation
2. **Real-time Notifications**: Send notifications when known persons are detected
3. **Analytics**: Track visitor patterns and statistics