# Watch Tower

A video surveillance system with facial recognition capabilities, featuring centralized configuration management, comprehensive logging, and a powerful CLI for system management.

## Prerequisites

Before getting started, ensure you have:

- **Docker and Docker Compose** - For containerized deployment
- **AWS Account** - With appropriate permissions for S3, Rekognition, and Secrets Manager
- **Ring Account** - With cameras for video surveillance
- **PostgreSQL Database** - For storing events and metadata (or AWS RDS)
- **FFmpeg** - For video processing (included in Docker image)

## Quick Start

### 1. Setup

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd watch_tower
   ```

2. **Configure environment variables:**
   ```bash
   # Create .env file with your configuration
   # See Environment Variables section below for required variables
   ```

3. **Set up AWS resources:**
   - Create S3 buckets for video recordings and known faces
   - Set up Rekognition collection
   - Configure Secrets Manager for database credentials
   - Create IAM roles and SNS topics

4. **Set up database:**
   - Create PostgreSQL database
   - Run schema: `psql -h your-host -U your-user -d your-database -f db/schemas.sql`
   - Add Ring credentials to vendors table

### 2. Using Docker Compose

```bash
# Start the application
docker compose up -d

# Check status
docker compose exec watch-tower watch-tower status

# Start business logic loop
docker compose exec watch-tower watch-tower business-logic start

# Stop business logic loop
docker compose exec watch-tower watch-tower business-logic stop

# View logs
docker compose logs -f watch-tower

# Stop the application
docker compose down
```

### Using the Management Script

```bash
# Start the application
./scripts/manage_watch_tower.sh start-container

# Check container logs
./scripts/manage_watch_tower.sh logs

# Stop the application
./scripts/manage_watch_tower.sh stop-container

# Restart the application
./scripts/manage_watch_tower.sh restart-container

# Build the container
./scripts/manage_watch_tower.sh build

# Open shell in container
./scripts/manage_watch_tower.sh shell
```

### Using the CLI Directly

```bash
# Check comprehensive system status
watch-tower status

# Start business logic loop
watch-tower business-logic start

# Stop business logic loop
watch-tower business-logic stop

# View recent visitor log entries
watch-tower visitor-log recent

# Verbose output
watch-tower --verbose status
```

## CLI Commands

### System Status
- `status` - Show comprehensive system status (overall health, business logic, configuration)
  - `--format [text|json]` - Output format
  - `--detailed` - Show detailed status information

### Business Logic Management
- `business-logic start` - Start the business logic loop via HTTP API
- `business-logic stop` - Stop the business logic loop via HTTP API

### Visitor Log Management
- `visitor-log recent` - Show recent visitor log entries with pagination

## Features

- **Ring Camera Integration**: Monitors Ring cameras for motion events
- **AWS Rekognition**: Intelligent face recognition and analysis
- **Video Processing**: Automatic video conversion and optimization
- **Database Storage**: Secure storage of events and metadata
- **Management API**: HTTP API for monitoring and control
- **CLI Interface**: Command-line tools for system management
- **Docker Support**: Containerized deployment
- **Health Monitoring**: Comprehensive system health checks

## Architecture

Watch Tower follows a modular architecture with clear separation of concerns:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Ring Camera   │───▶│  Motion Events  │───▶│  Video Upload   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                       │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Face Search    │◀───│  AWS Rekognition│◀───│  S3 Storage     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │
┌─────────────────┐    ┌─────────────────┐
│  Visitor Logs   │───▶│  PostgreSQL DB  │
└─────────────────┘    └─────────────────┘
```

**Key Components:**
- **Camera Registry**: Manages camera instances and their status
- **Connection Managers**: Handle authentication and API communication
- **Event Loop**: Processes motion events and coordinates video processing
- **AWS Services**: S3 for storage, Rekognition for facial recognition
- **Database Layer**: SQLAlchemy ORM with repository pattern
- **Management API**: FastAPI-based HTTP API for monitoring and control

## Management API

Watch Tower includes a real-time management API server that provides live system status information. The API runs on port 8080 and can be accessed from outside the container.

### Accessing the Management API

```bash
# From outside the container
curl http://localhost:8080/health

# From inside the container
curl http://localhost:8080/health
```

### Management API Features

