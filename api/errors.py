"""
API Error Handlers

Error handling utilities for the management API.
"""

import logging
from typing import NoReturn

from fastapi import HTTPException

from watch_tower.exceptions import BusinessLogicError, ConfigurationError

logger = logging.getLogger(__name__)


def handle_business_logic_operation_error(operation: str, error: Exception) -> NoReturn:
    """Handle errors from business logic operations.
    
    Args:
        operation: The operation being performed (e.g., "start", "stop")
        error: The exception that occurred
        
    Raises:
        HTTPException: Always raises an HTTPException with appropriate status code
    """
    if isinstance(error, BusinessLogicError):
        logger.error(f"Business logic error during {operation}: {error}")
        raise HTTPException(
            status_code=400,
            detail=f"Business logic error: {str(error)}"
        )
    elif isinstance(error, ConfigurationError):
        logger.error(f"Configuration error during {operation}: {error}")
        raise HTTPException(
            status_code=500,
            detail=f"Configuration error: {str(error)}"
        )
    else:
        logger.error(f"Unexpected error during {operation}: {error}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(error)}"
        )

