import sys
from loguru import logger
from app.core.config import LOG_LEVEL

def setup_logging() -> None:
    logger.remove()

    logger.add(
        sys.stdout,
        level=LOG_LEVEL,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
    )

    logger.add(
        "logs/app.log",
        rotation="10 MB",
        retention="14 days",
        level=LOG_LEVEL,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
    )

    logger.info("Logging initialized")
