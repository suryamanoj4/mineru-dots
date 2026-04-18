"""VParse File转Markdown转换服务的配置工具。"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# API 配置
VPARSE_API_BASE = os.getenv("VPARSE_API_BASE", "https://vparse.net")
VPARSE_API_KEY = os.getenv("VPARSE_API_KEY", "")

# Local API Configuration
USE_LOCAL_API = os.getenv("USE_LOCAL_API", "").lower() in ["true", "1", "yes"]
LOCAL_VPARSE_API_BASE = os.getenv("LOCAL_VPARSE_API_BASE", "http://localhost:8080")

# Default output directory for converted files
DEFAULT_OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./downloads")


# Set up logging system
def setup_logging():
    """
    Set up the logging system, configuring the log level based on environment variables.

    Returns:
        logging.Logger: Configured logger.
    """
    # 获取环境变量中的日志级别设置
    log_level = os.getenv("VPARSE_LOG_LEVEL", "INFO").upper()
    debug_mode = os.getenv("VPARSE_DEBUG", "").lower() in ["true", "1", "yes"]

    # If debug_mode is set, override log_level
    if debug_mode:
        log_level = "DEBUG"

    # Ensure log_level is valid
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    if log_level not in valid_levels:
        log_level = "INFO"

    # Set log format
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Configure logging
    logging.basicConfig(level=getattr(logging, log_level), format=log_format)

    logger = logging.getLogger("vparse")
    logger.setLevel(getattr(logging, log_level))

    # Output log level information
    logger.info(f"Log level set to: {log_level}")

    return logger


# Create default logger
logger = setup_logging()


# Create output directory if it does not exist
def ensure_output_dir(output_dir=None):
    """
    Ensure the output directory exists.

    Args:
        output_dir: Optional path for the output directory. If None, DEFAULT_OUTPUT_DIR is used.

    Returns:
        Path object for the output directory.
    """
    output_path = Path(output_dir or DEFAULT_OUTPUT_DIR)
    output_path.mkdir(parents=True, exist_ok=True)
    return output_path


# Validate API configuration
def validate_api_config():
    """
    Verify that required API configurations are set.

    Returns:
        dict: Configuration status.
    """
    return {
        "api_base": VPARSE_API_BASE,
        "api_key_set": bool(VPARSE_API_KEY),
        "output_dir": DEFAULT_OUTPUT_DIR,
    }
