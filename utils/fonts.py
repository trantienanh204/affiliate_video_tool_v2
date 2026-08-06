"""Find a font that supports Vietnamese characters."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from core.logging import get_logger

logger = get_logger(__name__)

# Ordered by preference (Vietnamese coverage first)
_CANDIDATES = [
    # Project assets
    "assets/fonts/NotoSans-Regular.ttf",
    "assets/fonts/DejaVuSans.ttf",
    # Linux common
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansVietnamese-Regular.ttf",
    # Windows
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\arialuni.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
    r"C:\Windows\Fonts\tahoma.ttf",
    r"C:\Windows\Fonts\calibri.ttf",
    # macOS
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
]


@lru_cache(maxsize=1)
def find_vietnamese_font() -> str | None:
    """Return first existing font path that can render Vietnamese, or None."""
    root = Path(__file__).resolve().parents[1]
    for candidate in _CANDIDATES:
        p = Path(candidate)
        if not p.is_absolute():
            p = root / p
        if p.is_file():
            logger.debug("Using font: %s", p)
            return str(p)
    # Last resort: let MoviePy / system pick a default name
    for name in ("DejaVuSans", "Arial", "Noto Sans", "Liberation Sans"):
        logger.warning("No font file found, trying system name: %s", name)
        return name
    logger.error("No suitable Vietnamese font found")
    return None
