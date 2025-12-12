import logging

def get_logger(name: str | None = None) -> logging.Logger:
    """
    Returns a logger instance for the specified name.

    Retrieves a logger from the logging module, creating it if necessary.

    Args:
        name: Optional name for the logger.

    Returns:
        logging.Logger: Logger instance for the given name.
    """
    logger = logging.getLogger(name)

    return logger
