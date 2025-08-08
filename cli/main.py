"""
Watch Tower CLI Main Entry Point

This module serves as the main entry point for the Watch Tower CLI,
bringing together all command groups and providing the main CLI interface.
"""

import logging

import click

from cli.commands import status_command, business_logic_group, visitor_log_group

logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version="3.0.0")
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """Watch Tower - Video Surveillance System CLI

    This CLI provides commands to manage the Watch Tower video surveillance system,
    including starting and stopping the business logic loop, checking system status,
    and managing the application lifecycle.
    """
    # Ensure ctx.obj exists and is a dict
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose

    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Verbose mode enabled")

# Add command groups to the main CLI
cli.add_command(status_command, name='status')
cli.add_command(business_logic_group, name='business-logic')
cli.add_command(visitor_log_group, name='visitor-log')


if __name__ == '__main__':
    cli()