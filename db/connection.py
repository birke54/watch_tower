from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from aws.secrets_manager.secrets_manager_service import get_db_secret
from db.exceptions import DatabaseConnectionError
from functools import lru_cache
from watch_tower.config import config
from utils.logging_config import get_logger

logger = get_logger(__name__)

# Module-level variables for database connection
engine = None
SessionLocal = None


@lru_cache()
def get_engine():
    """
    Get or create the database engine.
    Uses caching to ensure only one engine is created.

    Returns:
        Engine: SQLAlchemy engine

    Raises:
        DatabaseConnectionError: If there are issues creating the database connection
    """
    try:
        # Validate only database configuration
        config.validate_database_only()

        # Get database configuration from secret
        secret = get_db_secret(config.db_secret_name)

        # Create database URL
        database_url = (
            f"postgresql://{secret['username']}:{secret['password']}@"
            f"{secret['host']}:{secret['port']}/{secret['dbname']}"
        )

        # Create engine with connection pooling and pre-ping
        return create_engine(
            database_url,
            pool_pre_ping=True,
            pool_size=config.database.pool_size,
            max_overflow=config.database.max_overflow,
            pool_recycle=config.database.pool_recycle,
            pool_timeout=config.database.pool_timeout,
            connect_args={'connect_timeout': config.database.connect_timeout}
        )

    except Exception as e:
        raise DatabaseConnectionError(f"Failed to create database engine: {str(e)}")


def get_session_factory():
    """
    Get or create the session factory.

    Returns:
        sessionmaker: SQLAlchemy session factory

    Raises:
        DatabaseConnectionError: If there are issues creating the session factory
    """
    try:
        engine = get_engine()
        return sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=engine
        )
    except Exception as e:
        raise DatabaseConnectionError(f"Failed to create session factory: {str(e)}")


def get_database_connection():
    """
    Get both the engine and session factory.
    This is a convenience function that returns both objects.

    Returns:
        tuple: (engine, session_factory) SQLAlchemy engine and session factory

    Raises:
        DatabaseConnectionError: If there are issues creating the database connection
    """
    try:
        engine = get_engine()
        session_factory = get_session_factory()
        return engine, session_factory
    except Exception as e:
        raise DatabaseConnectionError(f"Failed to create database connection: {str(e)}")
