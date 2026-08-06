"""
Centralized logging configuration.

Usage:
    from core.logging import get_logger
    logger = get_logger(__name__)
    logger.info("message")
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

from core.config import settings

_CONFIGURED = False


def _configure_root() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    fmt = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    handlers: list[logging.Handler] = [
        logging.StreamHandler(sys.stdout),
    ]

    if settings.log_file:
        log_path = Path(settings.log_file)
        if not log_path.is_absolute():
            log_path = settings.project_root / log_path
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_path, encoding="utf-8"))

    logging.basicConfig(
        level=level,
        format=fmt,
        datefmt=datefmt,
        handlers=handlers,
        force=True,
    )
    _CONFIGURED = True


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Return a named logger (configures root on first call)."""
    _configure_root()
    return logging.getLogger(name or "ava")
