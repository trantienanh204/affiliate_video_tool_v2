"""Procedural 2D/2.5D Cartoon Animation Engine for Kids Videos (0đ cost, 100% dynamic motion).

Transforms static illustrations into lively, bouncing cartoon animations:
- Animated drifting clouds & rotating sun rays
- Rhythmic character hopping, squash & stretch, and playful tilting
- Bouncing cartoon apples / counting objects with pop-in effects
- Kawaii procedural animal characters (rabbit, bear, monkey, cat, dog, panda, lion, elephant)
- Floating sparkles & colorful bubbles
- Fully synchronized, high-contrast subtitle pill showing the EXACT spoken voiceover text

All characters are drawn 100% procedurally using PIL — no external images needed.
Character type is inferred from card.image_prompt and card.emoji keywords.
"""

from __future__ import annotations

import math
import re
import textwrap
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy import VideoClip

from video.kids_education.canvas import _get_font, _fit_text, sanitize_emoji
from video.kids_education.presets import KidsCard


def _hex_to_rgb(hex_code: str) -> tuple[int, int, int]:
    hex_code = hex_code.lstrip("#")
    if len(hex_code) == 3:
        hex_code = "".join(c * 2 for c in hex_code)
    try:
        return tuple(int(hex_code[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:
        return (255, 107, 107)


# ---------------------------------------------------------------------------
# Kawaii Apple (counting prop — reused for apple-counting scenes)
# ---------------------------------------------------------------------------

def _draw_cartoon_apple_small(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int) -> None:
    """Draws a cute, shiny kawaii cartoon apple at (cx, cy)."""
    r = max(8, size // 2)
    draw.ellipse([(cx - int(r * 0.9), cy - int(r * 0.7)), (cx + int(r * 0.9), cy + int(r * 0.9))], fill=(239, 68, 68))
    draw.line([(cx, cy - int(r * 0.7)), (cx + int(r * 0.2), cy - int(r * 1.15))], fill=(120, 53, 15), width=max(2, int(r * 0.15)))
    draw.ellipse([(cx + int(r * 0.15), cy - int(r * 1.1)), (cx + int(r * 0.65), cy - int(r * 0.75))], fill=(34, 197, 94))
    eye_r = max(2, int(r * 0.12))
    draw.ellipse([(cx - int(r * 0.35) - eye_r, cy - eye_r), (cx - int(r * 0.35) + eye_r, cy + eye_r)], fill=(30, 41, 59))
    draw.ellipse([(cx + int(r * 0.35) - eye_r, cy - eye_r), (cx + int(r * 0.35) + eye_r, cy + eye_r)], fill=(30, 41, 59))
    draw.arc([(cx - int(r * 0.25), cy), (cx + int(r * 0.25), cy + int(r * 0.35))], start=0, end=180, fill=(30, 41, 59), width=max(2, int(r * 0.08)))


# ---------------------------------------------------------------------------
# Kawaii Animal Drawers — each function draws a cute animal centered at (cx, cy)
# with a "size" radius unit.  All use PIL only.
# ---------------------------------------------------------------------------

def _draw_kawaii_rabbit(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int) -> None:
    """Adorable white fluffy bunny with big pink-tipped ears."""
    r = max(20, size)
    # Body
    draw.ellipse([(cx - r, cy - int(r * 0.6)), (cx + r, cy + int(r * 0.9))], fill=(245, 245, 245), outline=(200, 200, 200), width=2)
    # Head
    hd_r = int(r * 0.65)
    draw.ellipse([(cx - hd_r, cy - int(r * 0.6) - hd_r * 2 + hd_r // 2), (cx + hd_r, cy - int(r * 0.6) + hd_r // 2)], fill=(245, 245, 245), outline=(200, 200, 200), width=2)
    hd_cy = cy - int(r * 0.6) - hd_r + hd_r // 2  # head center y
    # Long Ears
    for ex in [-int(hd_r * 0.4), int(hd_r * 0.4)]:
        ear_top_y = hd_cy - hd_r - int(r * 0.9)
        draw.ellipse([(cx + ex - int(hd_r * 0.22), ear_top_y), (cx + ex + int(hd_r * 0.22), hd_cy - hd_r + 10)], fill=(245, 245, 245), outline=(200, 200, 200), width=2)
        # Pink inside
        draw.ellipse([(cx + ex - int(hd_r * 0.12), ear_top_y + 6), (cx + ex + int(hd_r * 0.12), hd_cy - hd_r + 8)], fill=(255, 182, 193))
    # Eyes
    eye_r = max(4, int(hd_r * 0.15))
    for ex in [-int(hd_r * 0.35), int(hd_r * 0.35)]:
        draw.ellipse([(cx + ex - eye_r, hd_cy - eye_r), (cx + ex + eye_r, hd_cy + eye_r)], fill=(30, 41, 59))
        draw.ellipse([(cx + ex + 1, hd_cy - eye_r + 1), (cx + ex + 3, hd_cy - eye_r + 3)], fill=(255, 255, 255))
    # Pink nose
    draw.ellipse([(cx - 5, hd_cy + 2), (cx + 5, hd_cy + 10)], fill=(255, 105, 135))
    # Smile
    draw.arc([(cx - 10, hd_cy + 6), (cx + 10, hd_cy + 20)], start=0, end=180, fill=(30, 41, 59), width=2)
    # Tiny Tail
    draw.ellipse([(cx + r - 10, cy + int(r * 0.3)), (cx + r + 8, cy + int(r * 0.6))], fill=(255, 255, 255), outline=(200, 200, 200), width=1)
    # Little arms/paws
    draw.ellipse([(cx - r - 8, cy), (cx - r + 8, cy + int(r * 0.5))], fill=(240, 240, 240), outline=(200, 200, 200), width=1)
    draw.ellipse([(cx + r - 8, cy), (cx + r + 8, cy + int(r * 0.5))], fill=(240, 240, 240), outline=(200, 200, 200), width=1)


def _draw_kawaii_bear(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int) -> None:
    """Friendly brown Teddy Bear with round ears and tummy patch."""
    r = max(20, size)
    bear_brown = (180, 110, 50)
    light_brown = (225, 175, 110)
    # Body
    draw.ellipse([(cx - r, cy - int(r * 0.5)), (cx + r, cy + int(r * 0.95))], fill=bear_brown)
    # Tummy patch
    draw.ellipse([(cx - int(r * 0.55), cy - int(r * 0.1)), (cx + int(r * 0.55), cy + int(r * 0.75))], fill=light_brown)
    # Head
    hd_r = int(r * 0.65)
    hd_cy = cy - int(r * 0.5) - hd_r + hd_r // 3
    draw.ellipse([(cx - hd_r, hd_cy - hd_r), (cx + hd_r, hd_cy + hd_r)], fill=bear_brown)
    # Round Ears
    for ex in [-int(hd_r * 0.75), int(hd_r * 0.75)]:
        ear_r = int(hd_r * 0.38)
        draw.ellipse([(cx + ex - ear_r, hd_cy - hd_r - ear_r // 2), (cx + ex + ear_r, hd_cy - hd_r + ear_r)], fill=bear_brown)
        draw.ellipse([(cx + ex - ear_r // 2, hd_cy - hd_r), (cx + ex + ear_r // 2, hd_cy - hd_r + ear_r)], fill=light_brown)
    # Muzzle
    mz_w, mz_h = int(hd_r * 0.5), int(hd_r * 0.35)
    draw.ellipse([(cx - mz_w, hd_cy + 2), (cx + mz_w, hd_cy + mz_h * 2)], fill=light_brown)
    # Eyes
    eye_r = max(4, int(hd_r * 0.15))
    for ex in [-int(hd_r * 0.38), int(hd_r * 0.38)]:
        draw.ellipse([(cx + ex - eye_r, hd_cy - eye_r - 4), (cx + ex + eye_r, hd_cy + eye_r - 4)], fill=(30, 41, 59))
        draw.ellipse([(cx + ex + 1, hd_cy - eye_r - 2), (cx + ex + 3, hd_cy - eye_r)], fill=(255, 255, 255))
    # Nose
    draw.ellipse([(cx - 5, hd_cy + 4), (cx + 5, hd_cy + 11)], fill=(30, 41, 59))
    # Smile
    draw.arc([(cx - 12, hd_cy + 8), (cx + 12, hd_cy + 24)], start=0, end=180, fill=(30, 41, 59), width=2)
    # Ears stub arms
    draw.ellipse([(cx - r - 8, cy + int(r * 0.1)), (cx - r + 8, cy + int(r * 0.6))], fill=bear_brown)
    draw.ellipse([(cx + r - 8, cy + int(r * 0.1)), (cx + r + 8, cy + int(r * 0.6))], fill=bear_brown)


def _draw_kawaii_monkey(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int) -> None:
    """Playful brown monkey with big ears and curly tail."""
    r = max(20, size)
    monkey_brown = (139, 90, 43)
    light_tan = (210, 160, 90)
    # Body
    draw.ellipse([(cx - int(r * 0.85), cy - int(r * 0.4)), (cx + int(r * 0.85), cy + int(r * 0.9))], fill=monkey_brown)
    # Belly
    draw.ellipse([(cx - int(r * 0.45), cy), (cx + int(r * 0.45), cy + int(r * 0.7))], fill=light_tan)
    # Head
    hd_r = int(r * 0.6)
    hd_cy = cy - int(r * 0.4) - hd_r + hd_r // 3
    draw.ellipse([(cx - hd_r, hd_cy - hd_r), (cx + hd_r, hd_cy + hd_r)], fill=monkey_brown)
    # Big round ears
    for ex in [-hd_r, hd_r]:
        ear_r = int(hd_r * 0.42)
        draw.ellipse([(cx + ex - ear_r, hd_cy - ear_r // 2), (cx + ex + ear_r, hd_cy + ear_r)], fill=monkey_brown)
        draw.ellipse([(cx + ex - ear_r // 2, hd_cy), (cx + ex + ear_r // 2, hd_cy + ear_r)], fill=light_tan)
    # Muzzle
    mz_r = int(hd_r * 0.42)
    mz_cy = hd_cy + int(hd_r * 0.2)
    draw.ellipse([(cx - mz_r, mz_cy - int(mz_r * 0.6)), (cx + mz_r, mz_cy + int(mz_r * 0.6))], fill=light_tan)
    # Nostrils
    for nx in [-5, 5]:
        draw.ellipse([(cx + nx - 3, mz_cy - 3), (cx + nx + 3, mz_cy + 3)], fill=(100, 60, 20))
    # Eyes
    eye_r = max(4, int(hd_r * 0.17))
    for ex in [-int(hd_r * 0.38), int(hd_r * 0.38)]:
        draw.ellipse([(cx + ex - eye_r, hd_cy - eye_r - 8), (cx + ex + eye_r, hd_cy + eye_r - 8)], fill=(30, 41, 59))
        draw.ellipse([(cx + ex + 1, hd_cy - eye_r - 6), (cx + ex + 3, hd_cy - eye_r - 4)], fill=(255, 255, 255))
    # Mouth
    draw.arc([(cx - 10, mz_cy), (cx + 10, mz_cy + 15)], start=0, end=180, fill=(80, 40, 10), width=2)
    # Curly tail arc
    draw.arc([(cx + int(r * 0.6), cy + int(r * 0.2)), (cx + int(r * 1.4), cy + int(r * 0.9))], start=270, end=90, fill=monkey_brown, width=8)
    # Arms
    draw.ellipse([(cx - r - 10, cy + int(r * 0.0)), (cx - r + 10, cy + int(r * 0.55))], fill=monkey_brown)
    draw.ellipse([(cx + r - 10, cy + int(r * 0.0)), (cx + r + 10, cy + int(r * 0.55))], fill=monkey_brown)


def _draw_kawaii_cat(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int) -> None:
    """Adorable orange tabby kitten with pointy ears and whiskers."""
    r = max(20, size)
    orange = (255, 140, 60)
    light_orange = (255, 200, 130)
    # Body
    draw.ellipse([(cx - r, cy - int(r * 0.5)), (cx + r, cy + r)], fill=orange)
    # Tummy
    draw.ellipse([(cx - int(r * 0.5), cy), (cx + int(r * 0.5), cy + int(r * 0.8))], fill=light_orange)
    # Head
    hd_r = int(r * 0.65)
    hd_cy = cy - int(r * 0.5) - hd_r + hd_r // 3
    draw.ellipse([(cx - hd_r, hd_cy - hd_r), (cx + hd_r, hd_cy + hd_r)], fill=orange)
    # Pointy ears (triangles)
    for sign in [-1, 1]:
        ex = sign * int(hd_r * 0.6)
        ear_pts = [
            (cx + ex, hd_cy - hd_r - int(hd_r * 0.6)),
            (cx + ex - int(hd_r * 0.3), hd_cy - hd_r + 5),
            (cx + ex + int(hd_r * 0.3), hd_cy - hd_r + 5),
        ]
        draw.polygon(ear_pts, fill=orange)
        inner_pts = [
            (cx + ex, hd_cy - hd_r - int(hd_r * 0.4)),
            (cx + ex - int(hd_r * 0.15), hd_cy - hd_r + 8),
            (cx + ex + int(hd_r * 0.15), hd_cy - hd_r + 8),
        ]
        draw.polygon(inner_pts, fill=(255, 182, 193))
    # Eyes (big green cat eyes)
    eye_r = max(5, int(hd_r * 0.18))
    for ex in [-int(hd_r * 0.38), int(hd_r * 0.38)]:
        draw.ellipse([(cx + ex - eye_r, hd_cy - eye_r - 2), (cx + ex + eye_r, hd_cy + eye_r - 2)], fill=(60, 200, 80))
        draw.ellipse([(cx + ex - eye_r // 2, hd_cy - eye_r - 2), (cx + ex + eye_r // 2, hd_cy + eye_r - 2)], fill=(30, 41, 59))
        draw.ellipse([(cx + ex + 1, hd_cy - eye_r), (cx + ex + 3, hd_cy - eye_r + 2)], fill=(255, 255, 255))
    # Nose & whiskers
    draw.polygon([(cx, hd_cy + 5), (cx - 5, hd_cy + 11), (cx + 5, hd_cy + 11)], fill=(255, 100, 120))
    for wy in [hd_cy + 8, hd_cy + 14]:
        draw.line([(cx - int(hd_r * 0.6), wy), (cx - 15, wy)], fill=(180, 180, 180), width=1)
        draw.line([(cx + 15, wy), (cx + int(hd_r * 0.6), wy)], fill=(180, 180, 180), width=1)
    # Smile
    draw.arc([(cx - 10, hd_cy + 10), (cx + 10, hd_cy + 24)], start=0, end=180, fill=(30, 41, 59), width=2)
    # Striped tail
    draw.arc([(cx + int(r * 0.5), cy + int(r * 0.3)), (cx + int(r * 1.3), cy + r)], start=270, end=70, fill=orange, width=10)


def _draw_kawaii_dog(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int) -> None:
    """Cheerful golden retriever puppy with floppy ears and wagging tail."""
    r = max(20, size)
    golden = (220, 170, 60)
    light = (245, 215, 130)
    # Body
    draw.ellipse([(cx - r, cy - int(r * 0.4)), (cx + r, cy + r)], fill=golden)
    # Tummy
    draw.ellipse([(cx - int(r * 0.5), cy + int(r * 0.1)), (cx + int(r * 0.5), cy + int(r * 0.85))], fill=light)
    # Head
    hd_r = int(r * 0.65)
    hd_cy = cy - int(r * 0.4) - hd_r + hd_r // 3
    draw.ellipse([(cx - hd_r, hd_cy - hd_r), (cx + hd_r, hd_cy + hd_r)], fill=golden)
    # Floppy ears
    for sign in [-1, 1]:
        ex = sign * int(hd_r * 0.75)
        draw.ellipse([(cx + ex - int(hd_r * 0.38), hd_cy - hd_r // 2), (cx + ex + int(hd_r * 0.38), hd_cy + hd_r)], fill=(180, 130, 40))
    # Muzzle
    mz_w = int(hd_r * 0.5)
    draw.ellipse([(cx - mz_w, hd_cy + 5), (cx + mz_w, hd_cy + int(hd_r * 0.6))], fill=light)
    # Nose
    draw.ellipse([(cx - 7, hd_cy + 8), (cx + 7, hd_cy + 17)], fill=(30, 41, 59))
    # Mouth / tongue
    draw.arc([(cx - 12, hd_cy + 14), (cx + 12, hd_cy + 28)], start=0, end=180, fill=(200, 60, 60), width=3)
    # Eyes
    eye_r = max(4, int(hd_r * 0.17))
    for ex in [-int(hd_r * 0.4), int(hd_r * 0.4)]:
        draw.ellipse([(cx + ex - eye_r, hd_cy - eye_r - 5), (cx + ex + eye_r, hd_cy + eye_r - 5)], fill=(30, 41, 59))
        draw.ellipse([(cx + ex + 1, hd_cy - eye_r - 3), (cx + ex + 3, hd_cy - eye_r - 1)], fill=(255, 255, 255))
    # Tail wagging up
    draw.arc([(cx + int(r * 0.5), cy - int(r * 0.4)), (cx + int(r * 1.4), cy + int(r * 0.4))], start=200, end=360, fill=golden, width=10)


def _draw_kawaii_panda(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int) -> None:
    """Round chubby panda with black eye patches."""
    r = max(20, size)
    white = (248, 248, 248)
    black = (30, 30, 30)
    # Body
    draw.ellipse([(cx - r, cy - int(r * 0.5)), (cx + r, cy + r)], fill=white)
    # Black legs stub
    for lx in [-int(r * 0.55), int(r * 0.55)]:
        draw.ellipse([(cx + lx - int(r * 0.3), cy + int(r * 0.6)), (cx + lx + int(r * 0.3), cy + int(r * 1.1))], fill=black)
    # Head
    hd_r = int(r * 0.65)
    hd_cy = cy - int(r * 0.5) - hd_r + hd_r // 3
    draw.ellipse([(cx - hd_r, hd_cy - hd_r), (cx + hd_r, hd_cy + hd_r)], fill=white)
    # Round ears
    for ex in [-int(hd_r * 0.75), int(hd_r * 0.75)]:
        ear_r = int(hd_r * 0.38)
        draw.ellipse([(cx + ex - ear_r, hd_cy - hd_r - ear_r // 2), (cx + ex + ear_r, hd_cy - hd_r + ear_r)], fill=black)
    # Eye patches
    for ex in [-int(hd_r * 0.42), int(hd_r * 0.42)]:
        draw.ellipse([(cx + ex - int(hd_r * 0.3), hd_cy - int(hd_r * 0.3)), (cx + ex + int(hd_r * 0.3), hd_cy + int(hd_r * 0.2))], fill=black)
        draw.ellipse([(cx + ex - int(hd_r * 0.14), hd_cy - int(hd_r * 0.18)), (cx + ex + int(hd_r * 0.14), hd_cy + int(hd_r * 0.08))], fill=white)
        # Iris
        draw.ellipse([(cx + ex - 3, hd_cy - 6), (cx + ex + 3, hd_cy)], fill=black)
    # Muzzle
    draw.ellipse([(cx - int(hd_r * 0.4), hd_cy + 4), (cx + int(hd_r * 0.4), hd_cy + int(hd_r * 0.5))], fill=(220, 220, 220))
    # Nose
    draw.ellipse([(cx - 5, hd_cy + 6), (cx + 5, hd_cy + 13)], fill=black)
    # Smile
    draw.arc([(cx - 10, hd_cy + 12), (cx + 10, hd_cy + 24)], start=0, end=180, fill=black, width=2)
    # Chubby arms
    draw.ellipse([(cx - r - 10, cy + int(r * 0.0)), (cx - r + 12, cy + int(r * 0.55))], fill=black)
    draw.ellipse([(cx + r - 12, cy + int(r * 0.0)), (cx + r + 10, cy + int(r * 0.55))], fill=black)


def _draw_kawaii_lion(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int) -> None:
    """Brave little lion cub with fluffy orange mane."""
    r = max(20, size)
    tan = (220, 170, 80)
    mane = (200, 110, 20)
    light = (245, 210, 130)
    # Mane (spiky circle)
    mane_r = int(r * 0.85)
    hd_cy = cy - int(r * 0.4) - int(r * 0.65) + int(r * 0.65) // 3
    for i in range(12):
        angle = i * (2 * math.pi / 12)
        mx = cx + int((mane_r + 10) * math.cos(angle))
        my = hd_cy + int((mane_r + 10) * math.sin(angle))
        draw.ellipse([(mx - 14, my - 14), (mx + 14, my + 14)], fill=mane)
    # Mane ring
    draw.ellipse([(cx - mane_r, hd_cy - mane_r), (cx + mane_r, hd_cy + mane_r)], fill=mane)
    # Body
    draw.ellipse([(cx - r, cy - int(r * 0.4)), (cx + r, cy + r)], fill=tan)
    # Tummy
    draw.ellipse([(cx - int(r * 0.5), cy + int(r * 0.1)), (cx + int(r * 0.5), cy + int(r * 0.8))], fill=light)
    # Head
    hd_r = int(r * 0.65)
    draw.ellipse([(cx - hd_r, hd_cy - hd_r), (cx + hd_r, hd_cy + hd_r)], fill=tan)
    # Muzzle
    draw.ellipse([(cx - int(hd_r * 0.5), hd_cy + 2), (cx + int(hd_r * 0.5), hd_cy + int(hd_r * 0.55))], fill=light)
    # Nose
    draw.polygon([(cx, hd_cy + 5), (cx - 6, hd_cy + 13), (cx + 6, hd_cy + 13)], fill=(220, 60, 60))
    # Mouth
    draw.line([(cx, hd_cy + 13), (cx - 10, hd_cy + 20)], fill=(30, 41, 59), width=2)
    draw.line([(cx, hd_cy + 13), (cx + 10, hd_cy + 20)], fill=(30, 41, 59), width=2)
    # Eyes
    eye_r = max(5, int(hd_r * 0.18))
    for ex in [-int(hd_r * 0.38), int(hd_r * 0.38)]:
        draw.ellipse([(cx + ex - eye_r, hd_cy - eye_r - 5), (cx + ex + eye_r, hd_cy + eye_r - 5)], fill=(200, 140, 30))
        draw.ellipse([(cx + ex - eye_r // 2, hd_cy - eye_r - 5), (cx + ex + eye_r // 2, hd_cy + eye_r - 5)], fill=(30, 41, 59))
        draw.ellipse([(cx + ex + 1, hd_cy - eye_r - 3), (cx + ex + 3, hd_cy - eye_r - 1)], fill=(255, 255, 255))


def _draw_kawaii_elephant(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int) -> None:
    """Gentle grey elephant with big ears and curly trunk."""
    r = max(20, size)
    grey = (150, 160, 180)
    light_grey = (200, 210, 225)
    # Body
    draw.ellipse([(cx - r, cy - int(r * 0.5)), (cx + r, cy + r)], fill=grey)
    # Head
    hd_r = int(r * 0.6)
    hd_cy = cy - int(r * 0.5) - hd_r + hd_r // 3
    draw.ellipse([(cx - hd_r, hd_cy - hd_r), (cx + hd_r, hd_cy + hd_r)], fill=grey)
    # Big floppy ears
    for sign in [-1, 1]:
        ex = sign * int(hd_r * 0.9)
        draw.ellipse([(cx + ex - int(hd_r * 0.6), hd_cy - hd_r // 2), (cx + ex + int(hd_r * 0.6), hd_cy + hd_r // 2)], fill=grey)
        draw.ellipse([(cx + ex - int(hd_r * 0.4), hd_cy - hd_r // 4), (cx + ex + int(hd_r * 0.4), hd_cy + hd_r // 4)], fill=light_grey)
    # Trunk (curling down then right)
    trunk_pts = [
        (cx, hd_cy + hd_r),
        (cx - int(hd_r * 0.2), hd_cy + hd_r + int(hd_r * 0.5)),
        (cx - int(hd_r * 0.3), hd_cy + hd_r + int(hd_r * 1.0)),
        (cx + int(hd_r * 0.2), hd_cy + hd_r + int(hd_r * 1.1)),
    ]
    for i in range(len(trunk_pts) - 1):
        draw.line([trunk_pts[i], trunk_pts[i + 1]], fill=grey, width=14)
    # Eyes
    eye_r = max(4, int(hd_r * 0.15))
    for ex in [-int(hd_r * 0.38), int(hd_r * 0.38)]:
        draw.ellipse([(cx + ex - eye_r, hd_cy - eye_r - 5), (cx + ex + eye_r, hd_cy + eye_r - 5)], fill=(30, 41, 59))
        draw.ellipse([(cx + ex + 1, hd_cy - eye_r - 3), (cx + ex + 3, hd_cy - eye_r - 1)], fill=(255, 255, 255))
    # Tusks
    draw.arc([(cx - int(hd_r * 0.5), hd_cy + hd_r // 2), (cx, hd_cy + hd_r)], start=180, end=90, fill=(240, 230, 180), width=5)
    # Legs
    for lx in [-int(r * 0.55), -int(r * 0.15), int(r * 0.15), int(r * 0.55)]:
        draw.ellipse([(cx + lx - int(r * 0.22), cy + int(r * 0.6)), (cx + lx + int(r * 0.22), cy + int(r * 1.1))], fill=grey)


def _draw_kawaii_party(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int, t: float = 0.0) -> None:
    """Celebration scene: colorful confetti, stars, and party hat."""
    r = max(20, size)
    colors = [(255, 80, 80), (80, 200, 255), (255, 220, 50), (80, 220, 100), (200, 100, 255)]
    # Confetti bursts (rotating)
    for i in range(14):
        angle = t * 2.5 + i * (2 * math.pi / 14)
        dist = r * (0.5 + 0.5 * (i % 3) / 2)
        px = cx + int(dist * math.cos(angle))
        py = cy + int(dist * math.sin(angle))
        cr = 7 + (i % 4) * 3
        draw.ellipse([(px - cr, py - cr), (px + cr, py + cr)], fill=colors[i % len(colors)])
    # Star burst center
    for i in range(8):
        angle = t * 1.5 + i * math.pi / 4
        x1 = cx + int((r * 0.15) * math.cos(angle))
        y1 = cy + int((r * 0.15) * math.sin(angle))
        x2 = cx + int((r * 0.5) * math.cos(angle))
        y2 = cy + int((r * 0.5) * math.sin(angle))
        draw.line([(x1, y1), (x2, y2)], fill=(255, 230, 50), width=5)
    # Center star
    draw.ellipse([(cx - 25, cy - 25), (cx + 25, cy + 25)], fill=(255, 220, 50))
    draw.text((cx, cy), "🎉", font=_get_font(int(r * 0.6)), fill=(255, 255, 255), anchor="mm")


def _draw_kawaii_star(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int, t: float = 0.0) -> None:
    """Generic friendly star character for unknown topics."""
    r = max(20, size)
    # Outer glow rings
    for gr in range(3, 0, -1):
        alpha_r = r + gr * 10
        draw.ellipse([(cx - alpha_r, cy - alpha_r), (cx + alpha_r, cy + alpha_r)], fill=(255, 240, 100, 60))
    # Star body
    draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], fill=(255, 220, 50))
    # Rotating star spikes
    for i in range(8):
        angle = t * 2.0 + i * math.pi / 4
        x1 = cx + int(r * math.cos(angle))
        y1 = cy + int(r * math.sin(angle))
        x2 = cx + int((r + 22) * math.cos(angle))
        y2 = cy + int((r + 22) * math.sin(angle))
        draw.line([(x1, y1), (x2, y2)], fill=(255, 180, 0), width=6)
    # Face
    eye_r = max(4, int(r * 0.14))
    for ex in [-int(r * 0.3), int(r * 0.3)]:
        draw.ellipse([(cx + ex - eye_r, cy - eye_r - 5), (cx + ex + eye_r, cy + eye_r - 5)], fill=(30, 41, 59))
    draw.arc([(cx - int(r * 0.3), cy + 2), (cx + int(r * 0.3), cy + int(r * 0.4))], start=0, end=180, fill=(30, 41, 59), width=3)


# ---------------------------------------------------------------------------
# Character type detector
# ---------------------------------------------------------------------------

def _detect_character_type(card: KidsCard) -> str:
    """Infer the character type from image_prompt, emoji, and title keywords.
    
    Priority order: emoji is checked first (most reliable signal), then
    celebration keywords (before animals so '🎉 puppy dog party' → party),
    then individual animal keywords.
    """
    emoji = card.emoji.strip()
    combined = f"{card.image_prompt} {card.title}".lower()
    all_text = f"{emoji} {combined}"

    # Emoji-exact matches (highest priority — unambiguous)
    if "🐰" in emoji or "🐇" in emoji:
        return "rabbit"
    if "🐻" in emoji:
        return "bear"
    if "🐵" in emoji or "🐒" in emoji:
        return "monkey"
    if "🐱" in emoji or "🐈" in emoji:
        return "cat"
    if "🐶" in emoji or "🐕" in emoji:
        return "dog"
    if "🐼" in emoji:
        return "panda"
    if "🦁" in emoji:
        return "lion"
    if "🐘" in emoji:
        return "elephant"
    if "🎉" in emoji or "🎊" in emoji:
        return "party"

    # Text-based fallback (combined image_prompt + title)
    if any(k in combined for k in ("party", "tiệc", "celebration", "hooray", "hoan hô")):
        return "party"
    if any(k in combined for k in ("rabbit", "bunny", "thỏ")):
        return "rabbit"
    if any(k in combined for k in ("bear", "gấu", "teddy")):
        return "bear"
    if any(k in combined for k in ("monkey", "khỉ", "ape")):
        return "monkey"
    if any(k in combined for k in ("cat", "mèo", "kitten")):
        return "cat"
    if any(k in combined for k in ("dog", "puppy", "cún", "chó")):
        return "dog"
    if any(k in combined for k in ("panda",)):
        return "panda"
    if any(k in combined for k in ("lion", "sư tử")):
        return "lion"
    if any(k in combined for k in ("elephant", "voi")):
        return "elephant"
    return "star"


def _draw_character(draw: ImageDraw.ImageDraw, char_type: str, cx: int, cy: int, size: int, t: float = 0.0) -> None:
    """Dispatch to the right kawaii animal/character drawing function."""
    if char_type == "rabbit":
        _draw_kawaii_rabbit(draw, cx, cy, size)
    elif char_type == "bear":
        _draw_kawaii_bear(draw, cx, cy, size)
    elif char_type == "monkey":
        _draw_kawaii_monkey(draw, cx, cy, size)
    elif char_type == "cat":
        _draw_kawaii_cat(draw, cx, cy, size)
    elif char_type == "dog":
        _draw_kawaii_dog(draw, cx, cy, size)
    elif char_type == "panda":
        _draw_kawaii_panda(draw, cx, cy, size)
    elif char_type == "lion":
        _draw_kawaii_lion(draw, cx, cy, size)
    elif char_type == "elephant":
        _draw_kawaii_elephant(draw, cx, cy, size)
    elif char_type == "party":
        _draw_kawaii_party(draw, cx, cy, size, t=t)
    else:
        _draw_kawaii_star(draw, cx, cy, size, t=t)


# ---------------------------------------------------------------------------
# Main frame renderer
# ---------------------------------------------------------------------------

def render_animated_kids_frame(
    t: float,
    card: KidsCard,
    duration: float,
    width: int = 540,
    height: int = 960,
    char_type: str = "star",
) -> np.ndarray:
    """Renders a single frame of the vibrant, lively cartoon animation at time t."""
    theme_rgb = _hex_to_rgb(card.theme_color)

    # 1. Cheerful sky background
    img = Image.new("RGBA", (width, height), (224, 242, 254, 255))
    draw = ImageDraw.Draw(img)

    # 2. Smiling sun with rotating rays (Top right)
    sun_x, sun_y, sun_r = int(width * 0.85), int(height * 0.12), int(width * 0.08)
    draw.ellipse([(sun_x - sun_r, sun_y - sun_r), (sun_x + sun_r, sun_y + sun_r)], fill=(254, 240, 138))
    draw.ellipse([(sun_x - sun_r + 4, sun_y - sun_r + 4), (sun_x + sun_r - 4, sun_y + sun_r - 4)], fill=(250, 204, 21))
    # Rotating rays
    num_rays = 8
    ray_rot = t * 1.6
    for i in range(num_rays):
        angle = ray_rot + i * (2 * math.pi / num_rays)
        x1 = sun_x + int((sun_r + 6) * math.cos(angle))
        y1 = sun_y + int((sun_r + 6) * math.sin(angle))
        x2 = sun_x + int((sun_r + 18) * math.cos(angle))
        y2 = sun_y + int((sun_r + 18) * math.sin(angle))
        draw.line([(x1, y1), (x2, y2)], fill=(245, 158, 11), width=4)
    # Sun face
    draw.ellipse([(sun_x - 5, sun_y - 5), (sun_x + 5, sun_y + 5)], fill=(30, 41, 59))
    draw.arc([(sun_x - sun_r // 2, sun_y), (sun_x + sun_r // 2, sun_y + sun_r // 2)], start=0, end=180, fill=(30, 41, 59), width=2)

    # 3. Animated drifting fluffy clouds
    cloud_layers = [
        (40, int(height * 0.07), 45, 22),
        (260, int(height * 0.14), 55, 16),
        (160, int(height * 0.20), 40, 28),
    ]
    for base_x, c_y, c_size, speed in cloud_layers:
        cur_x = int((base_x + speed * t) % (width + 140)) - 70
        draw.ellipse([(cur_x, c_y), (cur_x + c_size * 2, c_y + c_size)], fill=(255, 255, 255, 235))
        draw.ellipse([(cur_x + int(c_size * 0.4), c_y - int(c_size * 0.35)), (cur_x + int(c_size * 1.6), c_y + int(c_size * 0.75))], fill=(255, 255, 255, 250))

    # 4. Multi-layer lush rolling hills
    draw.ellipse([(-120, int(height * 0.54)), (width + 120, int(height * 1.05))], fill=(134, 239, 172))
    draw.ellipse([(-60, int(height * 0.62)), (width + 160, int(height * 1.15))], fill=(74, 222, 128))

    # Little flowers on hill
    for fx, fy, fcolor in [
        (int(width * 0.12), int(height * 0.68), (244, 114, 182)),
        (int(width * 0.28), int(height * 0.72), (250, 204, 21)),
        (int(width * 0.78), int(height * 0.67), (244, 114, 182)),
        (int(width * 0.88), int(height * 0.71), (255, 255, 255)),
    ]:
        draw.ellipse([(fx - 6, fy - 6), (fx + 6, fy + 6)], fill=fcolor)
        draw.ellipse([(fx - 2, fy - 2), (fx + 2, fy + 2)], fill=(255, 255, 255))

    # 5. Floating Sparkles / Bubbles
    for p_idx in range(6):
        px = int(width * (0.15 + 0.14 * p_idx) + 12 * math.sin(t * 3.0 + p_idx))
        py = int(height * 0.70 - ((t * 45 + p_idx * 60) % int(height * 0.45)))
        pr = 5 + (p_idx % 4)
        draw.ellipse([(px - pr, py - pr), (px + pr, py + pr)], fill=(255, 255, 255, 180))
        draw.ellipse([(px - pr, py - pr), (px + pr, py + pr)], outline=theme_rgb, width=2)

    # 6. Animated Cartoon Character — PROCEDURAL (always relevant to card topic)
    bounce_freq = 2.2
    hop = abs(math.sin(t * math.pi * bounce_freq))
    char_base_y = int(height * 0.46)
    char_y = char_base_y - int(hop * 28)

    # Contact shadow on ground
    shadow_w = int(width * 0.34 * (1.0 - hop * 0.25))
    shadow_h = int(height * 0.022 * (1.0 - hop * 0.25))
    shadow_cx = width // 2
    shadow_cy = char_base_y + int(height * 0.08)
    draw.ellipse(
        [(shadow_cx - shadow_w // 2, shadow_cy - shadow_h // 2),
         (shadow_cx + shadow_w // 2, shadow_cy + shadow_h // 2)],
        fill=(34, 197, 94, 160),
    )

    # Squash/stretch: modify temp drawing surface
    char_size = int(width * 0.16)
    squash = 0.05 * math.sin(t * math.pi * bounce_freq * 2)
    # Draw character directly (PIL doesn't natively rotate/scale subregion, so we draw at char_y)
    _draw_character(draw, char_type, width // 2, char_y, char_size, t=t)

    # 7. Animated Bouncing Counting Apples / Items (if applicable)
    full_info = f"{card.title} {card.subtitle}".lower()
    is_apple_theme = any(k in full_info for k in ("táo", "apple", "quả"))
    count_match = re.search(r"\b([1-5])\b", card.title)
    count = int(count_match.group(1)) if count_match else (1 if is_apple_theme else 0)

    if count > 0:
        apple_y_base = int(height * 0.59)
        apple_size = int(width * 0.16)
        positions = []
        if count == 1:
            positions = [(int(width * 0.78), apple_y_base, 0.0)]
        elif count == 2:
            positions = [
                (int(width * 0.18), apple_y_base, 0.0),
                (int(width * 0.82), apple_y_base, 0.4),
            ]
        elif count == 3:
            positions = [
                (int(width * 0.16), apple_y_base - 20, 0.0),
                (int(width * 0.84), apple_y_base - 20, 0.3),
                (int(width * 0.50), apple_y_base + 35, 0.6),
            ]
        else:
            positions = [
                (int(width * 0.15), apple_y_base - 30, 0.0),
                (int(width * 0.85), apple_y_base - 30, 0.2),
                (int(width * 0.28), apple_y_base + 30, 0.4),
                (int(width * 0.72), apple_y_base + 30, 0.6),
            ]

        for ax, ay, phase in positions:
            a_bob = abs(math.sin((t + phase) * math.pi * 2.8)) * 18
            cur_ay = int(ay - a_bob)
            pop_scale = min(1.0, max(0.2, (t - phase * 0.5) * 3.0)) if t > phase * 0.5 else 0.0
            if pop_scale > 0.1:
                cur_size = int(apple_size * pop_scale)
                _draw_cartoon_apple_small(draw, ax, cur_ay, cur_size)

    # 8. Top Header Badge (Short Title / Theme)
    top_badge_y = int(height * 0.045)
    title_font, t_bbox = _fit_text(
        draw,
        card.title,
        max_width=width - 80,
        initial_size=int(height * 0.030),
        min_size=20,
        bold=True,
    )
    t_w = t_bbox[2] - t_bbox[0]
    badge_w = t_w + 50
    badge_h = int(height * 0.050)
    badge_x = (width - badge_w) // 2
    draw.rounded_rectangle(
        [(badge_x, top_badge_y), (badge_x + badge_w, top_badge_y + badge_h)],
        radius=badge_h // 2,
        fill=(255, 255, 255, 240),
        outline=theme_rgb,
        width=3,
    )
    draw.text((width // 2, top_badge_y + badge_h // 2), card.title, font=title_font, fill=(15, 23, 42), anchor="mm")

    # 9. Synchronized Subtitles
    sub_box_y = int(height * 0.74)
    sub_box_h = int(height * 0.17)
    sub_margin = int(width * 0.05)
    sub_box = [(sub_margin, sub_box_y), (width - sub_margin, sub_box_y + sub_box_h)]

    draw.rounded_rectangle(
        sub_box,
        radius=24,
        fill=(15, 23, 42, 230),
        outline=(250, 204, 21),
        width=3,
    )

    sub_tag_font = _get_font(int(height * 0.018), bold=True)
    draw.text((sub_margin + 24, sub_box_y + 18), "🌟 PHỤ ĐỀ / SUBTITLE", font=sub_tag_font, fill=(250, 204, 21))

    sub_font = _get_font(int(height * 0.024), bold=True)
    sub_lines = textwrap.wrap(card.spoken_text, width=28)
    sub_text_start_y = sub_box_y + int(height * 0.054)
    for l_idx, line in enumerate(sub_lines[:3]):
        draw.text(
            (width // 2, sub_text_start_y + l_idx * int(height * 0.034)),
            line,
            font=sub_font,
            fill=(255, 255, 255),
            anchor="mm",
        )

    # 10. Bottom Footer Accent
    bot_y = int(height * 0.95)
    bot_font = _get_font(int(height * 0.018), bold=True)
    draw.text(
        (width // 2, bot_y),
        "✨ Vừa Học Vừa Chơi • Bé Càng Thông Minh ✨",
        font=bot_font,
        fill=(15, 23, 42),
        anchor="mm",
    )

    return np.array(img.convert("RGB"))


def make_kids_animated_scene_clip(
    card: KidsCard,
    character_img=None,  # kept for backward compat — ignored, we use procedural art
    duration: float = 4.0,
    width: int = 540,
    height: int = 960,
) -> VideoClip:
    """Creates a smooth, procedurally animated VideoClip for a single educational scene.
    
    The character_img parameter is kept for backward compatibility but is now IGNORED.
    All characters are drawn procedurally using PIL based on the card's image_prompt/emoji.
    This guarantees 100% visual relevance — rabbit card → rabbit, bear card → bear, etc.
    """
    char_type = _detect_character_type(card)

    def make_frame(t: float) -> np.ndarray:
        return render_animated_kids_frame(
            t=t,
            card=card,
            duration=duration,
            width=width,
            height=height,
            char_type=char_type,
        )

    return VideoClip(make_frame, duration=duration)
