"""
Structured logging configuration using structlog.

Call configure_logging() exactly once at application startup (in lifespan).
After that, use structlog.get_logger(__name__) everywhere.
"""

import logging
import sys
from typing import Literal

import structlog


def _safe_add_logger_name(
    logger: object, method_name: str, event_dict: dict
) -> dict:
    # stdlib ProcessorFormatter can pass None as logger for some internal records
    record = event_dict.get("_record")
    if record is not None:
        event_dict.setdefault("logger", record.name)
    elif logger is not None:
        event_dict["logger"] = getattr(logger, "name", repr(logger))
    return event_dict


def configure_logging(
    level: str = "INFO",
    fmt: Literal["json", "console"] = "json",
) -> None:
    log_level = getattr(logging, level.upper(), logging.INFO)

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        _safe_add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]

    if fmt == "json":
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            *shared_processors,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(log_level)

    # Silence noisy third-party loggers
    for noisy in ("uvicorn.access", "sqlalchemy.engine", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
