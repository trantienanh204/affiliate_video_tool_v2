"""Procedural flashcard canvas generator using Pillow (100% offline, zero-cost)."""

from __future__ import annotations

import re
import textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from video.kids_education.presets import KidsCard

EMOJI_SLACK_MAP: dict[str, str] = {
    ":frog:": "🐸",
    ":cat_face:": "🐱",
    ":cat:": "🐱",
    ":dog:": "🐶",
    ":dog_face:": "🐶",
    ":rabbit:": "🐰",
    ":bear:": "🐻",
    ":monkey:": "🐵",
    ":monkey_face:": "🐵",
    ":lion:": "🦁",
    ":elephant:": "🐘",
    ":tiger:": "🐯",
    ":panda:": "🐼",
    ":apple:": "🍎",
    ":banana:": "🍌",
    ":car:": "🚗",
    ":police_car:": "🚓",
    ":fire_engine:": "🚒",
    ":truck:": "🚚",
    ":star:": "⭐",
    ":sparkles:": "✨",
    ":party:": "🎉",
    ":tada:": "🎉",
    ":balloon:": "🎈",
    ":rainbow:": "🌈",
    ":heart:": "❤️",
    ":smile:": "😊",
    ":laughing:": "😄",
}


def sanitize_emoji(emoji_str: str) -> str:
    """Replaces Slack/GitHub-style :name: codes with true Unicode or friendly emoji."""
    if not emoji_str:
        return "🌟"
    s = emoji_str.strip()
    for code, uni in EMOJI_SLACK_MAP.items():
        s = s.replace(code, uni)
    # Strip any remaining unmapped colon tags like :unknown_code:
    s = re.sub(r":[a-zA-Z0-9_-]+:", "", s).strip()
    return s if s else "🌟"


