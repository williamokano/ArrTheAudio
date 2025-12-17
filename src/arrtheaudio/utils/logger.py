"""Structured logging configuration for ArrTheAudio."""

import logging
import sys
from pathlib import Path
from typing import Any, Optional

import structlog

from arrtheaudio.config import LoggingConfig


def setup_logging(config: LoggingConfig) -> None:
    """Configure structured logging.

    Args:
        config: Logging configuration
    """
    # Create log directory if it doesn't exist
    log_path = Path(config.output)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Configure processors
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    # Add renderer based on format
    if config.format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    # Configure structlog
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure stdlib logging
    handlers = []

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, config.level.upper()))
    handlers.append(console_handler)

    # File handler
    try:
        file_handler = logging.FileHandler(config.output, mode="a", encoding="utf-8")
        file_handler.setLevel(getattr(logging, config.level.upper()))
        handlers.append(file_handler)
    except (OSError, PermissionError) as e:
        # If we can't create file handler, just log to console
        print(f"Warning: Could not create log file {config.output}: {e}", file=sys.stderr)

    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, config.level.upper()),
        handlers=handlers,
        force=True,  # Override any existing configuration
    )


def get_logger(name: Optional[str] = None) -> structlog.stdlib.BoundLogger:
    """Get a logger instance.

    Args:
        name: Logger name (defaults to caller's module name)

    Returns:
        Structured logger instance
    """
    return structlog.get_logger(name)
