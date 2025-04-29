import logging
import hashlib
from pathlib import Path

def setup_logging(log_level_str='INFO'):
    """Configures logging for the application."""
    log_level = getattr(logging, log_level_str.upper(), logging.INFO)
    logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    # Optionally, suppress overly verbose libraries
    # logging.getLogger("some_library").setLevel(logging.WARNING)

def get_logger(name):
    """Gets a logger instance for a specific module."""
    return logging.getLogger(name)

def calculate_sha256(filepath):
    """Calculates the SHA256 hash of a file.

    Args:
        filepath (Path): The path to the file.

    Returns:
        str | None: The hex digest of the SHA256 hash, or None if an error occurs.
    """
    logger = get_logger(__name__)
    hasher = hashlib.sha256()
    try:
        with open(filepath, 'rb') as file:
            while True:
                chunk = file.read(4096)
                if not chunk:
                    break
                hasher.update(chunk)
        return hasher.hexdigest()
    except IOError as e:
        logger.error(f"Could not read file {filepath}: {e}")
        return None 