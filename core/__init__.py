"""Core package: config, logging, exceptions, shared types."""

from core.config import settings
from core.logging import get_logger

__all__ = ["settings", "get_logger"]
