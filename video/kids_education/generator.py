"""Generator pipeline for Kids Education videos (0đ cost, MoviePy 2D/2.5D Ken Burns, Edge-TTS & BGM)."""

from __future__ import annotations

import io
import random
import urllib.parse
from pathlib import Path
from typing import Callable, Optional

import httpx
from PIL import Image

from core.config import settings
from core.logging import get_logger
from tts.edge import generate_tts, resolve_voice
from video.kenburns import make_kenburns_clip
from video.kids_education.canvas import create_flashcard_image
from video.kids_education.presets import KidsCard, get_preset_cards

logger = get_logger(__name__)

ProgressCb = Optional[Callable[[float, str], None]]


def download_or_generate_card_image(card: KidsCard, output_path: Path) -> Path:
    """
    Attempts to download a friendly AI cartoon illustration from Pollinations (0đ).
    Uses randomized seeds, high-res prompts, and user-agent headers.
    Gracefully falls back to procedural cartoon canvas if offline or on network failure.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    center_img: Image.Image | None = None
    seed = random.randint(1000, 999999)
    prompt_full = f"{card.image_prompt}, vibrant cartoon, 3d pixar disney style, cute characters, high quality, soft studio lighting"
    prompt_enc = urllib.parse.quote(prompt_full)
    url = f"https://image.pollinations.ai/prompt/{prompt_enc}?width=768&height=768&nologo=true&seed={seed}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }

    try:
        logger.info("Attempting AI image download for %s (seed=%d)", card.title, seed)
        with httpx.Client(timeout=14.0, headers=headers, follow_redirects=True) as client:
            resp = client.get(url)
            if resp.status_code == 200 and len(resp.content) > 1000:
                center_img = Image.open(io.BytesIO(resp.content))
                logger.info("Downloaded AI illustration for %s (%d bytes)", card.title, len(resp.content))
            else:
                logger.warning("AI image response %s, falling back to canvas", resp.status_code)
    except Exception as e:
        logger.warning("Online image generation timed out or failed for %s (%s); using procedural canvas", card.title, e)
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
    Applies Ken Burns zoom motion + neural speech sync + upbeat cheerful background music.
    """
    from moviepy import (
        AudioFileClip,
        CompositeAudioClip,
        ImageClip,
        concatenate_videoclips,
    )

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
    total_audio_duration = 0.0

    for i, card in enumerate(cards):
        frac = 0.1 + 0.65 * (i / total_cards)
        if progress_cb:
            progress_cb(frac, f"Đang vẽ hình và chuẩn bị thẻ {i + 1}/{total_cards}: {card.title}...")

        card_img_path = temp_dir / f"card_{i:02d}.png"
        download_or_generate_card_image(card, card_img_path)

        audio_clip = None
        duration = 3.8

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
                    duration = max(3.5, measured_dur + 0.8)
            except Exception as exc:
                logger.warning("TTS failed for card %s (%s); proceeding with silent card", card.title, exc)

        total_audio_duration += duration

        # Dynamic Ken Burns animated zoom motion
        try:
            zoom_in = (i % 2 == 0)
            z_start = 1.0 if zoom_in else 1.08
            z_end = 1.08 if zoom_in else 1.0
            clip = make_kenburns_clip(
                card_img_path,
                duration=duration,
                width=540,
                height=960,
                zoom_start=z_start,
                zoom_end=z_end,
                pan_x=0.03 if (i % 2 == 1) else -0.03,
            )
        except Exception as e:
            logger.warning("Ken Burns failed on card %d (%s); falling back to ImageClip", i, e)
            clip = ImageClip(str(card_img_path)).with_duration(duration)

        if audio_clip:
            clip = clip.with_audio(audio_clip)

        clips.append(clip)

    if progress_cb:
        progress_cb(0.80, "Đang hòa âm nhạc nền vui nhộn và xuất video (MoviePy 2.5D)...")

    final_video = concatenate_videoclips(clips, method="compose")

    # Upbeat Cheerful Background Music (BGM)
    bgm_path = settings.project_root / "assets" / "music" / "kids_cheerful.wav"
    bgm_clip = None
    if bgm_path.is_file():
        try:
            raw_bgm = AudioFileClip(str(bgm_path))
            # Loop BGM to match video duration
            loops_needed = int(final_video.duration / raw_bgm.duration) + 1
            loop_list = [raw_bgm] * loops_needed
            from moviepy import concatenate_audioclips
            looped_bgm = concatenate_audioclips(loop_list).subclipped(0, final_video.duration)
            
            # Lower volume for ducking behind voiceover
            bgm_volume = 0.16 if enable_tts else 0.35
            looped_bgm = looped_bgm.with_volume_scaled(bgm_volume)

            if final_video.audio:
                final_audio = CompositeAudioClip([looped_bgm, final_video.audio])
            else:
                final_audio = looped_bgm

            final_video = final_video.with_audio(final_audio)
            bgm_clip = raw_bgm
        except Exception as bgm_err:
            logger.warning("Could not mix BGM: %s", bgm_err)

    # Render MP4
    final_video.write_videofile(
        str(output_path),
        fps=16,
        codec="libx264",
        audio_codec="aac",
        preset="fast",
        logger=None,
    )

    # Clean up clips
    for c in clips:
        try:
            c.close()
        except Exception:
            pass
    if bgm_clip:
        try:
            bgm_clip.close()
        except Exception:
            pass
    try:
        final_video.close()
    except Exception:
        pass

    if progress_cb:
        progress_cb(1.0, "Đã hoàn thành video giáo dục cho bé!")

    return output_path
