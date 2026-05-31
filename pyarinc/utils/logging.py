import logging


def get_logger(name: str) -> logging.Logger:
    """Return a module-level logger configured for the library (no global side effects)."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        # library default: do not add handlers that change global logging state
        logger.setLevel(logging.INFO)
    return logger
