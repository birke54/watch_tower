# Ring Camera Integration

## Overview

Watch Tower integrates with Ring cameras through a plugin-based architecture. This document focuses on the Ring API integration, architecture, and usage patterns.

## Architecture

### Plugin System
Ring cameras are implemented as a plugin using the `PluginType.RING` enum. The system follows a modular design with clear separation of concerns:

- **Connection Management**: Handles authentication, token management, and API communication
- **Camera Interface**: Provides standardized camera operations
- **Event Processing**: Manages motion events and video processing
- **Data Storage**: Handles credential encryption and event persistence

### Key Components
- `connection_managers/ring_connection_manager.py` - Ring API authentication and communication
- `cameras/ring_camera.py` - Ring camera implementation
- `data_models/motion_event.py` - Motion event data structure
- `watch_tower/core/bootstrap.py` - Camera discovery and registration
- `db/repositories/vendors_repository.py` - Vendor credential management
- `db/cryptography/aes.py` - Credential encryption/decryption

## Authentication System

### Overview
The Ring integration uses a sophisticated authentication system with multiple fallback mechanisms:

1. **Token-based Authentication**: Uses stored OAuth tokens for fast authentication
2. **Credential-based Authentication**: Falls back to username/password when tokens expire
3. **Two-Factor Authentication**: Automatically handles 2FA requirements
4. **Token Persistence**: Tokens are stored encrypted in the database

### Credential Storage
Ring credentials are stored encrypted in the database using AES encryption. The system automatically handles:
- Credential encryption/decryption
- Token storage and retrieval
- Token expiration management
- Secure credential updates

### Authentication Flow
1. System attempts to authenticate using existing token
2. If token is invalid/expired, falls back to stored credentials
3. If 2FA is required, prompts user for authentication code
4. New token is automatically stored for future use (as plain JSON)

## Camera Operations

### Motion Event Retrieval
The system polls Ring cameras for motion events within specified time ranges. Events are filtered and converted to standardized `MotionEvent` objects with:
- Event timestamps
- Camera identification
- Event metadata from Ring API
- Unique event IDs for tracking

### Video Processing Pipeline
When motion events are detected, the system:

1. **Downloads** video from Ring servers
2. **Converts** video to H.264 format (if needed for AWS Rekognition)
3. **Uploads** processed video to S3
4. **Updates** database with S3 URL and processing timestamps
5. **Cleans up** temporary files

### Health Monitoring
Cameras are continuously monitored for:
- Connection status
- Battery life
- Firmware version
- Motion detection settings
- Volume settings

## Data Models

### MotionEvent Structure
Motion events are standardized across all camera types:

```python
@dataclass
class MotionEvent:
    event_id: str                    # Unique event identifier
    camera_vendor: PluginType        # PluginType.RING
    camera_name: str                 # Human-readable camera name
    timestamp: datetime              # Event timestamp (Pacific timezone)
    video_file: Optional[bytes]      # Local video data (if available)
    s3_url: Optional[str]            # S3 URL after upload
    event_metadata: Dict[str, Any]   # Ring-specific event data
```

### Event Metadata
Ring events include rich metadata such as:
- Ring event ID
- Doorbot information
- Event type (motion, doorbell, etc.)
- Device properties

## Configuration

### Ring-Specific Settings
The system uses a minimal configuration approach:

```python
@dataclass
class RingConfig:
    motion_poll_interval: int = 60  # Polling interval in seconds
    user_agent: str = "WatchTower API"
```

### Database Setup
Ring credentials are stored in the `vendors` table:

```sql
INSERT INTO vendors (name, username, password_enc, plugin_type, auth_data) 
VALUES ('Ring Account', 'your_ring_username', 'your_encrypted_password', 'RING', '{}');
```

## Error Handling

### Authentication Errors
- Invalid credentials are logged with appropriate error messages
- Token expiration triggers automatic re-authentication
- 2FA failures are handled gracefully with user prompts

### Video Processing Errors
- Failed downloads are logged with cleanup
- Video conversion failures are logged with cleanup
- S3 upload failures trigger cleanup and error reporting

### Network Errors
- Connection timeouts are logged with error reporting
- Network errors are logged
- API errors are logged with context

## Performance Considerations

### Connection Management
- OAuth tokens are cached in memory for fast access
- Database persistence ensures tokens survive application restarts
- Token refresh occurs when authentication fails due to expired tokens

### Video Processing
- Videos are processed asynchronously to avoid blocking
- Temporary files are cleaned up immediately after processing
- H.264 conversion only occurs when necessary
- Streaming downloads reduce memory usage

### Resource Management
- Database connection pooling for efficient database access
- Proper cleanup of temporary files and resources
- Memory-efficient video processing

## Testing

### Unit Testing
The Ring integration includes comprehensive unit tests covering:
- Authentication flows
- Camera operations
- Event processing
- Error handling scenarios

**Note**: No integration tests exist. All tests use mocks and don't test against the real Ring API.

### Test Examples
```python
# Test camera initialization
camera = RingCamera(mock_device_object)
assert camera.plugin_type == PluginType.RING
assert camera.camera_name == "Test Camera"

# Test motion event retrieval
events = await camera.retrieve_motion_events(from_time, to_time)
assert len(events) == 1
assert isinstance(events[0], MotionEvent)
```

## Troubleshooting

### Common Issues

#### Authentication Failures
- **Problem**: "Failed to authenticate with Ring"
- **Solution**: Check stored credentials in database and verify 2FA settings

#### Video Processing Errors
- **Problem**: "No video URL found for Ring event"
- **Solution**: Verify Ring subscription status and camera permissions

#### Connection Issues
- **Problem**: "Error retrieving cameras"
- **Solution**: Check network connectivity and Ring API status

### Debug Mode
Enable detailed logging by setting `LOG_LEVEL=DEBUG` to see:
- Authentication flow details (token loading, expiration timestamps)
- Video processing steps (conversion commands, file sizes, S3 operations)
- Camera registry operations
- AWS client creation details
- Camera state database operations

## Security Considerations

### Credential Protection
- All credentials are encrypted using AES encryption
- Encryption keys are stored in AWS Secrets Manager
- Database access is restricted to application user

### Token Security
- OAuth tokens are stored as plain JSON in the database (not encrypted)
- Token expiration is strictly enforced
- Automatic token refresh prevents long-term exposure

### API Security
- All API calls use HTTPS
- User agent is set to identify Watch Tower requests
- No rate limiting implementation (relies on Ring API's built-in limits)

## Integration Points

### AWS Services
- **S3**: Video storage and retrieval
- **Rekognition**: Face recognition processing
- **Secrets Manager**: Encryption key storage

### Database Tables
- **vendors**: Credential and token storage
- **motion_events**: Event tracking and metadata
- **visitor_logs**: Face recognition results

### External APIs
- **Ring API**: Camera control and video access
- **Ring OAuth**: Authentication and token management

## Best Practices

### Development
- Always use the connection manager for API access
- Handle authentication errors gracefully
- Implement proper cleanup in video processing
- Use async/await for all I/O operations

### Deployment
- Store credentials securely in the database
- Monitor authentication token expiration
- Set up proper logging for debugging
- Configure appropriate timeouts for API calls

### Maintenance
- Regularly update Ring API client library
- Monitor for API changes and deprecations
- Review and rotate encryption keys periodically
- Test authentication flows after credential updates