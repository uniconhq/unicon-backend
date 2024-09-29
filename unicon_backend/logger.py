import logging
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

DATE_FORMAT = "%d-%m-%Y %H:%M:%S"
LOGGER_FORMAT = "%(asctime)s | %(message)s"


class LoggerConfig(BaseModel):
    handlers: list
    format: str | None = None
    date_format: str | None = None
    logger_file: Path | None = None
    level: int = logging.INFO


@lru_cache
def get_logger_config():
    from rich.logging import RichHandler

    return LoggerConfig(
        handlers=[RichHandler(rich_tracebacks=True, tracebacks_show_locals=True, show_time=False)],
        format=LOGGER_FORMAT,
        date_format=DATE_FORMAT,
    )


def setup_rich_logger():
    # Remove all handlers from root logger
    # and proprogate to root logger.
    for name in logging.root.manager.loggerDict:
        logging.getLogger(name).handlers = []
        logging.getLogger(name).propagate = True

    logger_config = get_logger_config()  # get Rich logging config

    logging.basicConfig(
        level=logger_config.level,
        format=logger_config.format,
        datefmt=logger_config.date_format,
        handlers=logger_config.handlers,
    )
