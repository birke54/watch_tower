# Development Guide

## Setup

### Prerequisites
- Python 3.8+
- PostgreSQL (or AWS RDS)
- AWS Account with appropriate permissions
- Ring account with cameras
- FFmpeg (for video processing)
- Docker and Docker Compose (for containerized development)

### Local Development Setup

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd watch_tower
   ```

2. **Create virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   pip install -e .  # Install the CLI package in development mode
   ```

4. **Set up environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your actual values
   ```

5. **Set up database:**
   ```bash
   # Run the schema file against your PostgreSQL database
   psql -h your-host -U your-user -d your-database -f db/schemas.sql
   ```

6. **Install FFmpeg (required for video processing):**
   ```bash
   # Ubuntu/Debian
   sudo apt-get update && sudo apt-get install -y ffmpeg
   
   # macOS
   brew install ffmpeg
   
   # Windows
   # Download from https://ffmpeg.org/download.html
   ```

## AWS Setup

### Required AWS Services
1. **S3 Buckets**:
   - Create bucket for video recordings (`EVENT_RECORDINGS_BUCKET`)
   - Create bucket for known face images (`REKOGNITION_S3_KNOWN_FACES_BUCKET`)

2. **Rekognition Collection**:
   - Create a face collection (`REKOGNITION_COLLECTION_ID`)
   - Upload known face images to the collection

3. **Secrets Manager**:
   - Create secret for database credentials (`DB_SECRET_NAME`)
   - Create secret for encryption key (`ENCRYPTION_KEY_SECRET_NAME`)

4. **IAM Role** (for Rekognition video analysis):
   - Create IAM role with Rekognition permissions
   - Note the role ARN (`REKOGNITION_VIDEO_SERVICE_ROLE_ARN`)

5. **SNS Topic** (optional, for notifications):
   - Create SNS topic for video analysis notifications
   - Note the topic ARN (`SNS_REKOGNITION_VIDEO_ANALYSIS_TOPIC_ARN`)

### AWS Permissions
Your AWS credentials need:
- S3 read/write access to both buckets
- Rekognition collection management
- Secrets Manager read access
- SNS publish access (if using notifications)

## Database Setup

### PostgreSQL Setup
1. **Create database**:
   ```sql
   CREATE DATABASE watch_tower;
   ```

2. **Run schema**:
   ```bash
   psql -h your-host -U your-user -d watch_tower -f db/schemas.sql
   ```

3. **Add Ring vendor credentials**:
   ```sql
   INSERT INTO vendors (name, username, password_enc, plugin_type, auth_data) 
   VALUES ('Ring Account', 'your_ring_username', 'your_encrypted_password', 'RING', '{}');
   ```

### AWS Secrets Manager Setup
1. **Database credentials secret**:
   ```json
   {
     "host": "your-db-host",
     "port": 5432,
     "dbname": "watch_tower",
     "username": "your-db-user",
     "password": "your-db-password"
   }
   ```

2. **Encryption key secret**:
   ```json
   {
     "key": "your-32-byte-encryption-key"
   }
   ```

## Ring Camera Setup

### Prerequisites
- Ring account with cameras
- Ring cameras connected and working
- Valid Ring credentials

### Setup Steps
1. **Add Ring credentials to database** (see Database Setup above)
2. **Test Ring connection**:
   ```bash
   python -c "
   from watch_tower.core.bootstrap import bootstrap
   import asyncio
   asyncio.run(bootstrap())
   "
   ```

## Running the Application

### Method 1: Direct Python Execution
```bash
# Start the application (includes management API)
python app.py

# In another terminal, use the CLI
watch-tower status
watch-tower business-logic start
watch-tower business-logic stop
```

### Method 2: Docker Development
```bash
# Build and start with Docker Compose
docker compose up -d

# Use CLI inside container
docker compose exec watch-tower watch-tower status
docker compose exec watch-tower watch-tower business-logic start
```

### Method 3: Management Script
```bash
# Make script executable
chmod +x scripts/manage_watch_tower.sh

# Start container
./scripts/manage_watch_tower.sh start-container

# Check logs
./scripts/manage_watch_tower.sh logs

# Open shell
./scripts/manage_watch_tower.sh shell
```

## Environment Variables

### Required Variables
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

### Optional Variables
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

## Testing

### Running Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov

# Run specific test file
pytest tests/test_events_loop.py

# Run tests with verbose output
pytest -v

# Run only unit tests (exclude integration)
pytest -m "not integration"
```

### Test Structure
- **Unit tests**: Test individual functions and classes
- **Integration tests**: Test database and AWS service interactions
- **Async tests**: Use `@pytest.mark.asyncio` for async functions

### Documentation
- Use docstrings for all public functions and classes
- Follow Google docstring format
- Include type hints in docstrings
- Document exceptions that may be raised

## Architecture

### Core Components
1. **Camera Registry**: Manages camera instances and their status
2. **Connection Managers**: Handle authentication and communication with camera vendors
3. **Event Loop**: Processes motion events and coordinates video processing
4. **AWS Services**: S3 for storage, Rekognition for facial recognition
5. **Database Layer**: SQLAlchemy ORM with repository pattern
6. **Management API**: FastAPI-based HTTP API for monitoring and control
7. **CLI Interface**: Command-line tools for system management

### Data Flow
```
Camera → Motion Event → Video Upload → Face Recognition → Visitor Log
```

## Database

### Schema Management
- All schema changes go through `db/schemas.sql`
- Use migrations for production deployments
- Test schema changes in development first

### Repository Pattern
- Each table has a corresponding repository class
- Repositories inherit from `BaseRepository`
- Use dependency injection for database sessions

## Troubleshooting

### Common Issues
1. **Database connection errors**: Check `DB_SECRET_NAME` and AWS credentials
2. **Ring authentication failures**: Verify Ring credentials in database
3. **S3 upload failures**: Check bucket permissions and `EVENT_RECORDINGS_BUCKET`
4. **Face recognition errors**: Verify Rekognition collection exists
5. **FFmpeg not found**: Install FFmpeg system dependency
6. **Import errors**: Ensure you've run `pip install -e .`
7. **Management API not accessible**: Check `MANAGEMENT_API_HOST` and `MANAGEMENT_API_PORT`

### Logging
- Set `LOG_LEVEL=DEBUG` for detailed logging
- Check application logs for error details
- Use structured logging for better debugging

### Debug Mode
```bash
# Enable verbose CLI output
watch-tower --verbose status

# Check management API health
curl http://localhost:8080/health

# View application logs
docker compose logs -f watch-tower
```

## Contributing

### Pull Request Process
1. Create a feature branch from `main`
2. Make your changes with tests
3. Ensure all tests pass
4. Update documentation if needed
5. Submit a pull request

### Code Review Checklist
- [ ] Tests pass
- [ ] Code follows style guidelines
- [ ] Documentation is updated
- [ ] No security issues introduced
- [ ] Performance impact considered

## Security

### Best Practices
- Never commit credentials to version control
- Use AWS Secrets Manager for sensitive data
- Encrypt passwords before storing in database
- Validate all input data
- Use least privilege principle for AWS permissions