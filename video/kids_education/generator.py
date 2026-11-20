"""Generator pipeline for Kids Education videos (0đ cost, MoviePy 2D/2.5D, Edge-TTS)."""

from __future__ import annotations

import io
import urllib.parse
from pathlib import Path
from typing import Callable, Optional

import httpx
from PIL import Image

from core.config import settings
from core.logging import get_logger
from tts.edge import generate_tts, resolve_voice
from video.kids_education.canvas import create_flashcard_image
from video.kids_education.presets import KidsCard, get_preset_cards

logger = get_logger(__name__)

ProgressCb = Optional[Callable[[float, str], None]]


def download_or_generate_card_image(card: KidsCard, output_path: Path) -> Path:
    """
    Attempts to download a friendly AI cartoon illustration from Pollinations (0đ).
    Gracefully falls back to procedural canvas if offline or on network failure.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    center_img: Image.Image | None = None
    try:
        # 0-cost free cartoon image generation API
        prompt_enc = urllib.parse.quote(card.image_prompt)
        url = f"https://image.pollinations.ai/prompt/{prompt_enc}?width=768&height=768&nologo=true&seed=42"
        logger.info("Attempting AI image download for %s: %s", card.title, url[:80])
        with httpx.Client(timeout=6.0) as client:
            resp = client.get(url)
            if resp.status_code == 200 and len(resp.content) > 1000:
                center_img = Image.open(io.BytesIO(resp.content))
                logger.info("Downloaded AI illustration for %s (%d bytes)", card.title, len(resp.content))
    except Exception as e:
        logger.warning("Online image generation unavailable for %s (%s); using offline procedural canvas", card.title, e)
        center_img = None

    return create_flashcard_image(card, output_path, center_image=center_img)


def render_kids_education_video(
    cards_or_preset_id: list[KidsCard] | str,
    output_path: Path,
    voice_name: str = "vi-VN-HoaiMyNeural",
    enable_tts: bool = True,
    progress_cb: ProgressCb = None,
) -> Path:
    """
    Composes a multi-card Kids Education video (9:16 format) using MoviePy.
    Synchronizes card duration with neural pronunciation audio (0đ).
    """
    from moviepy import AudioFileClip, ImageClip, concatenate_videoclips

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if isinstance(cards_or_preset_id, str):
        cards = get_preset_cards(cards_or_preset_id)
    else:
        cards = list(cards_or_preset_id)

    if not cards:
        raise ValueError("Danh sách thẻ học giáo dục không được để trống.")

    temp_dir = output_path.parent / "kids_assets"
    temp_dir.mkdir(parents=True, exist_ok=True)

    clips = []
    total_cards = len(cards)

    for i, card in enumerate(cards):
        frac = 0.1 + 0.7 * (i / total_cards)
        if progress_cb:
            progress_cb(frac, f"Đang chuẩn bị thẻ học {i + 1}/{total_cards}: {card.title}...")

        card_img_path = temp_dir / f"card_{i:02d}.png"
        download_or_generate_card_image(card, card_img_path)

        audio_clip = None
        duration = 3.5

        if enable_tts:
            card_audio_path = temp_dir / f"audio_{i:02d}.mp3"
            try:
                voice_id = resolve_voice(voice_name)
                audio_path, measured_dur = generate_tts(
                    card.spoken_text,
                    voice=voice_id,
                    output_path=card_audio_path,
                )
                if audio_path and Path(audio_path).is_file():
                    audio_clip = AudioFileClip(str(audio_path))
                    duration = max(3.0, measured_dur + 0.6)
            except Exception as exc:
                logger.warning("TTS failed for card %s (%s); proceeding with silent card", card.title, exc)

        img_clip = ImageClip(str(card_img_path)).with_duration(duration)
        if audio_clip:
            img_clip = img_clip.with_audio(audio_clip)

        clips.append(img_clip)

    if progress_cb:
        progress_cb(0.85, "Đang kết xuất video giáo dục hoàn chỉnh (MoviePy 2.5D)...")

    final_video = concatenate_videoclips(clips, method="compose")

    # Render MP4
    final_video.write_videofile(
        str(output_path),
        fps=16,
        codec="libx264",
        audio_codec="aac" if enable_tts else None,
        preset="fast",
        logger=None,
    )

    # Clean up clips
    for c in clips:
        try:
            c.close()
        except Exception:
            pass
    try:
        final_video.close()
    except Exception:
        pass

    if progress_cb:
        progress_cb(1.0, "Đã hoàn thành video giáo dục cho bé!")

    return output_path
