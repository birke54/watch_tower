# CLI and Event Loop Management

This document describes the Watch Tower Command Line Interface (CLI) system and how to manage the business logic loop, which is responsible for processing camera events, video analysis, and system monitoring.

## Overview

The Watch Tower system provides a comprehensive interface for managing the video surveillance system through two primary control mechanisms:

1. **HTTP API Control** - Primary method for immediate start/stop operations
2. **State File Control** - Secondary method for persistence and auto-restart

## Architecture Components

### 1. Main CLI Application (`cli/main.py`)

The main CLI application provides the user interface and command structure:

```python
@click.group()
@click.version_option(version="3.0.0")
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
@click.pass_context
def cli(ctx, verbose):
    """Watch Tower - Video Surveillance System CLI"""
```

### 2. Service Layer (`WatchTowerService`)

The service layer handles the business logic for CLI operations:

```python
class WatchTowerService:
    """Service layer for Watch Tower CLI operations."""
    
    def __init__(self):
        self.state_file = config.cli.state_file_path
    
    async def start_business_logic_api(self, host: str = "localhost", port: int = 8080) -> Dict[str, Any]:
        """Start the business logic loop via HTTP API."""
    
    async def stop_business_logic_api(self, host: str = "localhost", port: int = 8080) -> Dict[str, Any]:
        """Stop the business logic loop via HTTP API."""
    
    def start_business_logic(self) -> None:
        """Start the business logic loop by updating the state file."""
```

### 3. Control Mechanisms

#### HTTP API Control (Primary)

The CLI uses HTTP API calls for immediate control:

```python
async def start_business_logic_api(self, host: str = "localhost", port: int = 8080) -> Dict[str, Any]:
    url = f"http://{host}:{port}/start"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, timeout=10) as response:
            if response.status == 200:
                return await response.json()
```

**Advantages:**
- Immediate response
- Standard REST API
- Works across containers
- Real-time status information

#### State File Control (Persistence)

The CLI can also control via state file for persistence:

```python
def start_business_logic(self) -> None:
    """Start the business logic loop by updating the state file."""
    state = {
        "running": True,
        "start_time": datetime.now(timezone.utc).isoformat(),
        "business_logic_completed": False,
        "business_logic_cancelled": False,
        "last_updated": datetime.now(timezone.utc).isoformat()
    }
    
    with open(self.state_file, "w") as f:
        json.dump(state, f)
```

**Advantages:**
- Persistence across restarts
- Automatic restart detection
- External monitoring capability
- Container orchestration friendly

## Command Structure

### Command Groups

The CLI is organized into logical command groups:

```python
@cli.group()
def business_logic():
    """Manage the business logic loop."""
    pass

@cli.group()
def visitor_log():
    """Manage and view visitor log entries."""
    pass
```

### Available Commands

#### System Status
- `status` - Show comprehensive system status (overall health, business logic, configuration)
  - `--format [text|json]` - Output format
  - `--detailed` - Show detailed status information

#### Business Logic Management
- `business-logic start` - Start the business logic loop via HTTP API
- `business-logic stop` - Stop the business logic loop via HTTP API

#### Visitor Log Management
- `visitor-log recent` - Show recent visitor log entries with pagination and formatting options

## Quick Start

### Infrastructure Operations (Management Script)

```bash
# Start the application container
./scripts/manage_watch_tower.sh start-container

# View container logs
./scripts/manage_watch_tower.sh logs

# Open shell in container
./scripts/manage_watch_tower.sh shell

# Stop the application container
./scripts/manage_watch_tower.sh stop-container

# Restart the application container
./scripts/manage_watch_tower.sh restart-container
```

### Application Operations (Main CLI)

```bash
# Check comprehensive system status
docker compose exec watch-tower watch-tower status

# Start the business logic loop
docker compose exec watch-tower watch-tower business-logic start

# Stop the business logic loop
docker compose exec watch-tower watch-tower business-logic stop

# View recent visitor log entries
docker compose exec watch-tower watch-tower visitor-log recent

# Enable verbose output
docker compose exec watch-tower watch-tower --verbose status
```

### Direct CLI Usage

```bash
# Check comprehensive system status
watch-tower status

# Start the business logic loop
watch-tower business-logic start

# Stop the business logic loop
watch-tower business-logic stop

# Restart the business logic loop
watch-tower business-logic stop && watch-tower business-logic start
```

## Understanding the Business Logic Loop

The Watch Tower business logic loop is responsible for:
- Polling cameras for motion events
- Processing video uploads to S3
- Running facial recognition tasks
- Managing visitor logs

The business logic loop runs independently of the bootstrap process, allowing you to stop and restart it without affecting the system setup.

## Control Methods

### Method 1: HTTP API (Primary Control)

The HTTP API provides immediate control over the business logic loop:

```bash
# Start via HTTP API
curl -X POST http://localhost:8080/start

# Stop via HTTP API
curl -X POST http://localhost:8080/stop

# Check health and status
curl http://localhost:8080/health
```

**Advantages:**
- Immediate response
- Standard REST API
- Works across containers
- Real-time status information

### Method 2: State File (Persistence & Auto-Restart)

The state file enables persistence and automatic restart:

```bash
# Programmatic start via state file
echo '{"running": true, "start_time": "2024-01-01T12:00:00+00:00"}' > /tmp/watch_tower_business_logic_state.json

# Monitor state file
cat /tmp/watch_tower_business_logic_state.json
```

**Advantages:**
- Persistence across restarts
- Automatic restart detection
- External monitoring capability
- Container orchestration friendly

