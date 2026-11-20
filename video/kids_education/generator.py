"""Generator pipeline for Kids Education videos (0đ cost, MoviePy 2D/2.5D Ken Burns, Edge-TTS & BGM)."""

from __future__ import annotations

import io
import random
import re
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


def _extract_cartoon_keyword(prompt: str, title: str) -> str:
    """Extracts targeted keyword for public domain clipart / cartoon search."""
    combined = f"{title} {prompt}".lower()
    mapping = [
        (["rabbit", "bunny", "thỏ"], "cartoon rabbit"),
        (["apple", "táo"], "cartoon apple"),
        (["bear", "gấu"], "cartoon bear"),
        (["monkey", "khỉ"], "cartoon monkey"),
        (["cat", "mèo", "kitten"], "cartoon cat"),
        (["dog", "cún", "chó", "puppy"], "cartoon puppy"),
        (["elephant", "voi"], "cartoon elephant"),
        (["lion", "sư tử"], "cartoon lion"),
        (["police", "cảnh sát"], "cartoon police car"),
        (["fire truck", "cứu hoả", "cứu hỏa"], "cartoon fire truck"),
        (["car", "xe", "ô tô"], "cartoon car"),
        (["train", "tàu hỏa"], "cartoon train"),
        (["rainbow", "cầu vồng"], "cartoon rainbow"),
        (["sun", "mặt trời"], "cartoon smiling sun"),
    ]
    for words, target in mapping:
        if any(w in combined for w in words):
            return target
    clean = re.sub(r"[^a-zA-Z0-9 ]", " ", prompt).split()
    return f"cartoon {clean[0]}" if clean else "cartoon character"


def _fetch_wikimedia_cartoon(keyword: str) -> Optional[Image.Image]:
    """Fetches a free, high-resolution public domain cartoon illustration from Wikimedia Commons."""
    headers = {
        "User-Agent": "KidsEducationVideoBot/1.0 (https://github.com/kidsapp; contact@example.com)"
    }
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": f"{keyword} filetype:bitmap|drawing",
        "gsrnamespace": 6,
        "prop": "imageinfo",
        "iiprop": "url",
        "iiurlwidth": 600,
        "format": "json",
        "gsrlimit": 4,
    }
    try:
        with httpx.Client(timeout=7.0, headers=headers, follow_redirects=True) as client:
            resp = client.get("https://commons.wikimedia.org/w/api.php", params=params)
            if resp.status_code == 200:
                pages = resp.json().get("query", {}).get("pages", {})
                for pid, val in pages.items():
                    thumb = val.get("imageinfo", [{}])[0].get("thumburl")
                    if thumb:
                        img_resp = client.get(thumb)
                        if img_resp.status_code == 200 and len(img_resp.content) > 5000:
                            img = Image.open(io.BytesIO(img_resp.content))
                            logger.info("Found Wikimedia cartoon for '%s' (%d bytes, %s)", keyword, len(img_resp.content), img.size)
                            return img
    except Exception as e:
        logger.warning("Wikimedia search failed for '%s': %s", keyword, e)
    return None


def _fetch_pollinations_ai(prompt: str) -> Optional[Image.Image]:
    """Attempts fast AI generation from Pollinations (0đ, short timeout)."""
    seed = random.randint(1000, 999999)
    prompt_full = f"{prompt}, vibrant cartoon clipart, 3d pixar disney style, cute, white background"
    prompt_enc = urllib.parse.quote(prompt_full)
    url = f"https://image.pollinations.ai/prompt/{prompt_enc}?width=512&height=512&nologo=true&seed={seed}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    try:
        with httpx.Client(timeout=4.5, headers=headers, follow_redirects=True) as client:
            resp = client.get(url)
            if resp.status_code == 200 and len(resp.content) > 1000:
                return Image.open(io.BytesIO(resp.content))
    except Exception as e:
        logger.debug("Pollinations AI skipped (%s)", e)
    return None


def download_or_generate_card_image(card: KidsCard, output_path: Path) -> Path:
    """
    Acquires a relevant, kid-friendly cartoon illustration via:
    1. Wikimedia Commons public domain cartoon clipart (free, instant, 0đ, no rate limit)
    2. Fast Pollinations AI attempt (short timeout)
    3. High-resolution procedural kawaii illustration in canvas.py (offline, guaranteed zero-fail)
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    keyword = _extract_cartoon_keyword(card.image_prompt, card.title)
    center_img = _fetch_wikimedia_cartoon(keyword)

    if center_img is None:
        center_img = _fetch_pollinations_ai(card.image_prompt)

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
