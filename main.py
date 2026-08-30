#!/usr/bin/env python3
"""
Entry point for Valkyria
"""
import signal
import sys
import logging
from app.application import ValkyriaApp
from app.logging_config import setup_logging

app_instance = None

logger = logging.getLogger(__name__)

def signal_handler(signum, frame):
    """Handle system signals for clean shutdown."""
    logger.info(f"Received signal {signum}, shutting down gracefully...")
    if app_instance and hasattr(app_instance, 'player'):
        try:
            app_instance.player.__del__()
            logger.info("Audio cleanup completed")
        except Exception as e:
            logger.error(f"Error during audio cleanup: {e}")
    sys.exit(0)

def main():
    global app_instance

    # Support for Windows multiprocessing
    import multiprocessing
    multiprocessing.freeze_support()

    # Setup signal handlers for clean shutdown
    signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # Termination signal

    setup_logging()
    app_instance = ValkyriaApp()
    app_instance.run()

if __name__ == "__main__":
    main()
