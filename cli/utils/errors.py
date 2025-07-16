"""
CLI Error Handling Utilities

This module contains utility functions for error handling and creating
standardized error responses and validation results.
"""

import logging
import sys
from typing import Any, Dict

import click

logger = logging.getLogger(__name__)


def create_validation_result(status: str, field: str, value: Any, message: str = "") -> Dict[str, Any]:
    """Create a standardized validation result."""
    return {
        'status': status,
        'field': field,
        'value': value,
        'message': message
    }


def create_error_status_response(error_message: str) -> Dict[str, Any]:
    """Create a standardized error status response."""
    return {
        "running": False,
        "start_time": "Unknown",
        "uptime": "Unknown",
        "business_logic_completed": True,
        "business_logic_cancelled": False,
        "error": error_message
    }


def handle_cli_error(error: Exception, error_msg: str, ctx: click.Context) -> None:
    """Handle CLI errors consistently."""
    logger.error(error_msg)
    if ctx.obj.get('verbose'):
        logger.exception("Full traceback:")
    click.echo(f"❌ {error_msg}")
    sys.exit(1) 