## What Happens During Operations

### Starting the Business Logic Loop

When you start the business logic loop, the following occurs:

1. **HTTP Request**: CLI sends POST request to `/start` endpoint
2. **Initialization**: Business logic components are initialized
3. **State File Update**: The state file is updated to reflect running status
4. **Loop Start**: The main business logic loop begins execution
5. **Monitoring**: Health checks and status monitoring begin

### Stopping the Business Logic Loop

When you stop the business logic loop gracefully, the following occurs:

1. **HTTP Request**: CLI sends POST request to `/stop` endpoint
2. **Shutdown Signal**: The `shutdown_event` is set to notify the business logic loop
3. **Current Iteration Completion**: The current iteration completes its work
4. **Cleanup**: Resources are cleaned up and state is updated
5. **State File Update**: The state file is updated to reflect stopped status

## Monitoring and Health Checks

### Real-time Status
```bash
# Check comprehensive status
watch-tower status

# Check with detailed information
watch-tower status --detailed

# Check in JSON format
watch-tower status --format json
```

### API Health Check
```bash
# Direct API health check
curl http://localhost:8080/health

# Check with jq for formatted output
curl -s http://localhost:8080/health | jq .
```

### State File Monitoring
```bash
# Monitor state file
watch -n 2 cat /tmp/watch_tower_business_logic_state.json

# Check state file with jq
cat /tmp/watch_tower_business_logic_state.json | jq .
```

## Command Mapping

| Management Script | Main CLI | Purpose |
|------------------|----------|---------|
| `start-container` | N/A | Start Docker container |
| `stop-container` | N/A | Stop Docker container |
| `restart-container` | N/A | Restart Docker container |
| `build` | N/A | Build Docker container |
| `logs` | N/A | View container logs |
| `shell` | N/A | Open shell in container |
| N/A | `status` | Show comprehensive system status |
| N/A | `business-logic start` | Start application business logic loop |
| N/A | `business-logic stop` | Stop application business logic loop |
| N/A | `visitor-log recent` | View recent visitor log entries |

## When to Use Each Interface

### Use Management Script When:
- **Managing Docker containers** (start/stop/restart/build)
- **Working from host machine** (outside container)
- **Infrastructure operations** (logs, shell access)
- **Development workflow** (frequent container restarts)
- **System administration** (infrastructure management)

### Use Main CLI When:
- **Business logic loop management** (start/stop/status)
- **Detailed monitoring** (real-time status, camera status)
- **Visitor log management** (viewing recent entries)
- **Application-level operations** (within container)

## Troubleshooting

### Common Issues

#### Business Logic Won't Start
```bash
# Check if management API is running
curl http://localhost:8080/health

# Check container logs
docker-compose logs watch-tower --tail=100

# Check state file
cat /tmp/watch_tower_business_logic_state.json
```

#### Business Logic Won't Stop
```bash
# Force stop via state file
echo '{"running": false}' > /tmp/watch_tower_business_logic_state.json

# Check if process is still running
docker-compose exec watch-tower ps aux | grep python
```

#### Status Shows Inconsistent Information
```bash
# Get detailed status
watch-tower status --detailed

# Check API health
curl http://localhost:8080/health

# Check state file
cat /tmp/watch_tower_business_logic_state.json
```

### Debug Mode
```bash
# Enable verbose logging
watch-tower --verbose status

# View debug logs
docker-compose logs watch-tower --tail=100
```

## Best Practices

### Starting the System
1. **Start Container**: Use management script to start the container
2. **Check Status**: Verify system is ready with `watch-tower status`
3. **Start Business Logic**: Use `watch-tower business-logic start`
4. **Monitor**: Use `watch-tower status` to monitor operation

### Stopping the System
1. **Stop Business Logic**: Use `watch-tower business-logic stop`
2. **Verify Stop**: Check status to confirm business logic has stopped
3. **Stop Container**: Use management script to stop container if needed

### Monitoring
- Use `watch-tower status` regularly to check system health
- Monitor logs for errors and warnings
- Use the management API for programmatic monitoring
- Set up external monitoring for the state file

## Testing

### Unit Testing
```python
def test_start_business_logic_api():
    service = WatchTowerService()
    result = asyncio.run(service.start_business_logic_api())
    assert 'error' not in result
```

### Integration Testing
```bash
# Test CLI commands
docker compose exec watch-tower watch-tower status
docker compose exec watch-tower watch-tower business-logic start
docker compose exec watch-tower watch-tower business-logic stop
```

### End-to-End Testing
```bash
# Full workflow test
./scripts/manage_watch_tower.sh start-container
docker compose exec watch-tower watch-tower business-logic start
docker compose exec watch-tower watch-tower status
docker compose exec watch-tower watch-tower business-logic stop
./scripts/manage_watch_tower.sh stop-container
```

## Security Considerations

### Container Isolation
- CLI runs inside Docker container
- Limited access to host system
- Isolated network namespace

### API Security
- Management API runs on localhost by default
- No authentication required for local access
- Can be secured with reverse proxy for external access

### State File Security
- State file stored in `/tmp` directory
- File permissions controlled by container
- No sensitive data in state file

## Performance Considerations

### HTTP API Performance
- Fast response times (< 100ms)
- Connection pooling with aiohttp
- Timeout handling (10 seconds)

### State File Performance
- Minimal I/O overhead
- 2-second polling interval
- JSON serialization/deserialization

### Memory Usage
- Lightweight CLI application
- No persistent memory usage
- Clean shutdown and cleanup 