"""Generator pipeline for Kids Education videos (0đ cost, MoviePy 2D/2.5D Animation, Edge-TTS & BGM).

All character images are now drawn 100% procedurally (PIL) — no external image APIs needed.
This guarantees visual relevance: rabbit card → draws a kawaii rabbit, bear card → draws a bear, etc.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from core.config import settings
from core.logging import get_logger
from tts.edge import generate_tts, resolve_voice
from video.kids_education.animation import make_kids_animated_scene_clip
from video.kids_education.canvas import create_flashcard_image
from video.kids_education.presets import KidsCard, get_preset_cards

logger = get_logger(__name__)

ProgressCb = Optional[Callable[[float, str], None]]


def acquire_card_character_image(card: KidsCard) -> None:
    """Deprecated: character images are now drawn procedurally inside make_kids_animated_scene_clip.
    Kept for backward compatibility — always returns None."""
    return None


def download_or_generate_card_image(
    card: KidsCard,
    output_path: Path,
    center_image=None,
) -> Path:
    """
    Renders a static flashcard image for poster/thumbnail preview (thumbnail only).
    Characters are drawn procedurally inside the animation engine.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return create_flashcard_image(card, output_path, center_image=None)


def render_kids_education_video(
    cards_or_preset_id: list[KidsCard] | str,
    output_path: Path,
    voice_name: str = "vi-VN-HoaiMyNeural",
    enable_tts: bool = True,
    progress_cb: ProgressCb = None,
) -> Path:
    """
    Composes a multi-scene Kids Education animation video (9:16 format) using MoviePy.
    Each scene features lively 2D/2.5D cartoon animation (hopping character, rotating sun,
    drifting clouds, popping counting items, and synchronized spoken subtitles) + upbeat BGM.
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
            progress_cb(frac, f"Đang tạo hoạt hình chuyển động cảnh {i + 1}/{total_cards}: {card.title}...")

        # 1. Save thumbnail / poster preview (procedural, no external fetch)
        card_img_path = temp_dir / f"card_{i:02d}.png"
        download_or_generate_card_image(card, card_img_path)

        # 3. Audio & Duration
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

        # 2. Living 2D/2.5D Animated Cartoon Scene (kawaii procedural character, rotating sun, drifting clouds, popping items, subtitles)
        try:
            clip = make_kids_animated_scene_clip(
                card=card,
                duration=duration,
                width=540,
                height=960,
            )
        except Exception as e:
            logger.warning("Animation failed on card %d (%s); falling back to static poster", i, e)
            clip = ImageClip(str(card_img_path)).with_duration(duration)

        if audio_clip:
            clip = clip.with_audio(audio_clip)

        clips.append(clip)

    if progress_cb:
        progress_cb(0.80, "Đang hòa âm nhạc nền vui nhộn và kết xuất video hoạt hình...")

    final_video = concatenate_videoclips(clips, method="compose")

    # Upbeat Cheerful Background Music (BGM)
    bgm_path = settings.project_root / "assets" / "music" / "kids_cheerful.wav"
    bgm_clip = None
    if bgm_path.is_file():
        try:
            raw_bgm = AudioFileClip(str(bgm_path))
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
        progress_cb(1.0, "Đã hoàn thành video hoạt hình cho bé!")

    return output_path