- **System Health**: Overall system status and component health
- **Business Logic Loop Status**: Real-time status of the business logic loop
- **Camera Monitoring**: Live camera status and health information
- **Database Connectivity**: Database connection status
- **AWS Services**: AWS service connectivity status

## Environment Variables

The application uses a centralized configuration system that loads from environment variables. Copy `.env.example` to `.env` and fill in your actual values:

```bash
cp .env.example .env
```

**Required Variables:**
```bash
# AWS Configuration
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key

# Database Configuration
DB_SECRET_NAME=your_db_secret_name
ENCRYPTION_KEY_SECRET_NAME=your_encryption_key_secret_name

# S3 Configuration
EVENT_RECORDINGS_BUCKET=your_event_recordings_bucket
REKOGNITION_S3_KNOWN_FACES_BUCKET=your_known_faces_bucket

# Rekognition Configuration
REKOGNITION_COLLECTION_ID=your_collection_id
SNS_REKOGNITION_VIDEO_ANALYSIS_TOPIC_ARN=your_sns_topic_arn
REKOGNITION_VIDEO_SERVICE_ROLE_ARN=your_service_role_arn
```

**Optional Variables:**
```bash
# Logging
LOG_LEVEL=INFO
LOG_FILE=/app/logs/watch_tower.log

# Management API
MANAGEMENT_API_HOST=0.0.0.0
MANAGEMENT_API_PORT=8080
MANAGEMENT_API_LOG_LEVEL=info
MANAGEMENT_API_ACCESS_LOG=false

# Performance Tuning
max_concurrent_uploads=2
max_concurrent_face_recognition=2
```

**Note:** Connection manager credentials are stored securely in the database vendors table and are not configured via environment variables.

## Configuration System

Watch Tower uses a centralized configuration system (`config.py`) that:
- Loads environment variables automatically
- Provides type-safe configuration access
- Validates required settings
- Supports different environments (dev/staging/prod)
- Centralizes all application settings

## Logging

The application features comprehensive logging:
- **Console output**: All logs appear in the terminal
- **File logging**: Optional file-based logging (configure via `LOG_FILE`)
- **Log rotation**: Automatic log file rotation (10MB max, 5 backup files)
- **Structured format**: Consistent log format across all modules
- **Performance monitoring**: Built-in performance tracking

## Testing

To run all tests:

```bash
pytest
```

To run with coverage:

```bash
pytest --cov
```

To run specific test categories:

```bash
pytest -m "not integration"  # Skip integration tests
pytest tests/aws/            # Run only AWS tests
```

## Troubleshooting

### Common Issues

**Database Connection Errors:**
- Verify `DB_SECRET_NAME` and AWS credentials
- Check PostgreSQL database is running and accessible
- Ensure database schema has been applied

**Ring Authentication Failures:**
- Verify Ring credentials in database vendors table
- Check Ring account has valid cameras
- Ensure 2FA is properly configured if enabled

**S3 Upload Failures:**
- Check bucket permissions and `EVENT_RECORDINGS_BUCKET` configuration
- Verify AWS credentials have S3 write access
- Ensure bucket exists in the specified region

**Face Recognition Errors:**
- Verify Rekognition collection exists and is accessible
- Check `REKOGNITION_COLLECTION_ID` configuration
- Ensure known faces have been indexed in the collection

**Management API Not Accessible:**
- Check `MANAGEMENT_API_HOST` and `MANAGEMENT_API_PORT` settings
- Verify container is running: `docker compose ps`
- Check logs: `docker compose logs watch-tower`

### Debug Mode

Enable verbose logging for troubleshooting:

```bash
# Set debug log level
export LOG_LEVEL=DEBUG

# Use verbose CLI output
watch-tower --verbose status

# Check management API health
curl http://localhost:8080/health

# View application logs
docker compose logs -f watch-tower
```

## Documentation

For detailed information about specific components:

- **[Development Guide](docs/development.md)** - Complete setup and development instructions
- **[Ring Integration](docs/ring_documentation.md)** - Ring camera integration details
- **[Visitor Log Implementation](docs/visitor_log_implementation.md)** - Face recognition and visitor logging
- **[CLI and Event Loop Management](docs/cli_and_event_loop_management.md)** - System management details
- **[Database Schema](db/database_schema.md)** - Database structure and relationships