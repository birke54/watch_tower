import os
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import text
from typing import Generator, Dict, Tuple
from db.connection import get_engine, get_session_factory, get_database_connection
from db.exceptions import DatabaseConnectionError
from aws.exceptions import SecretsManagerError

# Sample secret data for testing
MOCK_SECRET: Dict[str, str] = {
    "username": "test_user",
    "password": "test_pass",
    "host": "test_host",
    "port": "5432",
    "dbname": "test_db"
}


@pytest.fixture
def mock_env_vars() -> Generator[None, None, None]:
    """Fixture to set up test environment variables"""
    with patch.dict(os.environ, {
        'DB_SECRET_NAME': 'test-secret'
    }):
        yield


@pytest.fixture
def mock_secrets_manager() -> Generator[MagicMock, None, None]:
    """Fixture to mock AWS Secrets Manager service"""
    with patch('db.connection.get_db_secret') as mock_get_secret:
        mock_get_secret.return_value = MOCK_SECRET
        yield mock_get_secret


@pytest.fixture
def mock_db_connection(
        mock_secrets_manager: MagicMock) -> Generator[Tuple[MagicMock, MagicMock], None, None]:
    """Fixture to mock database connection"""
    with patch('db.connection.create_engine') as mock_create_engine, \
            patch('db.connection.sessionmaker') as mock_sessionmaker:

        # Set up mock engine
        mock_engine = MagicMock()
        mock_url = MagicMock()
        mock_url.__str__ = MagicMock(
            return_value=f"postgresql://{MOCK_SECRET['username']}:{MOCK_SECRET['password']}@{MOCK_SECRET['host']}:{MOCK_SECRET['port']}/{MOCK_SECRET['dbname']}")
        mock_engine.url = mock_url
        mock_engine.pool._pre_ping = True
        mock_create_engine.return_value = mock_engine

        # Set up mock session with proper structure
        mock_session = MagicMock()
        mock_session.is_active = True

        # Set up session maker with proper configuration
        mock_maker = MagicMock()
        mock_maker.kw = {'autocommit': False, 'autoflush': False}
        mock_session._maker = mock_maker

        # Set up query result
        mock_result = MagicMock()
        mock_result.scalar.return_value = 1
        mock_session.execute.return_value = mock_result

        # Set up sessionmaker to return our configured session
        mock_sessionmaker.return_value = lambda: mock_session

        yield mock_create_engine, mock_session


def test_get_engine(mock_env_vars: None, mock_secrets_manager: MagicMock,
                    mock_db_connection: Tuple[MagicMock, MagicMock]) -> None:
    get_engine.cache_clear()
    """Test that the engine can be created with correct configuration"""
    mock_create_engine, _ = mock_db_connection
    engine = get_engine()

    # Verify the engine was created with correct URL
    assert str(
        engine.url) == f"postgresql://{MOCK_SECRET['username']}:{MOCK_SECRET['password']}@{MOCK_SECRET['host']}:{MOCK_SECRET['port']}/{MOCK_SECRET['dbname']}"

    # Verify the engine has the expected configuration
    assert engine.pool._pre_ping is True

    # Verify create_engine was called with correct arguments
    mock_create_engine.assert_called_once()
    call_args = mock_create_engine.call_args[1]
    assert call_args['pool_pre_ping'] is True
    assert call_args['connect_args'] == {'connect_timeout': 5}


def test_get_session_factory(mock_db_connection: Tuple[MagicMock, MagicMock]) -> None:
    get_engine.cache_clear()
    """Test that the session factory can be created with correct configuration"""
    session_factory = get_session_factory()

    # Create a session and verify its configuration
    session = session_factory()
    assert session.is_active
    assert session._maker.kw['autocommit'] is False
    assert session._maker.kw['autoflush'] is False


def test_engine_caching(mock_db_connection: Tuple[MagicMock, MagicMock]) -> None:
    get_engine.cache_clear()
    """Test that the engine is cached and reused"""
    engine1 = get_engine()
    engine2 = get_engine()

    # Verify both calls return the same engine instance
    assert engine1 is engine2


def test_get_database_connection(
        mock_db_connection: Tuple[MagicMock, MagicMock]) -> None:
    get_engine.cache_clear()
    """Test that get_database_connection returns both engine and session factory"""
    engine, session_factory = get_database_connection()

    # Verify engine
    assert str(
        engine.url) == f"postgresql://{MOCK_SECRET['username']}:{MOCK_SECRET['password']}@{MOCK_SECRET['host']}:{MOCK_SECRET['port']}/{MOCK_SECRET['dbname']}"

    # Verify session factory
    session = session_factory()
    assert session.is_active
    assert session._maker.kw['autocommit'] is False
    assert session._maker.kw['autoflush'] is False


def test_get_engine_secret_error(mock_env_vars: None) -> None:
    """Test that get_engine raises DatabaseConnectionError when secret retrieval fails"""
    # Clear the engine cache before testing
    get_engine.cache_clear()

    with patch('db.connection.get_db_secret', side_effect=SecretsManagerError("Secret error")):
        with pytest.raises(DatabaseConnectionError) as exc_info:
            get_engine()
        assert "Failed to create database engine" in str(exc_info.value)
        assert "Secret error" in str(exc_info.value)


def test_get_session_factory_engine_error(mock_env_vars: None) -> None:
    """Test that get_session_factory raises DatabaseConnectionError when engine creation fails"""
    # Clear the engine cache before testing
    get_engine.cache_clear()

    with patch('db.connection.get_engine', side_effect=Exception("Engine error")):
        with pytest.raises(DatabaseConnectionError) as exc_info:
            get_session_factory()
        assert "Failed to create session factory" in str(exc_info.value)
        assert "Engine error" in str(exc_info.value)


@pytest.mark.integration
def test_actual_connection(mock_db_connection: Tuple[MagicMock, MagicMock]) -> None:
    """Integration test to verify actual database connection
    This test will only run if explicitly marked with -m integration
    """
    get_engine.cache_clear()
    engine, session_factory = get_database_connection()
    session = session_factory()

    try:
        # Try to execute a simple query
        result = session.execute(text("SELECT 1"))
        assert result.scalar() == 1
    finally:
        session.close()
