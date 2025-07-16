"""
Status Command

This module contains the status command implementation for displaying
comprehensive system status information.
"""

import json
import logging
from datetime import datetime, timezone

import click

from cli.services import WatchTowerService
from cli.utils import (
    validate_aws_config,
    validate_database_config,
    validate_ring_config,
    validate_app_config,
    handle_cli_error,
)

logger = logging.getLogger(__name__)

# Initialize service
service = WatchTowerService()


@click.command()
@click.option('--format', '-f', default='text', type=click.Choice(['text', 'json']), help='Output format (text or json)')
@click.option('--detailed', '-d', is_flag=True, help='Show detailed status information')
@click.pass_context
def status_command(ctx: click.Context, format: str, detailed: bool) -> None:
    """Show comprehensive system status."""
    try:
        if ctx.obj.get('verbose'):
            logger.debug("Getting comprehensive system status...")
        
        # Get business logic status
        business_logic_status = service.get_status()
        
        # Validate configuration
        config_results = []
        config_passed = 0
        config_failed = 0
        config_warnings = 0
        
        try:
            # AWS Configuration
            aws_results = validate_aws_config()
            config_results.extend(aws_results)
            for result in aws_results:
                if result['status'] == '✅':
                    config_passed += 1
                elif result['status'] == '❌':
                    config_failed += 1
                elif result['status'] == '⚠️':
                    config_warnings += 1
        except Exception as e:
            config_results.append({
                'status': '❌',
                'field': 'AWS Configuration',
                'value': 'Error',
                'message': str(e)
            })
            config_failed += 1
        
        try:
            # Database Configuration
            db_results = validate_database_config()
            config_results.extend(db_results)
            for result in db_results:
                if result['status'] == '✅':
                    config_passed += 1
                elif result['status'] == '❌':
                    config_failed += 1
                elif result['status'] == '⚠️':
                    config_warnings += 1
        except Exception as e:
            config_results.append({
                'status': '❌',
                'field': 'Database Configuration',
                'value': 'Error',
                'message': str(e)
            })
            config_failed += 1
        
        try:
            # Ring Configuration
            ring_results = validate_ring_config()
            config_results.extend(ring_results)
            for result in ring_results:
                if result['status'] == '✅':
                    config_passed += 1
                elif result['status'] == '❌':
                    config_failed += 1
                elif result['status'] == '⚠️':
                    config_warnings += 1
        except Exception as e:
            config_results.append({
                'status': '❌',
                'field': 'Ring Configuration',
                'value': 'Error',
                'message': str(e)
            })
            config_failed += 1
        
        try:
            # App Configuration
            app_results = validate_app_config()
            config_results.extend(app_results)
            for result in app_results:
                if result['status'] == '✅':
                    config_passed += 1
                elif result['status'] == '❌':
                    config_failed += 1
                elif result['status'] == '⚠️':
                    config_warnings += 1
        except Exception as e:
            config_results.append({
                'status': '❌',
                'field': 'App Configuration',
                'value': 'Error',
                'message': str(e)
            })
            config_failed += 1
        
        # Determine overall status
        if config_failed > 0:
            overall_status = "❌ Unhealthy"
        elif config_warnings > 0:
            overall_status = "⚠️  Warning"
        else:
            overall_status = "✅ Healthy"
        
        # Build status info
        status_info = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_status": overall_status,
            "business_logic": business_logic_status,
            "configuration": {
                "passed": config_passed,
                "failed": config_failed,
                "warnings": config_warnings,
                "results": config_results
            }
        }
        
        if ctx.obj.get('verbose'):
            logger.debug(f"System status: {status_info}")
        
        if format == 'json':
            click.echo(json.dumps(status_info, indent=2))
        else:
            click.echo("🏰 Watch Tower System Status")
            click.echo("=" * 40)
            click.echo(f"Overall Status: {overall_status}")
            click.echo(f"Timestamp: {status_info['timestamp']}")
            
            click.echo("\n🔄 Business Logic Loop:")
            bl_status = business_logic_status
            click.echo(f"  Status: {'🟢 Running' if bl_status.get('running') else '🔴 Stopped'}")
            click.echo(f"  Start Time: {bl_status.get('start_time', 'Unknown')}")
            click.echo(f"  Uptime: {bl_status.get('uptime', 'Unknown')}")
            
            if 'error' in bl_status:
                click.echo(f"  Error: {bl_status['error']}")
            
            click.echo(f"\n⚙️  Configuration:")
            click.echo(f"  ✅ Passed: {config_passed}")
            click.echo(f"  ❌ Failed: {config_failed}")
            click.echo(f"  ⚠️  Warnings: {config_warnings}")
            
            if detailed and config_results:
                click.echo("\n📋 Configuration Details:")
                for result in config_results:
                    status_icon = result['status']
                    field = result['field']
                    value = result['value']
                    message = result.get('message', '')
                    display_value = str(value) if value is not None else 'Not set'
                    click.echo(f"  {status_icon} {field}: {display_value}")
                    if message:
                        click.echo(f"     💡 {message}")
            
            # Summary
            if config_failed > 0:
                click.echo(f"\n❌ System has {config_failed} configuration errors")
                click.echo("💡 Check your environment variables and configuration")
            elif config_warnings > 0:
                click.echo(f"\n⚠️  System has {config_warnings} configuration warnings")
            else:
                click.echo("\n✅ All systems operational")
            
    except Exception as e:
        handle_cli_error(e, f"Failed to get system status: {e}", ctx) 