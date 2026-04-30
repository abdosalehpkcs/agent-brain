"""Centralized logging configuration for the agent-brain backend."""

from __future__ import annotations

import logging
import os

_configured = False


def configure_logging() -> None:
    """Configure the root logger once. Subsequent calls are no-ops."""
    global _configured
    if _configured:
        return

    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_format = os.getenv(
        "LOG_FORMAT",
        "%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    logging.basicConfig(level=getattr(logging, log_level, logging.INFO), format=log_format)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a named logger, ensuring logging has been configured."""
    configure_logging()
    return logging.getLogger(name)
