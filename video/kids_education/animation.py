"""Procedural 2D/2.5D Cartoon Animation Engine for Kids Videos (0đ cost, 100% dynamic motion).

Transforms static illustrations into lively, bouncing cartoon animations:
- Animated drifting clouds & rotating sun rays
- Rhythmic character hopping, squash & stretch, and playful tilting
- Bouncing cartoon apples / counting objects with pop-in effects
- Floating sparkles & colorful bubbles
- Fully synchronized, high-contrast subtitle pill showing the EXACT spoken voiceover text
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


def _draw_cartoon_apple_small(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int) -> None:
    """Draws a cute, shiny kawaii cartoon apple at (cx, cy)."""
    r = max(8, size // 2)
    # Red apple body
    draw.ellipse([(cx - int(r * 0.9), cy - int(r * 0.7)), (cx + int(r * 0.9), cy + int(r * 0.9))], fill=(239, 68, 68))
    # Stem
    draw.line([(cx, cy - int(r * 0.7)), (cx + int(r * 0.2), cy - int(r * 1.15))], fill=(120, 53, 15), width=max(2, int(r * 0.15)))
    # Green leaf
    draw.ellipse([(cx + int(r * 0.15), cy - int(r * 1.1)), (cx + int(r * 0.65), cy - int(r * 0.75))], fill=(34, 197, 94))
    # Eyes & smile
    eye_r = max(2, int(r * 0.12))
    draw.ellipse([(cx - int(r * 0.35) - eye_r, cy - eye_r), (cx - int(r * 0.35) + eye_r, cy + eye_r)], fill=(30, 41, 59))
    draw.ellipse([(cx + int(r * 0.35) - eye_r, cy - eye_r), (cx + int(r * 0.35) + eye_r, cy + eye_r)], fill=(30, 41, 59))
    draw.arc([(cx - int(r * 0.25), cy), (cx + int(r * 0.25), cy + int(r * 0.35))], start=0, end=180, fill=(30, 41, 59), width=max(2, int(r * 0.08)))


def render_animated_kids_frame(
    t: float,
    card: KidsCard,
    character_img: Optional[Image.Image],
    duration: float,
    width: int = 540,
    height: int = 960,
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
    # Background hill
    draw.ellipse([(-120, int(height * 0.54)), (width + 120, int(height * 1.05))], fill=(134, 239, 172))
    # Foreground bright hill
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

    # 6. Animated Cartoon Character in Center
    bounce_freq = 2.2  # 2.2 hops per second
    hop = abs(math.sin(t * math.pi * bounce_freq))
    char_base_y = int(height * 0.45)
    char_y = char_base_y - int(hop * 32)
    tilt = 3.5 * math.sin(t * math.pi * bounce_freq)

    # Dynamic contact shadow on ground
    shadow_w = int(width * 0.36 * (1.0 - hop * 0.25))
    shadow_h = int(height * 0.025 * (1.0 - hop * 0.25))
    shadow_cx = width // 2
    shadow_cy = char_base_y + int(height * 0.15)
    draw.ellipse(
        [(shadow_cx - shadow_w // 2, shadow_cy - shadow_h // 2),
         (shadow_cx + shadow_w // 2, shadow_cy + shadow_h // 2)],
        fill=(34, 197, 94, 180),
    )

    # Render character image with squash & stretch
    char_w = int(width * 0.50)
    if character_img:
        try:
            aspect = character_img.width / max(1, character_img.height)
            tw = char_w
            th = int(char_w / aspect)
            c_base = character_img.resize((tw, th), Image.Resampling.LANCZOS)
            
            # Squash and stretch
            scale_x = 1.0 + 0.05 * math.sin(t * math.pi * bounce_freq * 2)
            scale_y = 1.0 - 0.05 * math.sin(t * math.pi * bounce_freq * 2)
            nw = max(1, int(tw * scale_x))
            nh = max(1, int(th * scale_y))
            c_scaled = c_base.resize((nw, nh), Image.Resampling.BILINEAR)
            
            # Playful rotation
            c_rot = c_scaled.rotate(tilt, expand=True, resample=Image.Resampling.BILINEAR)
            paste_x = (width - c_rot.width) // 2
            paste_y = char_y - c_rot.height // 2
            if c_rot.mode == "RGBA":
                img.paste(c_rot, (paste_x, paste_y), mask=c_rot)
            else:
                img.paste(c_rot, (paste_x, paste_y))
        except Exception:
            character_img = None

    if character_img is None:
        # Fallback procedural friendly character face
        c_r = int(width * 0.22)
        c_cx = width // 2
        draw.ellipse([(c_cx - c_r, char_y - c_r), (c_cx + c_r, char_y + c_r)], fill=theme_rgb)
        draw.ellipse([(c_cx - c_r + 6, char_y - c_r + 6), (c_cx + c_r - 6, char_y + c_r - 6)], outline=(255, 255, 255), width=4)
        safe_emoji = sanitize_emoji(card.emoji)
        emoji_font = _get_font(int(c_r * 1.1), bold=True)
        draw.text((c_cx, char_y), safe_emoji if len(safe_emoji) <= 2 else "🌟", font=emoji_font, fill=(255, 255, 255), anchor="mm")

    # 7. Animated Bouncing Counting Apples / Items (if applicable)
    full_info = f"{card.title} {card.subtitle}".lower()
    is_apple_theme = any(k in full_info for k in ("táo", "apple", "quả"))
    count_match = re.search(r"\b([1-5])\b", card.title)
    count = int(count_match.group(1)) if count_match else (1 if is_apple_theme else 0)

    if count > 0:
        apple_y_base = int(height * 0.58)
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
            # Each apple bobs happily
            a_bob = abs(math.sin((t + phase) * math.pi * 2.8)) * 18
            cur_ay = int(ay - a_bob)
            # Pop-in scale effect
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

    # 9. Synchronized Subtitles (Phụ đề hiển thị CHÍNH XÁC lời thoại phát âm)
    # Styled like high-contrast professional kids learning channels
    sub_box_y = int(height * 0.74)
    sub_box_h = int(height * 0.17)
    sub_margin = int(width * 0.05)
    sub_box = [(sub_margin, sub_box_y), (width - sub_margin, sub_box_y + sub_box_h)]

    # Dark rounded pill container with glowing yellow border
    draw.rounded_rectangle(
        sub_box,
        radius=24,
        fill=(15, 23, 42, 230),
        outline=(250, 204, 21),
        width=3,
    )

    # Subtitle Header tag
    sub_tag_font = _get_font(int(height * 0.018), bold=True)
    draw.text((sub_margin + 24, sub_box_y + 18), "🌟 PHỤ ĐỀ / SUBTITLE", font=sub_tag_font, fill=(250, 204, 21))

    # The exact spoken words of the voiceover wrapped clearly across lines
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
    character_img: Optional[Image.Image],
    duration: float,
    width: int = 540,
    height: int = 960,
) -> VideoClip:
    """Creates a smooth, procedurally animated VideoClip for a single educational scene."""
    # Ensure character_img is pre-processed once for high FPS performance
    cached_char = character_img
    if cached_char:
        try:
            cached_char = cached_char.convert("RGBA")
        except Exception:
            cached_char = None

    def make_frame(t: float) -> np.ndarray:
        return render_animated_kids_frame(
            t=t,
            card=card,
            character_img=cached_char,
            duration=duration,
            width=width,
            height=height,
        )

    return VideoClip(make_frame, duration=duration)
