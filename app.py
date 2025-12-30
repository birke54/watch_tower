"""
Main application entry point for Watch Tower.

This module provides the main application class and startup/shutdown logic.
"""

import asyncio
import signal
import sys

import uvicorn

from watch_tower.config import config
from watch_tower.core.bootstrap import bootstrap
from watch_tower.core.business_logic_manager import BUSINESS_LOGIC_MANAGER as business_logic_manager
from api import create_management_app
from utils.logging_config import setup_logging


def setup_signal_handlers(loop, business_logic_manager):
    """Setup signal handlers for graceful shutdown."""
    def handle_sigterm():
        print("[DEBUG] Received SIGTERM: shutting down application.")
        loop.create_task(business_logic_manager.stop())
        sys.exit(0)

    try:
        # Try to use add_signal_handler (Unix/Linux)
        loop.add_signal_handler(signal.SIGTERM, handle_sigterm)
        print("[DEBUG] Signal handler registered using add_signal_handler")
    except (NotImplementedError, AttributeError):
        # Fallback to signal.signal (works on more platforms)
        try:
            signal.signal(signal.SIGTERM, lambda signum, frame: handle_sigterm())
            print("[DEBUG] Signal handler registered using signal.signal")
        except (OSError, ValueError) as e:
            print(f"[WARNING] Could not register signal handler: {e}")
            print("[WARNING] Graceful shutdown may not work properly")


async def start_management_server():
    """Start the FastAPI management server in a separate task."""
    app = create_management_app()
    server_config = uvicorn.Config(
        app=app,
        host=config.management.host,
        port=config.management.port,
        log_level=config.management.log_level,
        access_log=config.management.access_log
    )
    server = uvicorn.Server(server_config)
    await server.serve()


def main() -> None:
    """Main entry point for the Watch Tower application."""
    try:
        # Setup logging with config values
        setup_logging(
            level=getattr(
                config,
                'logging',
                None) and getattr(
                    config.logging,
                    'level',
                    None),
            log_file=getattr(
                config,
                'logging',
                None) and getattr(
                    config.logging,
                    'log_file',
                    None),
            log_format=getattr(
                config,
                'logging',
                None) and getattr(
                    config.logging,
                    'format',
                    None),
            max_files=getattr(
                config,
                'logging',
                None) and getattr(
                    config.logging,
                    'max_files',
                    5))
        # Setup event loop and signal handlers
        loop = asyncio.get_event_loop()
        setup_signal_handlers(loop, business_logic_manager)
        # Run bootstrap
        print("Starting Watch Tower...")
        loop.run_until_complete(bootstrap())
        print("Bootstrap completed successfully")
        # Start event loop
        print("Starting event loop...")
        loop.run_until_complete(_run_main_application_loop())
    except KeyboardInterrupt:
        print("\nReceived keyboard interrupt, shutting down...")
    except Exception as e:
        print(f"Application failed to start: {e}")
        sys.exit(1)


async def _run_main_application_loop() -> None:
    """Run the main application loop with management server and business logic management."""
    try:
        # Start the management server
        management_server_task = asyncio.create_task(start_management_server())
        print(
            f"""Management API server started on http://{config.management.host}:
            {config.management.port}""")

        # Start the business logic loop
        await business_logic_manager.start()
        while True:
            if business_logic_manager.running:
                await asyncio.sleep(1)
            else:
                # Idle loop: periodically check if the business logic loop should be
                # restarted
                await asyncio.sleep(2)
                state = business_logic_manager.get_status()
                if state.get("running", False) and not business_logic_manager.running:
                    print(
                        """[DEBUG] Detected running=True in state file,
                        restarting business logic loop...""")
                    await business_logic_manager.start()
    except KeyboardInterrupt:
        print("Received keyboard interrupt, shutting down...")
    finally:
        # Ensure graceful shutdown
        await business_logic_manager.stop()
        # Cancel management server task
        management_server_task.cancel()
        try:
            await management_server_task
        except asyncio.CancelledError:
            pass

if __name__ == "__main__":
    main()