def _hex_to_rgb(hex_code: str) -> tuple[int, int, int]:
    hex_code = hex_code.lstrip("#")
    if len(hex_code) == 3:
        hex_code = "".join(c * 2 for c in hex_code)
    try:
        return tuple(int(hex_code[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:
        return (78, 205, 196)


def _get_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    """Find a readable TTF font with fallback to default."""
    font_candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    ]
    for p in font_candidates:
        if Path(p).is_file():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    try:
        return ImageFont.truetype("arial.ttf", size)
    except Exception:
        return ImageFont.load_default()


def _fit_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_width: int,
    initial_size: int,
    min_size: int = 24,
    bold: bool = True,
) -> tuple[ImageFont.ImageFont, tuple[int, int, int, int]]:
    """Dynamically scales font size down until text fits within max_width."""
    size = initial_size
    font = _get_font(size, bold=bold)
    while size > min_size:
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        if w <= max_width:
            return font, bbox
        size -= 3
        font = _get_font(size, bold=bold)
    return font, draw.textbbox((0, 0), text, font=font)


def _draw_cartoon_apple(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int) -> None:
    """Draws a cute, shiny kawaii cartoon apple at (cx, cy)."""
    r = size // 2
    # Two overlapping circles for classic apple shape
    left_c = (cx - int(r * 0.4), cy, int(r * 0.8))
    right_c = (cx + int(r * 0.4), cy, int(r * 0.8))
    draw.ellipse([(left_c[0] - left_c[2], left_c[1] - left_c[2]), (left_c[0] + left_c[2], left_c[1] + left_c[2])], fill=(239, 68, 68))
    draw.ellipse([(right_c[0] - right_c[2], right_c[1] - right_c[2]), (right_c[0] + right_c[2], right_c[1] + right_c[2])], fill=(220, 38, 38))
    # Fill middle
    draw.rectangle([(cx - int(r * 0.3), cy - int(r * 0.6)), (cx + int(r * 0.3), cy + int(r * 0.6))], fill=(239, 68, 68))
    
    # Stem on top
    stem_top = cy - int(r * 1.25)
    draw.line([(cx, cy - int(r * 0.7)), (cx + int(r * 0.15), stem_top)], fill=(120, 53, 15), width=max(4, int(r * 0.12)))
    # Green Leaf
    leaf_cx = cx + int(r * 0.4)
    leaf_cy = cy - int(r * 0.95)
    draw.ellipse([(leaf_cx - int(r * 0.35), leaf_cy - int(r * 0.18)), (leaf_cx + int(r * 0.35), leaf_cy + int(r * 0.18))], fill=(34, 197, 94))
    
    # Cute Kawaii Eyes & Smile
    eye_r = max(3, int(r * 0.10))
    eye_y = cy - int(r * 0.1)
    draw.ellipse([(cx - int(r * 0.35) - eye_r, eye_y - eye_r), (cx - int(r * 0.35) + eye_r, eye_y + eye_r)], fill=(30, 41, 59))
    draw.ellipse([(cx + int(r * 0.35) - eye_r, eye_y - eye_r), (cx + int(r * 0.35) + eye_r, eye_y + eye_r)], fill=(30, 41, 59))
    # Eye sparkle
    draw.ellipse([(cx - int(r * 0.35) - 2, eye_y - 2), (cx - int(r * 0.35) + 2, eye_y + 2)], fill=(255, 255, 255))
    draw.ellipse([(cx + int(r * 0.35) - 2, eye_y - 2), (cx + int(r * 0.35) + 2, eye_y + 2)], fill=(255, 255, 255))
    # Cheerful Smile arc
    draw.arc([(cx - int(r * 0.2), cy + int(r * 0.05)), (cx + int(r * 0.2), cy + int(r * 0.35))], start=0, end=180, fill=(30, 41, 59), width=max(3, int(r * 0.07)))
    # Pink cheeks
    ch_r = max(4, int(r * 0.12))
    draw.ellipse([(cx - int(r * 0.55) - ch_r, cy + int(r * 0.08) - ch_r), (cx - int(r * 0.55) + ch_r, cy + int(r * 0.08) + ch_r)], fill=(254, 205, 211))
    draw.ellipse([(cx + int(r * 0.55) - ch_r, cy + int(r * 0.08) - ch_r), (cx + int(r * 0.55) + ch_r, cy + int(r * 0.08) + ch_r)], fill=(254, 205, 211))


def create_flashcard_image(
    card: KidsCard,
    output_path: Path,
    width: int = 1080,
    height: int = 1920,
    center_image: Image.Image | None = None,
) -> Path:
    """
    Renders a colorful, kid-friendly educational flashcard.
    If center_image is provided, it is composed with aspect-ratio preservation and alpha transparency.
    Otherwise, a rich procedural cartoon illustration with kawaii characters is drawn.
    All text auto-wraps and dynamically fits the screen without clipping.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    base_rgb = _hex_to_rgb(card.theme_color)
    safe_emoji = sanitize_emoji(card.emoji)

    # 1. Cheerful pastel background
    img = Image.new("RGB", (width, height), (245, 248, 255))
    draw = ImageDraw.Draw(img)

    # Top colorful banner
    banner_height = int(height * 0.22)
    draw.rectangle([(0, 0), (width, banner_height)], fill=base_rgb)

    # Decorative bubbles and confetti
    for bx, by, br, color in [
        (int(width * 0.12), int(banner_height * 0.4), int(width * 0.08), (255, 255, 255, 90)),
        (int(width * 0.88), int(banner_height * 0.3), int(width * 0.10), (255, 255, 255, 80)),
        (int(width * 0.50), int(banner_height * 0.85), int(width * 0.06), (255, 255, 255, 70)),
        (int(width * 0.06), int(height * 0.45), int(width * 0.025), base_rgb),
        (int(width * 0.94), int(height * 0.65), int(width * 0.03), base_rgb),
    ]:
        draw.ellipse([(bx - br, by - br), (bx + br, by + br)], fill=color)

    # 2. Card Container (White rounded card in the center)
    card_margin_x = int(width * 0.07)
    card_top = int(height * 0.14)
    card_bottom = int(height * 0.90)
    card_box = [(card_margin_x, card_top), (width - card_margin_x, card_bottom)]
    corner_r = int(width * 0.06)

    # Shadow
    shadow_offset = int(width * 0.025)
    draw.rounded_rectangle(
        [(card_box[0][0] + shadow_offset, card_box[0][1] + shadow_offset),
         (card_box[1][0] + shadow_offset, card_box[1][1] + shadow_offset)],
        radius=corner_r,
        fill=(210, 220, 235),
    )
    # White card body
    draw.rounded_rectangle(card_box, radius=corner_r, fill=(255, 255, 255))
    # Double outline
    draw.rounded_rectangle(card_box, radius=corner_r, outline=base_rgb, width=int(width * 0.014))

    # 3. Category / Tag Pill (Auto-sized to prevent text overflow)
    pill_text = "🌟 BÉ VUI HỌC MỖI NGÀY 🌟"
    tag_font = _get_font(int(height * 0.022), bold=True)
    t_bbox = draw.textbbox((0, 0), pill_text, font=tag_font)
    txt_w = t_bbox[2] - t_bbox[0]
    pill_w = max(txt_w + 60, int(width * 0.52))
    pill_h = int(height * 0.052)
    pill_x1 = (width - pill_w) // 2
    pill_y1 = card_top + int(height * 0.022)
    draw.rounded_rectangle(
        [(pill_x1, pill_y1), (pill_x1 + pill_w, pill_y1 + pill_h)],
        radius=pill_h // 2,
        fill=base_rgb,
    )
    draw.text(
        (width // 2, pill_y1 + pill_h // 2),
        pill_text,
        font=tag_font,
        fill=(255, 255, 255),
        anchor="mm",
    )

    # 4. Center Illustration Box
    inner_w = (width - 2 * card_margin_x) - int(width * 0.08)
    inner_h = int(height * 0.38)
    inner_x = (width - inner_w) // 2
    inner_y = pill_y1 + pill_h + int(height * 0.025)
    inner_box = [(inner_x, inner_y), (inner_x + inner_w, inner_y + inner_h)]

    # Draw rounded container for illustration
    draw.rounded_rectangle(
        inner_box,
        radius=int(width * 0.04),
        fill=(248, 250, 252),
        outline=base_rgb,
        width=int(width * 0.01),
    )

    rendered_center = False
    if center_image:
        try:
            # Preserve aspect ratio and respect alpha transparency
            cw, ch = center_image.size
            if cw > 0 and ch > 0:
                pad = 30
                max_w = inner_w - pad * 2
                max_h = inner_h - pad * 2
                scale = min(max_w / cw, max_h / ch)
                new_w = max(1, int(cw * scale))
                new_h = max(1, int(ch * scale))
                resized = center_image.resize((new_w, new_h), Image.Resampling.LANCZOS)
                paste_x = inner_x + (inner_w - new_w) // 2
                paste_y = inner_y + (inner_h - new_h) // 2
                if resized.mode == "RGBA":
                    img.paste(resized, (paste_x, paste_y), mask=resized)
                else:
                    img.paste(resized, (paste_x, paste_y))
                rendered_center = True
        except Exception:
            rendered_center = False

    if not rendered_center:
        # Rich procedural cartoon landscape with kawaii characters
        # Sky background inside illustration box
        draw.rounded_rectangle(
            inner_box,
            radius=int(width * 0.04),
            fill=(224, 242, 254),
            outline=base_rgb,
            width=int(width * 0.01),
        )
        # Sun
        sun_x, sun_y, sun_r = inner_x + int(inner_w * 0.85), inner_y + int(inner_h * 0.22), int(inner_h * 0.16)
        draw.ellipse([(sun_x - sun_r, sun_y - sun_r), (sun_x + sun_r, sun_y + sun_r)], fill=(254, 240, 138))

        # Green rolling hills
        hill_top = inner_y + int(inner_h * 0.72)
        draw.ellipse([(inner_x - 50, hill_top), (inner_x + inner_w + 50, inner_y + inner_h + 80)], fill=(134, 239, 172))

        # Detect theme: apple / fruit counting vs general
        full_text = f"{card.title} {card.subtitle} {card.spoken_text}".lower()
        is_apple_theme = any(k in full_text for k in ("táo", "apple", "trái cây", "quả"))
        
        # Detect count
        count_match = re.search(r"\b([1-5])\b", card.title)
        count = int(count_match.group(1)) if count_match else 1

        if is_apple_theme:
            # Draw cute kawaii apples corresponding to count!
            c_y = inner_y + int(inner_h * 0.46)
            if count == 1:
                _draw_cartoon_apple(draw, width // 2, c_y, size=int(inner_h * 0.52))
            elif count == 2:
                spacing = int(inner_w * 0.24)
                _draw_cartoon_apple(draw, width // 2 - spacing, c_y, size=int(inner_h * 0.42))
                _draw_cartoon_apple(draw, width // 2 + spacing, c_y, size=int(inner_h * 0.42))
            elif count == 3:
                spacing = int(inner_w * 0.26)
                _draw_cartoon_apple(draw, width // 2 - spacing, c_y + 15, size=int(inner_h * 0.36))
                _draw_cartoon_apple(draw, width // 2, c_y - 25, size=int(inner_h * 0.38))
                _draw_cartoon_apple(draw, width // 2 + spacing, c_y + 15, size=int(inner_h * 0.36))
            else:
                spacing = int(inner_w * 0.22)
                _draw_cartoon_apple(draw, width // 2 - spacing, c_y - 35, size=int(inner_h * 0.32))
                _draw_cartoon_apple(draw, width // 2 + spacing, c_y - 35, size=int(inner_h * 0.32))
                _draw_cartoon_apple(draw, width // 2 - spacing, c_y + 40, size=int(inner_h * 0.32))
                _draw_cartoon_apple(draw, width // 2 + spacing, c_y + 40, size=int(inner_h * 0.32))
        else:
            # Friendly glowing circular character badge
            c_x = (inner_box[0][0] + inner_box[1][0]) // 2
            c_y = inner_y + int(inner_h * 0.48)
            c_r = int(inner_h * 0.34)
            draw.ellipse([(c_x - c_r, c_y - c_r), (c_x + c_r, c_y + c_r)], fill=base_rgb)
            draw.ellipse([(c_x - c_r + 8, c_y - c_r + 8), (c_x + c_r - 8, c_y + c_r - 8)], outline=(255, 255, 255), width=int(width * 0.01))
            
            # If safe_emoji is a single character or symbol, draw it; else star
            emoji_font = _get_font(int(c_r * 0.95), bold=True)
            draw.text((c_x, c_y), safe_emoji if len(safe_emoji) <= 2 else "🌟", font=emoji_font, fill=(255, 255, 255), anchor="mm")

    # 5. Big Title with vibrant color & dynamic auto-fit (no clipping)
    max_title_w = width - 2 * card_margin_x - 60
    title_font, _ = _fit_text(
        draw,
        card.title,
        max_width=max_title_w,
        initial_size=int(height * 0.046),
        min_size=26,
        bold=True,
    )
    title_y = inner_y + inner_h + int(height * 0.055)
    draw.text((width // 2, title_y), card.title, font=title_font, fill=(15, 23, 42), anchor="mm")

    # 6. Subtitle with automatic text wrapping
    if card.subtitle:
        sub_font = _get_font(int(height * 0.026), bold=False)
        sub_lines = textwrap.wrap(card.subtitle, width=32)
        sub_start_y = title_y + int(height * 0.048)
        for idx, line in enumerate(sub_lines[:2]):
            draw.text(
                (width // 2, sub_start_y + idx * int(height * 0.034)),
                line,
                font=sub_font,
                fill=(71, 85, 105),
                anchor="mm",
            )

    # 7. Decorative Bottom Tag (fitted)
    bot_text = "✨ Vừa Học Vừa Chơi • Bé Càng Thêm Thông Minh ✨"
    bot_font, _ = _fit_text(
        draw,
        bot_text,
        max_width=width - 2 * card_margin_x - 40,
        initial_size=int(height * 0.022),
        min_size=16,
        bold=True,
    )
    bot_y = card_bottom - int(height * 0.042)
    draw.text((width // 2, bot_y), bot_text, font=bot_font, fill=base_rgb, anchor="mm")

    img.save(output_path, quality=95)
    return output_path
