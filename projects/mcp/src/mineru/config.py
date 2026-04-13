"""Configuration helpers for the MinerU MCP service."""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

MINERU_API_BASE = os.getenv("MINERU_API_BASE", "https://mineru.net")
MINERU_API_KEY = os.getenv("MINERU_API_KEY", "")

USE_LOCAL_API = os.getenv("USE_LOCAL_API", "").lower() in ["true", "1", "yes"]
LOCAL_MINERU_API_BASE = os.getenv("LOCAL_MINERU_API_BASE", "http://localhost:8080")

DEFAULT_OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./downloads")


def setup_logging():
    """Build the module logger from environment settings."""
    log_level = os.getenv("MINERU_LOG_LEVEL", "INFO").upper()
    debug_mode = os.getenv("MINERU_DEBUG", "").lower() in ["true", "1", "yes"]

    if debug_mode:
        log_level = "DEBUG"

    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    if log_level not in valid_levels:
        log_level = "INFO"

    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    logging.basicConfig(level=getattr(logging, log_level), format=log_format)

    logger = logging.getLogger("mineru")
    logger.setLevel(getattr(logging, log_level))

    logger.info(f"Log level set to: {log_level}")

    return logger


logger = setup_logging()


def ensure_output_dir(output_dir=None):
    """Create the output directory if it does not exist."""
    output_path = Path(output_dir or DEFAULT_OUTPUT_DIR)
    output_path.mkdir(parents=True, exist_ok=True)
    return output_path


def validate_api_config():
    """Return the current API configuration status."""
    return {
        "api_base": MINERU_API_BASE,
        "api_key_set": bool(MINERU_API_KEY),
        "output_dir": DEFAULT_OUTPUT_DIR,
    }
