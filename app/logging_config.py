import logging
import sys
from app.paths import get_user_data_path

def setup_logging():
    """
    Configure logging for the application.
    Logs to a file in the user data directory (no console output).
    """
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    try:
        log_dir = get_user_data_path()
        log_file = log_dir / 'valkyria.log'
        f_handler = logging.FileHandler(log_file, encoding='utf-8')
        f_handler.setLevel(logging.INFO)
        f_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        f_handler.setFormatter(f_format)
        logger.addHandler(f_handler)

        logging.info(f"Logging initialized at {log_file}")
    except Exception:
        c_handler = logging.StreamHandler(sys.stdout)
        c_handler.setLevel(logging.INFO)
        c_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        c_handler.setFormatter(c_format)
        logger.addHandler(c_handler)
        logging.warning("Failed to setup file logging, falling back to console", exc_info=True)

    logging.info("Logging setup complete")
