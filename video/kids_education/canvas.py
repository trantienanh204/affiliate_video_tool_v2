"""Procedural flashcard canvas generator using Pillow (100% offline, zero-cost)."""

from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from video.kids_education.presets import KidsCard


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


def create_flashcard_image(
    card: KidsCard,
    output_path: Path,
    width: int = 1080,
    height: int = 1920,
    center_image: Image.Image | None = None,
) -> Path:
    """
    Renders a colorful, kid-friendly educational flashcard.
    If center_image is provided, it is composed in the card center.
    Otherwise, a cute procedural decorative graphic with landscape, clouds & emoji is drawn.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    base_rgb = _hex_to_rgb(card.theme_color)

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

    # 3. Category / Tag Pill
    pill_w = int(width * 0.52)
    pill_h = int(height * 0.055)
    pill_x1 = (width - pill_w) // 2
    pill_y1 = card_top + int(height * 0.025)
    draw.rounded_rectangle(
        [(pill_x1, pill_y1), (pill_x1 + pill_w, pill_y1 + pill_h)],
        radius=pill_h // 2,
        fill=base_rgb,
    )
    tag_font = _get_font(int(height * 0.025), bold=True)
    draw.text(
        (width // 2, pill_y1 + pill_h // 2),
        "🌟 BÉ VUI HỌC MỖI NGÀY 🌟",
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

    if center_image:
        try:
            resized_center = center_image.convert("RGB").resize((inner_w, inner_h), Image.Resampling.LANCZOS)
            img.paste(resized_center, (inner_x, inner_y))
            draw.rectangle(inner_box, outline=base_rgb, width=int(width * 0.01))
        except Exception:
            center_image = None

    if center_image is None:
        # Cute procedural cartoon landscape (Sky + Hills + Big Emoji)
        draw.rounded_rectangle(inner_box, radius=int(width * 0.04), fill=(224, 242, 254), outline=base_rgb, width=int(width * 0.01))
        
        # Sun in corner
        sun_x, sun_y, sun_r = inner_x + int(inner_w * 0.85), inner_y + int(inner_h * 0.22), int(inner_h * 0.16)
        draw.ellipse([(sun_x - sun_r, sun_y - sun_r), (sun_x + sun_r, sun_y + sun_r)], fill=(254, 240, 138))

        # Green rolling hill at bottom
        hill_top = inner_y + int(inner_h * 0.72)
        draw.ellipse([(inner_x - 50, hill_top), (inner_x + inner_w + 50, inner_y + inner_h + 80)], fill=(134, 239, 172))

        # Big central glowing circle for Character / Emoji
        c_x = (inner_box[0][0] + inner_box[1][0]) // 2
        c_y = inner_y + int(inner_h * 0.48)
        c_r = int(inner_h * 0.36)
        draw.ellipse([(c_x - c_r, c_y - c_r), (c_x + c_r, c_y + c_r)], fill=base_rgb)
        draw.ellipse([(c_x - c_r + 8, c_y - c_r + 8), (c_x + c_r - 8, c_y + c_r - 8)], outline=(255, 255, 255), width=int(width * 0.01))

        # Draw Emoji / Icon symbol large
        emoji_font = _get_font(int(c_r * 1.05), bold=True)
        draw.text((c_x, c_y), card.emoji or "🌟", font=emoji_font, fill=(255, 255, 255), anchor="mm")

    # 5. Big Title with vibrant color
    title_y = inner_y + inner_h + int(height * 0.055)
    title_font = _get_font(int(height * 0.052), bold=True)
    draw.text((width // 2, title_y), card.title, font=title_font, fill=(15, 23, 42), anchor="mm")

    # 6. Subtitle / Phonetic / Meaning
    if card.subtitle:
        sub_y = title_y + int(height * 0.065)
        sub_font = _get_font(int(height * 0.028), bold=False)
        draw.text((width // 2, sub_y), card.subtitle, font=sub_font, fill=(71, 85, 105), anchor="mm")

    # 7. Decorative Bottom Tag
    bot_y = card_bottom - int(height * 0.045)
    bot_font = _get_font(int(height * 0.024), bold=True)
    draw.text((width // 2, bot_y), "✨ Vừa Học Vừa Chơi • Bé Càng Thêm Thông Minh ✨", font=bot_font, fill=base_rgb, anchor="mm")

    img.save(output_path, quality=95)
    return output_path
