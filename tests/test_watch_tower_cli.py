"""
Tests for Watch Tower CLI functionality.

This module provides comprehensive test coverage for:
- CLI helper functions
- WatchTowerService class
- Configuration validation functions
- CLI command execution
"""

import json
import os
import tempfile
from datetime import datetime, timezone
from typing import Generator, Tuple
from unittest.mock import ANY, MagicMock, Mock, mock_open, patch

import click
import pytest
from click.testing import CliRunner

from cli.services import WatchTowerService
from cli.utils import (
    create_validation_result,
    create_error_status_response,
    handle_cli_error,
    format_confidence_score,
    format_timestamp,
    create_json_entry,
    validate_aws_config,
    validate_database_config,
    validate_ring_config,
    validate_app_config,
)
from cli import cli
from utils.errors import (
    DependencyError,
    ManagementAPIError,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture(name='cli_runner')
def cli_runner_fixture() -> CliRunner:
    """Create a CLI runner for testing."""
    return CliRunner()


@pytest.fixture(name='watch_tower_service')
def watch_tower_service_fixture() -> Generator[Tuple[WatchTowerService, str], None, None]:
    """Create a WatchTowerService with a temporary state file."""
    service = WatchTowerService()
    file_descriptor, temp_state_file_path = tempfile.mkstemp()
    os.close(file_descriptor)
    service.state_file = temp_state_file_path
    yield service, temp_state_file_path
    if os.path.exists(temp_state_file_path):
        os.unlink(temp_state_file_path)


@pytest.fixture(name='mock_visitor_entry')
def mock_visitor_entry_fixture() -> Mock:
    """Create a mock visitor log entry."""
    entry = Mock()
    entry.visitor_log_id = 1
    entry.camera_name = 'Front Door'
    entry.persons_name = 'John Doe'
    entry.confidence_score = 0.95
    entry.visited_at = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    entry.created_at = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    return entry


# =============================================================================
# Helper Functions Tests
# =============================================================================

def test_create_validation_result() -> None:
    """Test create_validation_result function."""
    result = create_validation_result(
        '✅', 'test_field', 'test_value', 'test_message')

    assert result['status'] == '✅'
    assert result['field'] == 'test_field'
    assert result['value'] == 'test_value'
    assert result['message'] == 'test_message'


def test_create_validation_result_no_message() -> None:
    """Test create_validation_result function without message."""
    result = create_validation_result('❌', 'test_field', None)

    assert result['status'] == '❌'
    assert result['field'] == 'test_field'
    assert result['value'] is None
    assert result['message'] == ''


def test_create_error_status_response() -> None:
    """Test create_error_status_response function."""
    error_msg = "Test error message"
    response = create_error_status_response(error_msg)

    assert response['running'] is False
    assert response['start_time'] == 'Unknown'
    assert response['uptime'] == 'Unknown'
    assert response['business_logic_completed'] is True
    assert response['business_logic_cancelled'] is False
    assert response['error'] == error_msg


def test_format_confidence_score_with_value() -> None:
    """Test format_confidence_score with valid score."""
    score = 0.85
    formatted = format_confidence_score(score)
    assert formatted == '85.0%'


def test_format_confidence_score_none() -> None:
    """Test format_confidence_score with None."""
    formatted = format_confidence_score(None)
    assert formatted == 'Unknown'


def test_format_confidence_score_zero() -> None:
    """Test format_confidence_score with zero."""
    formatted = format_confidence_score(0.0)
    assert formatted == '0.0%'


def test_format_timestamp_with_datetime() -> None:
    """Test format_timestamp with valid datetime."""
    timestamp = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    formatted = format_timestamp(timestamp)
    assert '2023-01-01' in formatted
    assert ':' in formatted  # Contains time separator


def test_format_timestamp_none() -> None:
    """Test format_timestamp with None."""
    formatted = format_timestamp(None)
    assert formatted == 'Unknown'


def test_format_timestamp_custom_timezone() -> None:
    """Test format_timestamp with custom timezone."""
    timestamp = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    formatted = format_timestamp(timestamp, 'UTC')
    assert '2023-01-01' in formatted


def test_create_json_entry() -> None:
    """Test create_json_entry function."""
    entry = Mock()
    entry.visitor_log_id = 1
    entry.camera_name = 'Test Camera'
    entry.persons_name = 'John Doe'
    entry.confidence_score = 0.95
    entry.visited_at = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    entry.created_at = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    json_entry = create_json_entry(entry)

    assert json_entry['visitor_log_id'] == 1
    assert json_entry['camera_name'] == 'Test Camera'
    assert json_entry['persons_name'] == 'John Doe'
    assert json_entry['confidence_score'] == 95.0
    assert '2023-01-01T12:00:00' in json_entry['visited_at']
    assert '2023-01-01T12:00:00' in json_entry['created_at']


def test_create_json_entry_with_none_values() -> None:
    """Test create_json_entry with None values."""
    entry = Mock()
    entry.visitor_log_id = 1
    entry.camera_name = None
    entry.persons_name = None
    entry.confidence_score = None
    entry.visited_at = None
    entry.created_at = None

    json_entry = create_json_entry(entry)

    assert json_entry['visitor_log_id'] == 1
    assert json_entry['camera_name'] is None
    assert json_entry['persons_name'] is None
    assert json_entry['confidence_score'] is None
    assert json_entry['visited_at'] is None
    assert json_entry['created_at'] is None


# =============================================================================
# WatchTowerService Tests
# =============================================================================

@patch('cli.services.watch_tower_service.asyncio.run')
def test_get_status_success_with_business_logic(
        mock_asyncio_run: Mock,
        watch_tower_service: Tuple[WatchTowerService, str]) -> None:
    """Test get_status with business_logic data."""
    service, _ = watch_tower_service
    mock_health_data = {
        'business_logic': {
            'running': True,
            'start_time': '2023-01-01T12:00:00Z',
            'uptime': '1h 30m'
        }
    }
    mock_asyncio_run.return_value = mock_health_data

    result = service.get_status()

    assert result['running'] is True
    assert result['start_time'] == '2023-01-01T12:00:00Z'
    assert result['uptime'] == '1h 30m'
    assert result['business_logic_completed'] is False
    assert result['business_logic_cancelled'] is False


@patch('cli.services.watch_tower_service.asyncio.run')
def test_get_status_success_with_event_loop(
        mock_asyncio_run: Mock,
        watch_tower_service: Tuple[WatchTowerService, str]) -> None:
    """Test get_status with event_loop data (backward compatibility)."""
    service, _ = watch_tower_service
    mock_health_data = {
        'event_loop': {
            'running': False,
            'start_time': '2023-01-01T12:00:00Z',
            'uptime': '2h 15m'
        }
    }
    mock_asyncio_run.return_value = mock_health_data

    result = service.get_status()

    assert result['running'] is False
    assert result['start_time'] == '2023-01-01T12:00:00Z'
    assert result['uptime'] == '2h 15m'
    assert result['business_logic_completed'] is True
    assert result['business_logic_cancelled'] is False


@patch('cli.services.watch_tower_service.asyncio.run')
def test_get_status_no_business_logic_data(
        mock_asyncio_run: Mock,
        watch_tower_service: Tuple[WatchTowerService, str]) -> None:
    """Test get_status with no business logic data."""
    service, _ = watch_tower_service
    mock_health_data = {'other_data': 'value'}
    mock_asyncio_run.return_value = mock_health_data

    result = service.get_status()

    assert result['running'] is False
    assert result['error'] == "No business logic status found in health data"


@patch('cli.services.watch_tower_service.asyncio.run')
def test_get_status_dependency_error(
        mock_asyncio_run: Mock,
        watch_tower_service: Tuple[WatchTowerService, str]) -> None:
    """Test get_status with dependency error."""
    service, _ = watch_tower_service
    mock_asyncio_run.side_effect = DependencyError("aiohttp", "pip install aiohttp")

    result = service.get_status()

    assert result['running'] is False
    assert "aiohttp" in result['error']


@patch('cli.services.watch_tower_service.asyncio.run')
def test_get_status_management_api_error(
        mock_asyncio_run: Mock,
        watch_tower_service: Tuple[WatchTowerService, str]) -> None:
    """Test get_status with management API error."""
    service, _ = watch_tower_service
    mock_asyncio_run.side_effect = ManagementAPIError("API error", status_code=500)

    result = service.get_status()

    assert result['running'] is False
    assert "API error" in result['error']


@patch('cli.services.watch_tower_service.asyncio.run')
def test_get_status_general_exception(
        mock_asyncio_run: Mock,
        watch_tower_service: Tuple[WatchTowerService, str]) -> None:
    """Test get_status with general exception."""
    service, _ = watch_tower_service
    mock_asyncio_run.side_effect = Exception("Unexpected error")

    result = service.get_status()

    assert result['running'] is False
    assert "Unexpected error" in result['error']


@patch('cli.services.watch_tower_service.json.dump')
@patch('builtins.open', new_callable=mock_open)
def test_start_business_logic(
        mock_file: Mock,
        mock_json_dump: Mock,
        watch_tower_service: Tuple[WatchTowerService, str]) -> None:
    """Test start_business_logic method."""
    service, temp_state_file_path = watch_tower_service
    service.start_business_logic()

    mock_file.assert_called_once_with(temp_state_file_path, 'w')
    mock_json_dump.assert_called_once()

    call_args = mock_json_dump.call_args[0]
    state_data = call_args[0]
    assert state_data['running'] is True
    assert 'start_time' in state_data
    assert state_data['business_logic_completed'] is False
    assert state_data['business_logic_cancelled'] is False


@patch('cli.services.watch_tower_service.config')
def test_validate_config(
        mock_config: Mock,
        watch_tower_service: Tuple[WatchTowerService, str]) -> None:
    """Test validate_config method."""
    service, _ = watch_tower_service
    service.validate_config()
    mock_config.validate.assert_called_once()


# =============================================================================
# Configuration Validation Tests
# =============================================================================

@patch('cli.utils.validators.config')
def test_validate_aws_config_all_valid(mock_config: Mock) -> None:
    """Test validate_aws_config with all valid values."""
    mock_config.aws_region = 'us-west-2'
    mock_config.aws_access_key_id = 'AKIA1234567890EXAMPLE'
    mock_config.aws_secret_access_key = 'secret_key'

    results = validate_aws_config()

    assert len(results) == 3
    assert all(result['status'] == '✅' for result in results)
    assert results[0]['field'] == 'aws_region'
    assert results[1]['field'] == 'aws_access_key_id'
    assert results[2]['field'] == 'aws_secret_access_key'


@patch('cli.utils.validators.config')
def test_validate_aws_config_missing_values(mock_config: Mock) -> None:
    """Test validate_aws_config with missing values."""
    mock_config.aws_region = None
    mock_config.aws_access_key_id = None
    mock_config.aws_secret_access_key = None

    results = validate_aws_config()

    assert len(results) == 3
    assert all(result['status'] == '❌' for result in results)
    assert all('environment variable' in result['message'] for result in results)


@patch('cli.utils.validators.config')
def test_validate_database_config_all_valid(mock_config: Mock) -> None:
    """Test validate_database_config with all valid values."""
    mock_config.db_secret_name = 'db-secret'
    mock_config.encryption_key_secret_name = 'encryption-key-secret'

    results = validate_database_config()

    assert len(results) == 2
    assert all(result['status'] == '✅' for result in results)
    assert results[0]['field'] == 'db_secret_name'
    assert results[1]['field'] == 'encryption_key_secret_name'


@patch('cli.utils.validators.config')
def test_validate_database_config_missing_values(mock_config: Mock) -> None:
    """Test validate_database_config with missing values."""
    mock_config.db_secret_name = None
    mock_config.encryption_key_secret_name = None

    results = validate_database_config()

    assert len(results) == 2
    assert all(result['status'] == '❌' for result in results)
    assert all('environment variable' in result['message'] for result in results)


def test_validate_ring_config() -> None:
    """Test validate_ring_config function."""
    results = validate_ring_config()

    assert len(results) == 1
    assert results[0]['status'] == '✅'
    assert results[0]['field'] == 'ring_credentials'
    assert 'database_stored' in results[0]['value']


@patch('cli.utils.validators.config')
def test_validate_app_config_all_valid(mock_config: Mock) -> None:
    """Test validate_app_config with all valid values."""
    mock_config.event_recordings_bucket = 'event-recordings-bucket'
    mock_config.rekognition_collection_id = 'rekognition-collection'
    mock_config.rekognition_s3_known_faces_bucket = 'known-faces-bucket'
    mock_config.sns_rekognition_video_analysis_topic_arn = 'sns-topic-arn'
    mock_config.rekognition_video_service_role_arn = 'service-role-arn'
    mock_config.environment = 'production'
    mock_config.debug = False

    results = validate_app_config()

    assert len(results) == 7
    required_fields = [
        'event_recordings_bucket',
        'rekognition_collection_id',
        'rekognition_s3_known_faces_bucket',
        'sns_rekognition_video_analysis_topic_arn',
        'rekognition_video_service_role_arn'
    ]
    for field in required_fields:
        field_result = next(r for r in results if r['field'] == field)
        assert field_result['status'] == '✅'

    info_fields = ['environment', 'debug']
    for field in info_fields:
        field_result = next(r for r in results if r['field'] == field)
        assert field_result['status'] == 'ℹ️'


@patch('cli.utils.validators.config')
def test_validate_app_config_missing_values(mock_config: Mock) -> None:
    """Test validate_app_config with missing values."""
    mock_config.event_recordings_bucket = None
    mock_config.rekognition_collection_id = None
    mock_config.rekognition_s3_known_faces_bucket = None
    mock_config.sns_rekognition_video_analysis_topic_arn = None
    mock_config.rekognition_video_service_role_arn = None
    mock_config.environment = 'development'
    mock_config.debug = True

    results = validate_app_config()

    assert len(results) == 7
    required_fields = [
        'event_recordings_bucket',
        'rekognition_collection_id',
        'rekognition_s3_known_faces_bucket',
        'sns_rekognition_video_analysis_topic_arn',
        'rekognition_video_service_role_arn'
    ]
    for field in required_fields:
        field_result = next(r for r in results if r['field'] == field)
        assert field_result['status'] == '❌'
        assert 'environment variable' in field_result['message']

    info_fields = ['environment', 'debug']
    for field in info_fields:
        field_result = next(r for r in results if r['field'] == field)
        assert field_result['status'] == 'ℹ️'


# =============================================================================
# CLI Error Handling Tests
# =============================================================================

def test_handle_cli_error(caplog: pytest.LogCaptureFixture) -> None:
    """Test handle_cli_error function."""
    ctx = click.Context(click.Command('test'))
    ctx.obj = {'verbose': False}
    error = Exception('Test error')

    with pytest.raises(SystemExit) as exc_info:
        handle_cli_error(error, 'Test error message', ctx)

    assert exc_info.value.code == 1
    assert 'Test error message' in caplog.text


def test_handle_cli_error_verbose(caplog: pytest.LogCaptureFixture) -> None:
    """Test handle_cli_error function with verbose mode."""
    ctx = click.Context(click.Command('test'))
    ctx.obj = {'verbose': True}
    error = Exception('Test error')

    with pytest.raises(SystemExit) as exc_info:
        handle_cli_error(error, 'Test error message', ctx)

    assert exc_info.value.code == 1
    assert 'Test error message' in caplog.text
    assert 'Full traceback:' in caplog.text


# =============================================================================
# CLI Basic Commands Tests
# =============================================================================

def test_cli_help(cli_runner: CliRunner) -> None:
    """Test CLI help command."""
    result = cli_runner.invoke(cli, ['--help'])
    assert result.exit_code == 0
    assert 'Watch Tower - Video Surveillance System CLI' in result.output
    assert 'business-logic' in result.output
    assert 'system' in result.output
    assert 'visitor-log' in result.output


def test_cli_version(cli_runner: CliRunner) -> None:
    """Test CLI version command."""
    result = cli_runner.invoke(cli, ['--version'])
    assert result.exit_code == 0
    assert '3.0.0' in result.output


def test_cli_verbose_flag(cli_runner: CliRunner) -> None:
    """Test CLI verbose flag."""
    result = cli_runner.invoke(cli, ['--verbose', '--help'])
    assert result.exit_code == 0
    assert 'Watch Tower - Video Surveillance System CLI' in result.output


# =============================================================================
# Status Command Tests
# =============================================================================

@patch('cli.commands.status.SERVICE')
def test_status_command_text_format(mock_service: Mock, cli_runner: CliRunner) -> None:
    """Test status command with text format."""
    mock_service.get_status.return_value = {
        'running': True,
        'start_time': '2023-01-01T12:00:00Z',
        'uptime': '1h 30m'
    }

    with patch('cli.commands.status.validate_aws_config') as mock_aws, \
         patch('cli.commands.status.validate_database_config') as mock_db, \
         patch('cli.commands.status.validate_ring_config') as mock_ring, \
         patch('cli.commands.status.validate_app_config') as mock_app:
        mock_aws.return_value = [{'status': '✅', 'field': 'test', 'value': 'ok'}]
        mock_db.return_value = [{'status': '✅', 'field': 'test', 'value': 'ok'}]
        mock_ring.return_value = [{'status': '✅', 'field': 'test', 'value': 'ok'}]
        mock_app.return_value = [{'status': '✅', 'field': 'test', 'value': 'ok'}]

        result = cli_runner.invoke(cli, ['status'])

        assert result.exit_code == 0
        assert '🏰 Watch Tower System Status' in result.output
        assert '🟢 Running' in result.output
        assert '✅ Passed: 4' in result.output
        assert '✅ All systems operational' in result.output


@patch('cli.commands.status.SERVICE')
def test_status_command_json_format(mock_service: Mock, cli_runner: CliRunner) -> None:
    """Test status command with JSON format."""
    mock_service.get_status.return_value = {
        'running': False,
        'start_time': '2023-01-01T12:00:00Z',
        'uptime': '0h 0m'
    }

    with patch('cli.commands.status.validate_aws_config') as mock_aws, \
         patch('cli.commands.status.validate_database_config') as mock_db, \
         patch('cli.commands.status.validate_ring_config') as mock_ring, \
         patch('cli.commands.status.validate_app_config') as mock_app:
        mock_aws.return_value = [
            {'status': '❌', 'field': 'test', 'value': None, 'message': 'error'}]
        mock_db.return_value = [{'status': '✅', 'field': 'test', 'value': 'ok'}]
        mock_ring.return_value = [{'status': '✅', 'field': 'test', 'value': 'ok'}]
        mock_app.return_value = [{'status': '✅', 'field': 'test', 'value': 'ok'}]

        result = cli_runner.invoke(cli, ['status', '--format', 'json'])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert output_data['overall_status'] == '❌ Unhealthy'
        assert output_data['business_logic']['running'] is False
        assert output_data['configuration']['failed'] == 1


@patch('cli.commands.status.SERVICE')
def test_status_command_detailed(mock_service: Mock, cli_runner: CliRunner) -> None:
    """Test status command with detailed output."""
    mock_service.get_status.return_value = {
        'running': True,
        'start_time': '2023-01-01T12:00:00Z',
        'uptime': '1h 30m'
    }

    with patch('cli.commands.status.validate_aws_config') as mock_aws, \
         patch('cli.commands.status.validate_database_config') as mock_db, \
         patch('cli.commands.status.validate_ring_config') as mock_ring, \
         patch('cli.commands.status.validate_app_config') as mock_app:
        mock_aws.return_value = [
            {'status': '✅', 'field': 'aws_region', 'value': 'us-west-2'}]
        mock_db.return_value = [
            {'status': '✅', 'field': 'db_secret_name', 'value': 'db-secret'}]
        mock_ring.return_value = [
            {'status': '✅', 'field': 'ring_credentials', 'value': 'database_stored'}]
        mock_app.return_value = [
            {'status': '✅', 'field': 'environment', 'value': 'production'}]

        result = cli_runner.invoke(cli, ['status', '--detailed'])

        assert result.exit_code == 0
        assert '📋 Configuration Details:' in result.output
        assert 'aws_region' in result.output
        assert 'db_secret_name' in result.output


@patch('cli.commands.status.SERVICE')
def test_status_command_error(mock_service: Mock, cli_runner: CliRunner) -> None:
    """Test status command with service error."""
    mock_service.get_status.return_value = {
        'running': False,
        'error': 'Service unavailable'
    }

    with patch('cli.commands.status.validate_aws_config') as mock_aws, \
         patch('cli.commands.status.validate_database_config') as mock_db, \
         patch('cli.commands.status.validate_ring_config') as mock_ring, \
         patch('cli.commands.status.validate_app_config') as mock_app:
        mock_aws.return_value = []
        mock_db.return_value = []
        mock_ring.return_value = []
        mock_app.return_value = []

        result = cli_runner.invoke(cli, ['status'])

        assert result.exit_code == 0
        assert '🔴 Stopped' in result.output
        assert 'Service unavailable' in result.output


# =============================================================================
# Business Logic Command Tests
# =============================================================================

@patch('cli.commands.business_logic.asyncio.run')
def test_business_logic_start_success(
        mock_asyncio_run: Mock, cli_runner: CliRunner) -> None:
    """Test business logic start command success."""
    mock_asyncio_run.return_value = {'status': 'started'}

    result = cli_runner.invoke(cli, ['business-logic', 'start'])

    assert result.exit_code == 0
    assert '✅ Business logic loop started successfully' in result.output


@patch('cli.commands.business_logic.asyncio.run')
def test_business_logic_start_dependency_error(
        mock_asyncio_run: Mock, cli_runner: CliRunner) -> None:
    """Test business logic start command with dependency error."""
    mock_asyncio_run.side_effect = DependencyError("aiohttp", "pip install aiohttp")

    result = cli_runner.invoke(cli, ['business-logic', 'start'])

    assert result.exit_code == 1
    assert '❌' in result.output
    assert 'aiohttp' in result.output


@patch('cli.commands.business_logic.asyncio.run')
def test_business_logic_start_api_error(
        mock_asyncio_run: Mock, cli_runner: CliRunner) -> None:
    """Test business logic start command with API error."""
    mock_asyncio_run.side_effect = ManagementAPIError("API error", status_code=500)

    result = cli_runner.invoke(cli, ['business-logic', 'start'])

    assert result.exit_code == 1
    assert '❌ Failed to start business logic loop' in result.output


@patch('cli.commands.business_logic.asyncio.run')
def test_business_logic_start_custom_host_port(
        mock_asyncio_run: Mock, cli_runner: CliRunner) -> None:
    """Test business logic start command with custom host and port."""
    mock_asyncio_run.return_value = {'status': 'started'}

    result = cli_runner.invoke(
        cli, ['business-logic', 'start', '--host', '192.168.1.100', '--port', '9000'])

    assert result.exit_code == 0
    assert '✅ Business logic loop started successfully' in result.output


@patch('cli.commands.business_logic.asyncio.run')
def test_business_logic_stop_success(
        mock_asyncio_run: Mock, cli_runner: CliRunner) -> None:
    """Test business logic stop command success."""
    mock_asyncio_run.return_value = {'status': 'stopped'}

    result = cli_runner.invoke(cli, ['business-logic', 'stop'])

    assert result.exit_code == 0
    assert '✅ Business logic loop stopped successfully' in result.output


@patch('cli.commands.business_logic.asyncio.run')
def test_business_logic_stop_api_error(
        mock_asyncio_run: Mock, cli_runner: CliRunner) -> None:
    """Test business logic stop command with API error."""
    mock_asyncio_run.side_effect = ManagementAPIError("API error", status_code=500)

    result = cli_runner.invoke(cli, ['business-logic', 'stop'])

    assert result.exit_code == 1
    assert '❌ Failed to stop business logic loop' in result.output


def test_business_logic_help(cli_runner: CliRunner) -> None:
    """Test business_logic help command."""
    result = cli_runner.invoke(cli, ['business-logic', '--help'])
    assert result.exit_code == 0
    assert 'Manage the business logic loop' in result.output


# =============================================================================
# Visitor Log Command Tests
# =============================================================================

@patch('db.connection.get_database_connection')
@patch('db.repositories.visitor_log_repository.VisitorLogRepository')
def test_visitor_log_recent_text_format(
        mock_repo_class: Mock,
        mock_db_connection: Mock,
        cli_runner: CliRunner,
        mock_visitor_entry: Mock) -> None:
    """Test visitor_log recent command with text format."""
    mock_engine = Mock()
    mock_session_factory = MagicMock()
    mock_db_connection.return_value = (mock_engine, mock_session_factory)

    mock_session = Mock()
    mock_session_factory.__enter__.return_value = mock_session

    mock_repo = Mock()
    mock_repo_class.return_value = mock_repo
    mock_repo.get_recent_entries.return_value = [mock_visitor_entry]

    result = cli_runner.invoke(cli, ['visitor-log', 'recent'])

    assert result.exit_code == 0
    assert '📋 Recent Visitor Log Entries' in result.output
    assert 'John Doe' in result.output
    assert 'Front Door' in result.output
    assert '95.0%' in result.output


@patch('db.connection.get_database_connection')
@patch('db.repositories.visitor_log_repository.VisitorLogRepository')
def test_visitor_log_recent_json_format(
        mock_repo_class: Mock,
        mock_db_connection: Mock,
        cli_runner: CliRunner,
        mock_visitor_entry: Mock) -> None:
    """Test visitor_log recent command with JSON format."""
    mock_engine = Mock()
    mock_session_factory = MagicMock()
    mock_db_connection.return_value = (mock_engine, mock_session_factory)

    mock_session = Mock()
    mock_session_factory.__enter__.return_value = mock_session

    mock_repo = Mock()
    mock_repo_class.return_value = mock_repo
    mock_repo.get_recent_entries.return_value = [mock_visitor_entry]

    result = cli_runner.invoke(cli, ['visitor-log', 'recent', '--format', 'json'])

    assert result.exit_code == 0
    entries = json.loads(result.output)
    assert len(entries) == 1
    assert entries[0]['persons_name'] == 'John Doe'
    assert entries[0]['camera_name'] == 'Front Door'
    assert entries[0]['confidence_score'] == 95.0


@patch('db.connection.get_database_connection')
@patch('db.repositories.visitor_log_repository.VisitorLogRepository')
def test_visitor_log_recent_no_entries(
        mock_repo_class: Mock,
        mock_db_connection: Mock,
        cli_runner: CliRunner) -> None:
    """Test visitor_log recent command with no entries."""
    mock_engine = Mock()
    mock_session_factory = MagicMock()
    mock_db_connection.return_value = (mock_engine, mock_session_factory)

    mock_session = Mock()
    mock_session_factory.__enter__.return_value = mock_session

    mock_repo = Mock()
    mock_repo_class.return_value = mock_repo
    mock_repo.get_recent_entries.return_value = []

    result = cli_runner.invoke(cli, ['visitor-log', 'recent'])

    assert result.exit_code == 0
    assert '📋 No visitor log entries found' in result.output


@patch('db.connection.get_database_connection')
@patch('db.repositories.visitor_log_repository.VisitorLogRepository')
def test_visitor_log_recent_custom_limit(
        mock_repo_class: Mock,
        mock_db_connection: Mock,
        cli_runner: CliRunner) -> None:
    """Test visitor_log recent command with custom limit."""
    mock_engine = Mock()
    mock_session_factory = MagicMock()
    mock_db_connection.return_value = (mock_engine, mock_session_factory)

    mock_session = Mock()
    mock_session_factory.__enter__.return_value = mock_session

    mock_repo = Mock()
    mock_repo_class.return_value = mock_repo
    mock_repo.get_recent_entries.return_value = []

    result = cli_runner.invoke(cli, ['visitor-log', 'recent', '--limit', '5'])

    assert result.exit_code == 0
    mock_repo.get_recent_entries.assert_called_once_with(ANY, limit=5)


def test_visitor_log_help(cli_runner: CliRunner) -> None:
    """Test visitor_log help command."""
    result = cli_runner.invoke(cli, ['visitor-log', '--help'])
    assert result.exit_code == 0
    assert 'Manage and view visitor log entries' in result.output


def test_visitor_log_recent_help(cli_runner: CliRunner) -> None:
    """Test visitor_log recent help command."""
    result = cli_runner.invoke(cli, ['visitor-log', 'recent', '--help'])
    assert result.exit_code == 0
    assert 'Show recent visitor log entries' in result.output
