"""
CPU-mode scene renderer: Ken Burns (zoom/pan) on a single image.

When no image is provided, generates a rich gradient + product-card
placeholder so the video is never a flat black screen.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

import numpy as np
from PIL import Image as PILImage, ImageDraw, ImageFont, ImageFilter
from moviepy import ColorClip, VideoClip

from core.config import settings
from core.logging import get_logger
from utils.fonts import find_vietnamese_font

logger = get_logger(__name__)

# Role → gradient color pairs (top RGB, bottom RGB)
_GRADIENTS: dict[str, Tuple[Tuple[int, int, int], Tuple[int, int, int]]] = {
    "hook": ((88, 28, 135), (30, 27, 75)),       # violet → deep indigo
    "showcase": ((15, 23, 42), (49, 46, 129)),   # slate → indigo
    "lifestyle": ((6, 78, 59), (20, 30, 50)),    # emerald → dark
    "detail": ((30, 58, 138), (15, 23, 42)),     # blue → slate
    "closeup": ((127, 29, 29), (30, 27, 75)),    # red → indigo
    "social_proof": ((55, 48, 163), (15, 23, 42)),
    "cta": ((120, 53, 15), (30, 27, 75)),        # amber → dark
    "default": ((30, 27, 75), (15, 23, 42)),
}


def _cover_resize(pil: PILImage.Image, w: int, h: int, extra_scale: float = 1.12) -> PILImage.Image:
    iw, ih = pil.size
    scale = max(w / iw, h / ih) * extra_scale
    nw, nh = int(iw * scale), int(ih * scale)
    pil = pil.resize((nw, nh), PILImage.LANCZOS)
    left = (nw - w) // 2
    top = (nh - h) // 2
    return pil.crop((left, top, left + w, top + h))


def _vertical_gradient(
    w: int,
    h: int,
    top: Tuple[int, int, int],
    bottom: Tuple[int, int, int],
) -> PILImage.Image:
    """Create a smooth vertical gradient image."""
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    for y in range(h):
        t = y / max(h - 1, 1)
        r = int(top[0] * (1 - t) + bottom[0] * t)
        g = int(top[1] * (1 - t) + bottom[1] * t)
        b = int(top[2] * (1 - t) + bottom[2] * t)
        arr[y, :] = (r, g, b)
    return PILImage.fromarray(arr)


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = find_vietnamese_font()
    if path and Path(path).is_file():
        try:
            return ImageFont.truetype(path, size=size)
        except Exception:
            pass
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size=size)
    except Exception:
        return ImageFont.load_default()


def make_placeholder_image(
    w: int,
    h: int,
    *,
    role: str = "default",
    product_name: str = "",
    location: str = "",
    category: str = "",
) -> PILImage.Image:
    """
    Build a TikTok-style placeholder card:
    gradient background + soft orb + product name + location badge.
    """
    top, bottom = _GRADIENTS.get(role, _GRADIENTS["default"])
    img = _vertical_gradient(w, h, top, bottom)
    draw = ImageDraw.Draw(img, "RGBA")

    # Soft glowing orbs for depth
    overlay = PILImage.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.ellipse([w // 2 - 280, h // 3 - 280, w // 2 + 280, h // 3 + 280], fill=(255, 255, 255, 28))
    od.ellipse([w // 4 - 120, h * 2 // 3 - 120, w // 4 + 120, h * 2 // 3 + 120], fill=(167, 139, 250, 35))
    od.ellipse([w * 3 // 4 - 100, h // 5 - 100, w * 3 // 4 + 100, h // 5 + 100], fill=(251, 191, 36, 25))
    img = PILImage.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    # Card panel
    margin = 70
    card_top = h // 2 - 180
    card_bot = h // 2 + 220
    draw.rounded_rectangle(
        [margin, card_top, w - margin, card_bot],
        radius=36,
        fill=(255, 255, 255, 40) if False else (20, 20, 35),
        outline=(255, 255, 255),
        width=2,
    )
    # Re-draw with semi-transparent via overlay
    card = PILImage.new("RGBA", (w, h), (0, 0, 0, 0))
    cd = ImageDraw.Draw(card)
    cd.rounded_rectangle(
        [margin, card_top, w - margin, card_bot],
        radius=36,
        fill=(15, 15, 28, 200),
        outline=(255, 255, 255, 90),
        width=2,
    )
    img = PILImage.alpha_composite(img.convert("RGBA"), card).convert("RGB")
    draw = ImageDraw.Draw(img)

    # Role badge
    role_label = {
        "hook": "HOOK",
        "showcase": "SHOWCASE",
        "lifestyle": "LIFESTYLE",
        "detail": "DETAIL",
        "cta": "CTA · MUA NGAY",
        "closeup": "CLOSE-UP",
        "social_proof": "REVIEW",
    }.get(role, role.upper())
    font_sm = _load_font(28)
    font_lg = _load_font(52)
    font_md = _load_font(34)

    # Center text helpers
    def center_text(text: str, y: int, font, fill=(255, 255, 255)):
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        draw.text(((w - tw) // 2, y), text, font=font, fill=fill)

    center_text(role_label, card_top + 36, font_sm, fill=(196, 181, 253))

    name = (product_name or "Sản phẩm").strip()
    if len(name) > 36:
        name = name[:34] + "…"
    center_text(name, card_top + 100, font_lg, fill=(255, 255, 255))

    if category:
        center_text(f"#{category}", card_top + 175, font_md, fill=(165, 180, 252))

    if location:
        center_text(f"📍 {location}", card_top + 230, font_md, fill=(253, 224, 71))

    # Hint at bottom
    center_text("Upload ảnh sản phẩm để video đẹp hơn", h - 160, font_sm, fill=(148, 163, 184))

    return img


def make_kenburns_clip(
    image_path: Optional[Path | str],
    duration: float,
    *,
    width: int | None = None,
    height: int | None = None,
    zoom_start: float = 1.0,
    zoom_end: float = 1.10,
    pan_x: float = 0.0,
    pan_y: float = 0.0,
    fps: int | None = None,
    # Placeholder context (used when no image)
    role: str = "default",
    product_name: str = "",
    location: str = "",
    category: str = "",
) -> VideoClip:
    """
    Ken Burns clip from image, or animated gradient placeholder.
    """
    w = width or settings.video_width
    h = height or settings.video_height
    fps = fps or settings.video_fps
    duration = max(0.5, float(duration))

    base_arr: Optional[np.ndarray] = None

    if image_path and Path(image_path).is_file():
        try:
            pil = PILImage.open(str(image_path)).convert("RGB")
            base = _cover_resize(pil, w, h, extra_scale=1.15)
            base_arr = np.array(base)
        except Exception as e:
            logger.warning("Ken Burns image failed (%s) → placeholder", e)

    if base_arr is None:
        # Rich placeholder instead of flat black
        pil = make_placeholder_image(
            w, h,
            role=role,
            product_name=product_name,
            location=location,
            category=category,
        )
        # Extra scale for zoom room
        pil = pil.resize((int(w * 1.12), int(h * 1.12)), PILImage.LANCZOS)
        left = (pil.width - w) // 2
        top = (pil.height - h) // 2
        base = pil.crop((left, top, left + w, top + h))
        # Keep larger canvas for zoom
        base_arr = np.array(
            make_placeholder_image(
                int(w * 1.15), int(h * 1.15),
                role=role,
                product_name=product_name,
                location=location,
                category=category,
            )
        )

    def make_frame(t: float) -> np.ndarray:
        progress = min(1.0, t / duration) if duration > 0 else 0.0
        zoom = zoom_start + (zoom_end - zoom_start) * progress
        cx = 0.5 + pan_x * 0.12 * progress
        cy = 0.5 + pan_y * 0.12 * progress

        bh, bw = base_arr.shape[:2]
        zw = max(1, int(bw / zoom))
        zh = max(1, int(bh / zoom))
        left = int(cx * bw - zw / 2)
        top = int(cy * bh - zh / 2)
        left = max(0, min(left, bw - zw))
        top = max(0, min(top, bh - zh))
        crop = base_arr[top : top + zh, left : left + zw]
        pil_c = PILImage.fromarray(crop).resize((w, h), PILImage.LANCZOS)
        return np.array(pil_c)

    clip = VideoClip(make_frame, duration=duration)
    clip = clip.with_fps(fps)
    return clip
