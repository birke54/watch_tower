"""
Business Logic Commands

This module contains the business logic management commands for starting
and stopping the business logic loop.
"""

import asyncio
import logging
import sys

import click

from cli.services import WatchTowerService
from cli.utils import handle_cli_error
from watch_tower.exceptions import DependencyError, ManagementAPIError

logger = logging.getLogger(__name__)

# Constants
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8080

# Initialize service
service = WatchTowerService()


@click.group()
def business_logic_group():
    """Manage the business logic loop."""


@business_logic_group.command()
@click.option('--host', default=DEFAULT_HOST,
              help=f'API host (default: {DEFAULT_HOST})')
@click.option('--port', default=DEFAULT_PORT,
              help=f'API port (default: {DEFAULT_PORT})')
@click.pass_context
def start(ctx: click.Context, host: str, port: int) -> None:
    """Start the business logic loop via HTTP API."""
    try:
        if ctx.obj.get('verbose'):
            logger.debug(
                f"Starting business logic loop via API at http://{host}:{port}/start...")

        result = asyncio.run(service.start_business_logic_api(host, port))

        if ctx.obj.get('verbose'):
            logger.debug(f"Start API response: {result}")

        click.echo("✅ Business logic loop started successfully")

    except DependencyError as e:
        click.echo(f"❌ {e}")
        sys.exit(1)
    except ManagementAPIError as e:
        click.echo(f"❌ Failed to start business logic loop: {e}")
        if ctx.obj.get('verbose') and e.original_error:
            logger.debug(f"Original error: {e.original_error}")
        sys.exit(1)
    except Exception as e:
        handle_cli_error(e, f"Failed to start business logic loop: {e}", ctx)


@business_logic_group.command()
@click.option('--host', default=DEFAULT_HOST,
              help=f'API host (default: {DEFAULT_HOST})')
@click.option('--port', default=DEFAULT_PORT,
              help=f'API port (default: {DEFAULT_PORT})')
@click.pass_context
def stop(ctx: click.Context, host: str, port: int) -> None:
    """Stop the business logic loop via HTTP API."""
    try:
        if ctx.obj.get('verbose'):
            logger.debug(
                f"Stopping business logic loop via API at http://{host}:{port}/stop...")

        result = asyncio.run(service.stop_business_logic_api(host, port))

        if ctx.obj.get('verbose'):
            logger.debug(f"Stop API response: {result}")

        click.echo("✅ Business logic loop stopped successfully")

    except DependencyError as e:
        click.echo(f"❌ {e}")
        sys.exit(1)
    except ManagementAPIError as e:
        click.echo(f"❌ Failed to stop business logic loop: {e}")
        if ctx.obj.get('verbose') and e.original_error:
            logger.debug(f"Original error: {e.original_error}")
        sys.exit(1)
    except Exception as e:
        handle_cli_error(e, f"Failed to stop business logic loop: {e}", ctx)
