"""Procedural 2D/2.5D Cartoon Animation Engine for Kids Videos.
0đ cost, 100% offline, smooth dynamic motion, high-res 3D cartoon characters.

Features:
- 3D Pixar/Disney style cartoon characters (Microsoft Fluent 3D, MIT License, bundled offline)
- 5 Diverse, breathtaking background environments (Sunny Meadow, Sunset Valley, Magical Night, Ocean Paradise, Candy Carnival)
- Rhythmic character hopping, squash & stretch, playful tilting, elastic pop-in entrance
- Bouncing 3D counting apples / props with sequential pop-in effects
- Smooth animated UI: drop-down title badge, slide-up subtitle pill showing EXACT spoken voiceover
- Fully offline, 0 network calls during generation
"""

from __future__ import annotations

import functools
import math
import re
import textwrap
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy import VideoClip

from core.config import settings
from video.kids_education.canvas import _get_font, _fit_text, sanitize_emoji
from video.kids_education.presets import KidsCard

ASSETS_DIR = settings.project_root / "assets" / "kids_characters"
_ASSET_CACHE: dict[str, Optional[Image.Image]] = {}


def _hex_to_rgb(hex_code: str) -> tuple[int, int, int]:
    hex_code = hex_code.lstrip("#")
    if len(hex_code) == 3:
        hex_code = "".join(c * 2 for c in hex_code)
    try:
        return tuple(int(hex_code[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:
        return (255, 107, 107)


@functools.lru_cache(maxsize=32)
def get_character_asset(char_type: str) -> Optional[Image.Image]:
    """Loads and caches a 3D character asset from assets/kids_characters."""
    if char_type not in _ASSET_CACHE:
        path = ASSETS_DIR / f"{char_type}.png"
        if path.is_file():
            try:
                img = Image.open(path).convert("RGBA")
                _ASSET_CACHE[char_type] = img
            except Exception:
                _ASSET_CACHE[char_type] = None
        else:
            _ASSET_CACHE[char_type] = None
    return _ASSET_CACHE[char_type]


def _detect_character_type(card: KidsCard) -> str:
    """Infer the character type from emoji and keywords in image_prompt/title.
    
    Priority order:
    1. Exact emoji symbol
    2. Specific title/prompt keywords
    3. Fallback to 'star'
    """
    emoji = card.emoji.strip()
    combined = f"{card.image_prompt} {card.title} {card.subtitle}".lower()

    # 1. Emoji checks (highest precision)
    if any(e in emoji for e in ("🐰", "🐇")):
        return "rabbit"
    if "🐻" in emoji:
        return "bear"
    if any(e in emoji for e in ("🐵", "🐒")):
        return "monkey"
    if any(e in emoji for e in ("🐱", "🐈")):
        return "cat"
    if any(e in emoji for e in ("🐶", "🐕")):
        return "dog"
    if "🐼" in emoji:
        return "panda"
    if "🦁" in emoji:
        return "lion"
    if "🐘" in emoji:
        return "elephant"
    if "🍎" in emoji:
        return "apple"
    if any(e in emoji for e in ("🎉", "🎊")):
        return "party"
    if "⭐" in emoji or "🌟" in emoji:
        return "star"
    if "☀️" in emoji or "🌞" in emoji:
        return "sun"
    if "🐸" in emoji:
        return "frog"
    if "🚀" in emoji:
        return "rocket"
    if any(e in emoji for e in ("🚗", "🚙", "🚘")):
        return "car"
    if any(e in emoji for e in ("🦖", "🦕")):
        return "dinosaur"
    if "🎈" in emoji:
        return "balloon"
    if "🌈" in emoji:
        return "rainbow"
    if any(e in emoji for e in ("📚", "📖")):
        return "books"
    if "👑" in emoji:
        return "crown"
    if "🍌" in emoji:
        return "banana"

    # 2. Text keyword matches
    if any(k in combined for k in ("party", "tiệc", "celebration", "liên hoan", "hooray")):
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
    if any(k in combined for k in ("panda", "trúc")):
        return "panda"
    if any(k in combined for k in ("lion", "sư tử")):
        return "lion"
    if any(k in combined for k in ("elephant", "voi")):
        return "elephant"
    if any(k in combined for k in ("khủng long", "dinosaur", "t-rex")):
        return "dinosaur"
    if any(k in combined for k in ("tên lửa", "rocket", "vũ trụ", "space")):
        return "rocket"
    if any(k in combined for k in ("xe", "car", "ô tô")):
        return "car"
    if any(k in combined for k in ("ếch", "frog")):
        return "frog"
    if any(k in combined for k in ("bóng bay", "balloon")):
        return "balloon"
    if any(k in combined for k in ("cầu vồng", "rainbow")):
        return "rainbow"
    if any(k in combined for k in ("sách", "book", "học")):
        return "books"
    if any(k in combined for k in ("chuối", "banana")):
        return "banana"
    if any(k in combined for k in ("táo", "apple")):
        return "apple"

    return "star"


def _detect_background_theme(card: KidsCard, scene_index: int = 0) -> str:
    """Selects one of the 5 diverse environment themes based on content or scene rotation."""
    combined = f"{card.title} {card.subtitle} {card.image_prompt} {card.emoji}".lower()

    # Content-based overrides
    if any(k in combined for k in ("đêm", "night", "sao", "trăng", "moon", "space", "vũ trụ", "rocket", "tên lửa")):
        return "magical_night"
    if any(k in combined for k in ("biển", "ocean", "sea", "cá", "fish", "nước", "water")):
        return "ocean_paradise"
    if any(k in combined for k in ("tiệc", "party", "kẹo", "candy", "cầu vồng", "rainbow", "balloon", "bóng bay")):
        return "candy_carnival"

    # Default rotation across the 5 scenic environments
    themes = ["sunny_meadow", "sunset_valley", "ocean_paradise", "candy_carnival", "magical_night"]
    return themes[scene_index % len(themes)]


# ---------------------------------------------------------------------------
# Background Environment Renderers
# ---------------------------------------------------------------------------

def _render_gradient(width: int, height: int, c_top: tuple, c_bot: tuple) -> Image.Image:
    """Generates a high-speed vertical color gradient."""
    top_arr = np.array(c_top, dtype=np.float32)
    bot_arr = np.array(c_bot, dtype=np.float32)
    y = np.linspace(0, 1, height, dtype=np.float32)[:, None, None]
    grad = (top_arr * (1.0 - y) + bot_arr * y).astype(np.uint8)
    grad = np.repeat(grad, width, axis=1)
    return Image.fromarray(grad).convert("RGBA")


def _render_sunny_meadow(img: Image.Image, draw: ImageDraw.ImageDraw, width: int, height: int, t: float) -> None:
    """Vibrant sunny meadow with spinning sun, fluffy drifting clouds, rolling hills & flowers."""
    # 1. 3D Sun or animated glowing sun
    sun_x, sun_y, sun_r = int(width * 0.84), int(height * 0.12), int(width * 0.08)
    sun_asset = get_character_asset("sun")
    if sun_asset:
        s_sz = int(width * 0.22)
        s_rot = sun_asset.rotate(t * 15.0, expand=True, resample=Image.Resampling.BILINEAR)
        img.paste(s_rot, (sun_x - s_rot.width // 2, sun_y - s_rot.height // 2), mask=s_rot)
    else:
        draw.ellipse([(sun_x - sun_r, sun_y - sun_r), (sun_x + sun_r, sun_y + sun_r)], fill=(254, 240, 138))
        draw.ellipse([(sun_x - sun_r + 4, sun_y - sun_r + 4), (sun_x + sun_r - 4, sun_y + sun_r - 4)], fill=(250, 204, 21))

    # Rotating sun rays
    num_rays = 8
    ray_rot = t * 1.6
    for i in range(num_rays):
        angle = ray_rot + i * (2 * math.pi / num_rays)
        x1 = sun_x + int((sun_r + 8) * math.cos(angle))
        y1 = sun_y + int((sun_r + 8) * math.sin(angle))
        x2 = sun_x + int((sun_r + 20) * math.cos(angle))
        y2 = sun_y + int((sun_r + 20) * math.sin(angle))
        draw.line([(x1, y1), (x2, y2)], fill=(245, 158, 11), width=4)

    # 2. Multi-layer drifting clouds (parallax speeds)
    clouds = [
        (40, int(height * 0.07), 48, 20),
        (260, int(height * 0.13), 56, 14),
        (160, int(height * 0.19), 42, 26),
    ]
    for base_x, c_y, c_size, speed in clouds:
        cur_x = int((base_x + speed * t) % (width + 160)) - 80
        draw.ellipse([(cur_x, c_y), (cur_x + c_size * 2, c_y + c_size)], fill=(255, 255, 255, 230))
        draw.ellipse([(cur_x + int(c_size * 0.4), c_y - int(c_size * 0.35)), (cur_x + int(c_size * 1.6), c_y + int(c_size * 0.75))], fill=(255, 255, 255, 245))

    # 3. Two lush rolling hills
    draw.ellipse([(-120, int(height * 0.54)), (width + 120, int(height * 1.05))], fill=(134, 239, 172))
    draw.ellipse([(-60, int(height * 0.62)), (width + 160, int(height * 1.15))], fill=(74, 222, 128))

    # Little flowers on hill
    for fx, fy, fcolor in [
        (int(width * 0.12), int(height * 0.68), (244, 114, 182)),
        (int(width * 0.28), int(height * 0.72), (250, 204, 21)),
        (int(width * 0.76), int(height * 0.67), (244, 114, 182)),
        (int(width * 0.88), int(height * 0.71), (255, 255, 255)),
    ]:
        draw.ellipse([(fx - 7, fy - 7), (fx + 7, fy + 7)], fill=fcolor)
        draw.ellipse([(fx - 2, fy - 2), (fx + 2, fy + 2)], fill=(255, 255, 255))


def _render_sunset_valley(img: Image.Image, draw: ImageDraw.ImageDraw, width: int, height: int, t: float) -> None:
    """Atmospheric golden-hour sunset with warm hues, glowing evening sun, purple hills and floating fireflies."""
    # Big setting sun with glowing halo
    sun_x, sun_y = int(width * 0.50), int(height * 0.30)
    for gr in [120, 90, 65]:
        draw.ellipse([(sun_x - gr, sun_y - gr), (sun_x + gr, sun_y + gr)], fill=(254, 215, 170, 70))
    draw.ellipse([(sun_x - 45, sun_y - 45), (sun_x + 45, sun_y + 45)], fill=(255, 247, 237))

    # Sunset clouds (pink/apricot)
    clouds = [
        (60, int(height * 0.14), 60, 16),
        (280, int(height * 0.22), 70, 12),
    ]
    for base_x, c_y, c_size, speed in clouds:
        cur_x = int((base_x + speed * t) % (width + 160)) - 80
        draw.ellipse([(cur_x, c_y), (cur_x + c_size * 2, c_y + c_size)], fill=(254, 205, 211, 200))
        draw.ellipse([(cur_x + int(c_size * 0.4), c_y - int(c_size * 0.3)), (cur_x + int(c_size * 1.6), c_y + int(c_size * 0.7))], fill=(253, 164, 175, 220))

    # Lavender & plum hills
    draw.ellipse([(-100, int(height * 0.55)), (width + 140, int(height * 1.05))], fill=(168, 85, 247))
    draw.ellipse([(-50, int(height * 0.63)), (width + 120, int(height * 1.15))], fill=(147, 51, 234))

    # Floating golden fireflies/sparks
    for idx in range(8):
        fx = int(width * (0.12 + 0.11 * idx) + 15 * math.sin(t * 3.0 + idx))
        fy = int(height * 0.70 - ((t * 35 + idx * 55) % int(height * 0.42)))
        fr = 3 + (idx % 3)
        draw.ellipse([(fx - fr - 2, fy - fr - 2), (fx + fr + 2, fy + fr + 2)], fill=(253, 224, 71, 100))
        draw.ellipse([(fx - fr, fy - fr), (fx + fr, fy + fr)], fill=(255, 255, 255))


def _render_magical_night(img: Image.Image, draw: ImageDraw.ImageDraw, width: int, height: int, t: float) -> None:
    """Dreamy midnight sky with crescent moon, twinkling stars, stardust and mystic hills."""
    # Twinkling stars (18 stars blinking with phase shift)
    star_positions = [
        (0.10, 0.08), (0.22, 0.15), (0.35, 0.06), (0.48, 0.18), (0.62, 0.10),
        (0.75, 0.16), (0.88, 0.07), (0.15, 0.24), (0.40, 0.28), (0.70, 0.26),
        (0.85, 0.22), (0.30, 0.36), (0.55, 0.34), (0.80, 0.38), (0.18, 0.44),
    ]
    for s_idx, (rx, ry) in enumerate(star_positions):
        sx = int(width * rx)
        sy = int(height * ry)
        # Twinkle brightness
        twinkle = 0.5 + 0.5 * math.sin(t * 4.0 + s_idx * 1.3)
        s_r = 3 + int(twinkle * 4)
        alpha = int(140 + twinkle * 115)
        # 4-point star cross
        draw.line([(sx - s_r * 2, sy), (sx + s_r * 2, sy)], fill=(255, 255, 255, alpha), width=2)
        draw.line([(sx, sy - s_r * 2), (sx, sy + s_r * 2)], fill=(255, 255, 255, alpha), width=2)
        draw.ellipse([(sx - 2, sy - 2), (sx + 2, sy + 2)], fill=(255, 255, 255, 255))

    # Glowing Crescent Moon
    moon_x, moon_y = int(width * 0.82), int(height * 0.12)
    draw.ellipse([(moon_x - 36, moon_y - 36), (moon_x + 36, moon_y + 36)], fill=(254, 240, 138, 240))
    # Crescent cutout
    draw.ellipse([(moon_x - 24, moon_y - 42), (moon_x + 40, moon_y + 30)], fill=(30, 27, 75))

    # Mystic dark navy / teal hills
    draw.ellipse([(-100, int(height * 0.56)), (width + 140, int(height * 1.05))], fill=(30, 41, 59))
    draw.ellipse([(-50, int(height * 0.63)), (width + 120, int(height * 1.15))], fill=(51, 65, 85))


def _render_ocean_paradise(img: Image.Image, draw: ImageDraw.ImageDraw, width: int, height: int, t: float) -> None:
    """Tropical ocean paradise with gentle waving horizons, golden dunes & ascending bubbles."""
    # Horizon wave layers
    wave_base_y = int(height * 0.52)
    wave_pts = []
    for x in range(0, width + 20, 20):
        y_offset = int(10 * math.sin(x * 0.03 + t * 2.8))
        wave_pts.append((x, wave_base_y + y_offset))
    wave_pts.extend([(width, height), (0, height)])
    draw.polygon(wave_pts, fill=(14, 165, 233, 210))

    # Golden sandy bottom dunes
    draw.ellipse([(-80, int(height * 0.62)), (width + 120, int(height * 1.15))], fill=(253, 224, 71))
    draw.ellipse([(-40, int(height * 0.68)), (width + 80, int(height * 1.18))], fill=(250, 204, 21))

    # Ascending ocean bubbles
    for idx in range(8):
        bx = int(width * (0.10 + 0.12 * idx) + 12 * math.sin(t * 2.5 + idx * 2))
        by = int(height * 0.72 - ((t * 45 + idx * 60) % int(height * 0.45)))
        br = 6 + (idx % 4) * 2
        draw.ellipse([(bx - br, by - br), (bx + br, by + br)], fill=(255, 255, 255, 120))
        draw.ellipse([(bx - br, by - br), (bx + br, by + br)], outline=(255, 255, 255, 230), width=2)
        # Specular glint
        draw.ellipse([(bx - br + 2, by - br + 2), (bx - br + 5, by - br + 5)], fill=(255, 255, 255))


def _render_candy_carnival(img: Image.Image, draw: ImageDraw.ImageDraw, width: int, height: int, t: float) -> None:
    """Festive celebration with 3D rainbow, colorful balloons, rolling pastel hills and confetti."""
    # 3D Rainbow asset or drawn rainbow arch across top
    rainbow_asset = get_character_asset("rainbow")
    if rainbow_asset:
        rb_sz = int(width * 0.40)
        rb_resized = rainbow_asset.resize((rb_sz, int(rb_sz * 0.8)), Image.Resampling.LANCZOS)
        img.paste(rb_resized, (int(width * 0.60), int(height * 0.06)), mask=rb_resized)
    else:
        # Drawn rainbow arches
        rb_colors = [(239, 68, 68), (249, 115, 22), (234, 179, 8), (34, 197, 94), (59, 130, 246), (168, 85, 247)]
        rb_cx, rb_cy = int(width * 0.85), int(height * 0.20)
        for idx, col in enumerate(rb_colors):
            r = int(width * 0.32) - idx * 8
            draw.arc([(rb_cx - r, rb_cy - r), (rb_cx + r, rb_cy + r)], start=160, end=300, fill=col, width=8)

    # Floating 3D Balloon
    balloon_asset = get_character_asset("balloon")
    if balloon_asset:
        b_y = int(height * 0.16 + 15 * math.sin(t * 2.0))
        b_sz = int(width * 0.18)
        b_resized = balloon_asset.resize((b_sz, b_sz), Image.Resampling.LANCZOS)
        img.paste(b_resized, (int(width * 0.08), b_y), mask=b_resized)

    # Rolling pastel hills (pink & mint)
    draw.ellipse([(-120, int(height * 0.54)), (width + 120, int(height * 1.05))], fill=(244, 114, 182))
    draw.ellipse([(-60, int(height * 0.62)), (width + 160, int(height * 1.15))], fill=(110, 231, 183))

    # Swirling Confetti
    colors = [(255, 99, 132), (54, 162, 235), (255, 206, 86), (75, 192, 192), (153, 102, 255)]
    for c_idx in range(16):
        angle = t * 2.2 + c_idx * (2 * math.pi / 16)
        dist = int(width * 0.38 * (0.4 + 0.6 * ((c_idx % 4) / 4)))
        cx = width // 2 + int(dist * math.cos(angle))
        cy = int(height * 0.44) + int(dist * math.sin(angle) * 0.6)
        sz = 6 + (c_idx % 4) * 2
        draw.ellipse([(cx - sz, cy - sz), (cx + sz, cy + sz)], fill=colors[c_idx % len(colors)])


# ---------------------------------------------------------------------------
# Character and Props Compositing
# ---------------------------------------------------------------------------

def _render_character_with_motion(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    width: int,
    height: int,
    char_type: str,
    t: float,
    duration: float,
    theme_rgb: tuple[int, int, int],
) -> None:
    """Composites the high-resolution 3D character with rhythmic hop, tilt, squash & stretch, and pop-in entrance."""
    # 1. Entrance Pop-In (Elastic spring entrance in first 0.35s)
    if t < 0.35:
        progress = max(0.0, t / 0.35)
        # Elastic overshoot: zooms from 0.2 to 1.18 then settles to 1.0
        pop_scale = 0.2 + 0.8 * progress + 0.22 * math.sin(progress * math.pi)
    else:
        pop_scale = 1.0

    # 2. Rhythmic Hop (Matching cheerful BGM tempo, ~132 BPM / 2.2 hops/sec)
    bounce_freq = 2.2
    hop = abs(math.sin(t * math.pi * bounce_freq))
    char_base_y = int(height * 0.45)
    char_y = char_base_y - int(hop * 32)

    # 3. Squash and Stretch
    # Stretches on the jump up, squashes on landing impact
    squash_stretch = math.sin(t * math.pi * bounce_freq * 2)
    scale_x = (1.0 + 0.05 * squash_stretch) * pop_scale
    scale_y = (1.0 - 0.05 * squash_stretch) * pop_scale

    # 4. Playful tilting
    tilt = 4.0 * math.sin(t * math.pi * bounce_freq)

    # 5. Dynamic contact ground shadow (expands/fades as character hops)
    shadow_w = int(width * 0.38 * (1.0 - hop * 0.25) * pop_scale)
    shadow_h = int(height * 0.024 * (1.0 - hop * 0.25) * pop_scale)
    shadow_cx = width // 2
    shadow_cy = char_base_y + int(height * 0.14)
    if shadow_w > 5 and shadow_h > 2:
        draw.ellipse(
            [(shadow_cx - shadow_w // 2, shadow_cy - shadow_h // 2),
             (shadow_cx + shadow_w // 2, shadow_cy + shadow_h // 2)],
            fill=(30, 41, 59, int(130 * (1.0 - hop * 0.4))),
        )

    # 6. Render 3D Character Asset
    char_asset = get_character_asset(char_type)
    if char_asset:
        target_size = int(width * 0.48)
        nw = max(10, int(target_size * scale_x))
        nh = max(10, int(target_size * scale_y))
        resized = char_asset.resize((nw, nh), Image.Resampling.LANCZOS)
        rotated = resized.rotate(tilt, expand=True, resample=Image.Resampling.BILINEAR)

        px = (width - rotated.width) // 2
        py = char_y - rotated.height // 2
        img.paste(rotated, (px, py), mask=rotated)
    else:
        # Fallback procedural friendly circular character badge
        c_r = int(width * 0.20 * pop_scale)
        c_cx = width // 2
        draw.ellipse([(c_cx - c_r, char_y - c_r), (c_cx + c_r, char_y + c_r)], fill=theme_rgb)
        draw.ellipse([(c_cx - c_r + 6, char_y - c_r + 6), (c_cx + c_r - 6, char_y + c_r - 6)], outline=(255, 255, 255), width=4)
        star_font = _get_font(int(c_r * 0.9), bold=True)
        draw.text((c_cx, char_y), "⭐", font=star_font, fill=(255, 255, 255), anchor="mm")


def _render_counting_props(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    width: int,
    height: int,
    card: KidsCard,
    t: float,
) -> None:
    """Animates 3D counting items (e.g. shiny red apples) popping in sequentially."""
    full_info = f"{card.title} {card.subtitle}".lower()
    is_apple_theme = any(k in full_info for k in ("táo", "apple", "quả"))
    count_match = re.search(r"\b([1-5])\b", card.title)
    count = int(count_match.group(1)) if count_match else (1 if is_apple_theme else 0)

    if count <= 0:
        return

    apple_asset = get_character_asset("apple")
    apple_y_base = int(height * 0.58)
    apple_size = int(width * 0.17)

    # Position layouts for 1, 2, 3, 4, 5 items
    if count == 1:
        positions = [(int(width * 0.78), apple_y_base, 0.15)]
    elif count == 2:
        positions = [
            (int(width * 0.18), apple_y_base, 0.15),
            (int(width * 0.82), apple_y_base, 0.45),
        ]
    elif count == 3:
        positions = [
            (int(width * 0.16), apple_y_base - 20, 0.15),
            (int(width * 0.84), apple_y_base - 20, 0.45),
            (int(width * 0.50), apple_y_base + 35, 0.75),
        ]
    elif count == 4:
        positions = [
            (int(width * 0.15), apple_y_base - 30, 0.15),
            (int(width * 0.85), apple_y_base - 30, 0.35),
            (int(width * 0.28), apple_y_base + 30, 0.55),
            (int(width * 0.72), apple_y_base + 30, 0.75),
        ]
    else:
        positions = [
            (int(width * 0.14), apple_y_base - 30, 0.10),
            (int(width * 0.86), apple_y_base - 30, 0.25),
            (int(width * 0.50), apple_y_base - 45, 0.40),
            (int(width * 0.28), apple_y_base + 30, 0.55),
            (int(width * 0.72), apple_y_base + 30, 0.70),
        ]

    for ax, ay, start_t in positions:
        if t < start_t:
            continue
        # Pop-in elastic scale
        dt = t - start_t
        pop = min(1.0, dt / 0.25)
        scale = 0.2 + 0.8 * pop + 0.25 * math.sin(pop * math.pi) if pop < 1.0 else 1.0

        # Gentle bobbing
        bob = abs(math.sin((t + start_t) * math.pi * 2.8)) * 16
        cur_y = int(ay - bob)
        cur_sz = max(10, int(apple_size * scale))

        # Shadow under prop
        sw = int(cur_sz * 0.75 * (1.0 - (bob / 20) * 0.3))
        sh = int(cur_sz * 0.18)
        draw.ellipse([(ax - sw // 2, ay + cur_sz // 2 - sh // 2), (ax + sw // 2, ay + cur_sz // 2 + sh // 2)], fill=(30, 41, 59, 100))

        if apple_asset:
            a_resized = apple_asset.resize((cur_sz, cur_sz), Image.Resampling.LANCZOS)
            img.paste(a_resized, (ax - cur_sz // 2, cur_y - cur_sz // 2), mask=a_resized)
        else:
            draw.ellipse([(ax - cur_sz // 2, cur_y - cur_sz // 2), (ax + cur_sz // 2, cur_y + cur_sz // 2)], fill=(239, 68, 68))


# ---------------------------------------------------------------------------
# UI Components: Drop-Down Header & Slide-Up Subtitles
# ---------------------------------------------------------------------------

def _render_animated_header(
    draw: ImageDraw.ImageDraw,
    width: int,
    height: int,
    card: KidsCard,
    t: float,
    theme_rgb: tuple[int, int, int],
) -> None:
    """Renders the top title badge with a smooth drop-down bounce entrance."""
    target_y = int(height * 0.045)
    # Smooth drop-down bounce at 0.0s -> 0.35s
    if t < 0.35:
        prog = t / 0.35
        # Overshoot drop: drops from -60 to target_y with slight spring bounce
        cur_y = int(-60 + (target_y + 60) * (1.0 - math.cos(prog * math.pi * 0.5)) + 12 * math.sin(prog * math.pi))
    else:
        cur_y = target_y

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

    # Drop shadow
    draw.rounded_rectangle(
        [(badge_x + 3, cur_y + 4), (badge_x + badge_w + 3, cur_y + badge_h + 4)],
        radius=badge_h // 2,
        fill=(15, 23, 42, 70),
    )
    # Glassy pill badge
    draw.rounded_rectangle(
        [(badge_x, cur_y), (badge_x + badge_w, cur_y + badge_h)],
        radius=badge_h // 2,
        fill=(255, 255, 255, 245),
        outline=theme_rgb,
        width=3,
    )
    draw.text((width // 2, cur_y + badge_h // 2), card.title, font=title_font, fill=(15, 23, 42), anchor="mm")


def _render_animated_subtitles(
    draw: ImageDraw.ImageDraw,
    width: int,
    height: int,
    card: KidsCard,
    t: float,
) -> None:
    """Renders the synchronized subtitle box with smooth slide-up animation and exact voiceover words."""
    target_box_y = int(height * 0.74)
    sub_box_h = int(height * 0.17)
    sub_margin = int(width * 0.05)

    # Slide-up animation at 0.0s -> 0.35s
    if t < 0.35:
        prog = t / 0.35
        cur_sub_y = int(height - (height - target_box_y) * (prog ** 1.3))
    else:
        cur_sub_y = target_box_y

    sub_box = [(sub_margin, cur_sub_y), (width - sub_margin, cur_sub_y + sub_box_h)]

    # Soft dark glow pill
    draw.rounded_rectangle(
        sub_box,
        radius=24,
        fill=(15, 23, 42, 235),
        outline=(250, 204, 21),
        width=3,
    )

    # Subtitle Header Tag
    sub_tag_font = _get_font(int(height * 0.018), bold=True)
    draw.text((sub_margin + 24, cur_sub_y + 18), "🌟 PHỤ ĐỀ / SUBTITLE", font=sub_tag_font, fill=(250, 204, 21))

    # Exact Spoken Voiceover Text
    sub_font = _get_font(int(height * 0.024), bold=True)
    sub_lines = textwrap.wrap(card.spoken_text, width=28)
    sub_text_start_y = cur_sub_y + int(height * 0.054)
    for l_idx, line in enumerate(sub_lines[:3]):
        draw.text(
            (width // 2, sub_text_start_y + l_idx * int(height * 0.034)),
            line,
            font=sub_font,
            fill=(255, 255, 255),
            anchor="mm",
        )

    # Footer accent
    bot_y = int(height * 0.955)
    bot_font = _get_font(int(height * 0.017), bold=True)
    draw.text(
        (width // 2, bot_y),
        "✨ Vừa Học Vừa Chơi • Bé Càng Thông Minh ✨",
        font=bot_font,
        fill=(15, 23, 42),
        anchor="mm",
    )


# ---------------------------------------------------------------------------
# Master Frame Renderer
# ---------------------------------------------------------------------------

def render_animated_kids_frame(
    t: float,
    card: KidsCard,
    duration: float,
    width: int = 540,
    height: int = 960,
    char_type: Optional[str] = None,
    bg_theme: Optional[str] = None,
    scene_index: int = 0,
) -> np.ndarray:
    """Renders a single frame of the vibrant, lively cartoon animation at time t."""
    theme_rgb = _hex_to_rgb(card.theme_color)
    if char_type is None:
        char_type = _detect_character_type(card)
    if bg_theme is None:
        bg_theme = _detect_background_theme(card, scene_index)

    # 1. Base Gradient Canvas according to Environment Theme
    if bg_theme == "sunset_valley":
        img = _render_gradient(width, height, (251, 146, 60), (167, 139, 250))
        draw = ImageDraw.Draw(img)
        _render_sunset_valley(img, draw, width, height, t)
    elif bg_theme == "magical_night":
        img = _render_gradient(width, height, (15, 23, 42), (88, 28, 135))
        draw = ImageDraw.Draw(img)
        _render_magical_night(img, draw, width, height, t)
    elif bg_theme == "ocean_paradise":
        img = _render_gradient(width, height, (165, 243, 252), (14, 116, 144))
        draw = ImageDraw.Draw(img)
        _render_ocean_paradise(img, draw, width, height, t)
    elif bg_theme == "candy_carnival":
        img = _render_gradient(width, height, (254, 205, 211), (224, 231, 255))
        draw = ImageDraw.Draw(img)
        _render_candy_carnival(img, draw, width, height, t)
    else:  # "sunny_meadow"
        img = _render_gradient(width, height, (186, 230, 253), (240, 249, 255))
        draw = ImageDraw.Draw(img)
        _render_sunny_meadow(img, draw, width, height, t)

    # 2. Compositing 3D Character with Physics & Animation
    _render_character_with_motion(img, draw, width, height, char_type, t, duration, theme_rgb)

    # 3. Compositing Counting Props (if applicable)
    _render_counting_props(img, draw, width, height, card, t)

    # 4. Animated Header (Spring Drop-Down)
    _render_animated_header(draw, width, height, card, t, theme_rgb)

    # 5. Animated Subtitles (Spring Slide-Up)
    _render_animated_subtitles(draw, width, height, card, t)

    return np.array(img.convert("RGB"))


def make_kids_animated_scene_clip(
    card: KidsCard,
    character_img=None,  # Deprecated param kept for backwards compatibility
    duration: float = 4.0,
    width: int = 540,
    height: int = 960,
    scene_index: int = 0,
    bg_theme: Optional[str] = None,
) -> VideoClip:
    """Creates a smooth, procedurally animated VideoClip for a single educational scene.
    
    Uses 3D high-resolution Fluent Emojis, dynamic backgrounds, bouncing physics,
    and synchronized subtitles.
    """
    char_type = _detect_character_type(card)
    chosen_theme = bg_theme if bg_theme else _detect_background_theme(card, scene_index)

    def make_frame(t: float) -> np.ndarray:
        return render_animated_kids_frame(
            t=t,
            card=card,
            duration=duration,
            width=width,
            height=height,
            char_type=char_type,
            bg_theme=chosen_theme,
            scene_index=scene_index,
        )

    return VideoClip(make_frame, duration=duration)
