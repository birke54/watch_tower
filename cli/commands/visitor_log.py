"""
Visitor Log Commands

This module contains the visitor log management commands for viewing
and managing visitor log entries.
"""

import json
import logging

import click

from cli.utils import format_confidence_score, format_timestamp, create_json_entry, handle_cli_error

logger = logging.getLogger(__name__)

# Constants
DEFAULT_VISITOR_LOG_LIMIT = 10


@click.group()
def visitor_log_group():
    """Manage and view visitor log entries."""


@visitor_log_group.command()
@click.option('--limit', '-l', default=DEFAULT_VISITOR_LOG_LIMIT, help=f'Number of entries to display (default: {DEFAULT_VISITOR_LOG_LIMIT})')
@click.option('--format', '-f', default='text', type=click.Choice(['text', 'json']), help='Output format (text or json)')
@click.option('--show-more', '-m', is_flag=True, help='Show more entries after initial display')
@click.pass_context
def recent(ctx: click.Context, limit: int, format: str, show_more: bool) -> None:
    """Show recent visitor log entries."""
    try:
        if ctx.obj.get('verbose'):
            logger.debug(f"Fetching recent visitor log entries (limit: {limit})")
        
        # Import here to avoid circular imports
        from db.repositories.visitor_log_repository import VisitorLogRepository
        from db.connection import get_database_connection
        
        # Get database connection and repository
        engine, session_factory = get_database_connection()
        visitor_log_repo = VisitorLogRepository()
        
        # Create a session and fetch recent entries
        with session_factory() as db_session:
            entries = visitor_log_repo.get_recent_entries(db_session, limit=limit)
        
        if ctx.obj.get('verbose'):
            logger.debug(f"Retrieved {len(entries)} visitor log entries")
        
        if format == 'json':
            # Convert entries to JSON-serializable format
            json_entries = [create_json_entry(entry) for entry in entries]
            click.echo(json.dumps(json_entries, indent=2))
        else:
            if not entries:
                click.echo("📋 No visitor log entries found")
                return
            
            click.echo("📋 Recent Visitor Log Entries")
            click.echo("=" * 100)
            
            # Print table header
            click.echo(f"{'#':<3} {'Name':<20} {'Camera':<20} {'Time':<25} {'Confidence':<12}")
            click.echo("-" * 85)
            
            # Print table rows
            for i, entry in enumerate(entries, 1):
                name = entry.persons_name or 'Unknown'
                camera = entry.camera_name or 'Unknown'
                time_str = format_timestamp(entry.visited_at)
                confidence = format_confidence_score(entry.confidence_score)
                click.echo(f"{i:<3} {name:<20} {camera:<20} {time_str:<25} {confidence:<12}")
            
            click.echo("-" * 85)
            
            click.echo(f"Showing {len(entries)} of {limit} most recent entries")
            
            if not show_more and len(entries) == limit:
                click.echo("\n💡 Use --show-more to display additional entries")
                click.echo("   Use --limit to change the number of entries displayed")
        
    except Exception as e:
        handle_cli_error(e, f"Failed to fetch visitor log entries: {e}", ctx) 