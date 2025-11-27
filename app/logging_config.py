import logging
import sys
from pathlib import Path

def setup_logging():
    """
    Configure logging for the application.
    Logs to a file in the current working directory (no console output).
    """
    # Create a custom logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # File logging - write to current working directory
    try:
        log_file = Path('tango_studio.log')
        f_handler = logging.FileHandler(log_file, encoding='utf-8')
        f_handler.setLevel(logging.INFO)
        f_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        f_handler.setFormatter(f_format)
        logger.addHandler(f_handler)
    except Exception:
        # If we can't write to the log file, fall back to console
        c_handler = logging.StreamHandler(sys.stdout)
        c_handler.setLevel(logging.INFO)
        c_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        c_handler.setFormatter(c_format)
        logger.addHandler(c_handler)

    logging.info("Logging setup complete - writing to file")
