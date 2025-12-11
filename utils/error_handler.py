"""
Centralized error handling utilities for Watch Tower.

This module provides decorators and utilities for consistent error handling
across the application.
"""

import functools
import logging
from typing import Any, Callable, Optional, Type, Union, Tuple
from contextlib import contextmanager

from utils.logging_config import get_logger

logger = get_logger(__name__)  # pylint: disable=invalid-name


def handle_errors(
        error_types: Optional[Union[Type[Exception], Tuple[Type[Exception], ...]]] = None,
        default_return: Any = None,
        log_error: bool = True,
        reraise: bool = True
) -> Callable:
    """
    Decorator for consistent error handling.

    Args:
        error_types: Exception types to catch (default: all exceptions)
        default_return: Value to return on error
        log_error: Whether to log the error
        reraise: Whether to re-raise the exception after handling

    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if error_types is None or isinstance(e, error_types):
                    if log_error:
                        logger.error(
                            "Error in %s: %s",
                            func.__name__,
                            str(e),
                            exc_info=True
                        )

                    if reraise:
                        raise
                    return default_return
                # Re-raise if it's not the type we're handling
                raise
        return wrapper
    return decorator


def handle_async_errors(
        error_types: Optional[Union[Type[Exception], Tuple[Type[Exception], ...]]] = None,
        default_return: Any = None,
        log_error: bool = True,
        reraise: bool = True
) -> Callable:
    """
    Decorator for consistent async error handling.

    Args:
        error_types: Exception types to catch (default: all exceptions)
        default_return: Value to return on error
        log_error: Whether to log the error
        reraise: Whether to re-raise the exception after handling

    Returns:
        Decorated async function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if error_types is None or isinstance(e, error_types):
                    if log_error:
                        logger.error(
                            "Error in async %s: %s",
                            func.__name__,
                            str(e),
                            exc_info=True
                        )

                    if reraise:
                        raise
                    return default_return
                # Re-raise if it's not the type we're handling
                raise
        return wrapper
    return decorator


@contextmanager
def error_context(
        operation: str,
        error_types: Optional[Union[Type[Exception], Tuple[Type[Exception], ...]]] = None,
        log_error: bool = True,
        reraise: bool = True
):
    """
    Context manager for error handling.

    Args:
        operation: Description of the operation being performed
        error_types: Exception types to catch (default: all exceptions)
        log_error: Whether to log the error
        reraise: Whether to re-raise the exception after handling

    Yields:
        None
    """
    try:
        yield
    except Exception as e:
        if error_types is None or isinstance(e, error_types):
            if log_error:
                logger.error(
                    "Error during %s: %s",
                    operation,
                    str(e),
                    exc_info=True
                )

            if reraise:
                raise
        # Re-raise if it's not the type we're handling
        raise


def log_and_raise(
        error: Exception,
        message: str,
        logger_instance: Optional[logging.Logger] = None
) -> None:
    """
    Log an error and re-raise it with additional context.

    Args:
        error: The exception to log and re-raise
        message: Additional context message
        logger_instance: Optional logger instance (uses module logger if None)
    """
    log = logger_instance or logger
    log.error("%s: %s", message, str(error), exc_info=True)
    raise error


def safe_execute(
        func: Callable,
        *args: Any,
        error_message: str = "Function execution failed",
        default_return: Any = None,
        **kwargs: Any
) -> Any:
    """
    Safely execute a function with error handling.

    Args:
        func: Function to execute
        *args: Positional arguments for the function
        error_message: Message to log on error
        default_return: Value to return on error
        **kwargs: Keyword arguments for the function

    Returns:
        Function result or default_return on error
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.error("%s: %s", error_message, str(e), exc_info=True)
        return default_return


async def safe_execute_async(
        func: Callable,
        *args: Any,
        error_message: str = "Async function execution failed",
        default_return: Any = None,
        **kwargs: Any
) -> Any:
    """
    Safely execute an async function with error handling.

    Args:
        func: Async function to execute
        *args: Positional arguments for the function
        error_message: Message to log on error
        default_return: Value to return on error
        **kwargs: Keyword arguments for the function

    Returns:
        Function result or default_return on error
    """
    try:
        return await func(*args, **kwargs)
    except Exception as e:
        logger.error("%s: %s", error_message, str(e), exc_info=True)
        return default_return
