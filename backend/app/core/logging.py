"""Structured logging configuration for the EnterpriseGPT backend.

Uses Python's standard `logging` module configured to emit structured,
timestamped log lines. This is intentionally dependency-light in Phase 1;
Phase 6 (Observability) will extend this with OpenTelemetry trace/span
correlation.
"""

import logging
import sys

from app.core.config import get_settings


def configure_logging() -> None:
    """Configure the root logger for the application.

    This should be called exactly once, during application startup.
    It sets the log level from settings and installs a single stream
    handler with a consistent format so log aggregators (e.g. Cloud
    Logging, Grafana Loki) can parse output reliably.
    """
    settings = get_settings()

    root_logger = logging.getLogger()
    root_logger.setLevel(settings.log_level.upper())

    # Avoid duplicate handlers if configure_logging() is called more than once
    # (e.g. under pytest with multiple app instantiations).
    if root_logger.handlers:
        return

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # Quiet down noisy third-party loggers at INFO level.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a module-scoped logger.

    Args:
        name: Typically `__name__` of the calling module.

    Returns:
        A configured `Logger` instance.
    """
    return logging.getLogger(name)
