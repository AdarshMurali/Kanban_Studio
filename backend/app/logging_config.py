import logging
import sys
from pythonjsonlogger import jsonlogger

def setup_logging():
    """Setup application logging"""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Create console handler with JSON formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)

    # JSON formatter
    formatter = jsonlogger.JsonFormatter(
        '%(asctime)s %(name)s %(levelname)s %(message)s %(pathname)s %(lineno)d'
    )
    console_handler.setFormatter(formatter)

    logger.addHandler(console_handler)

    return logger

# Application logger
app_logger = setup_logging()