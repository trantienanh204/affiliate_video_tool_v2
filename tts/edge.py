"""
edge-tts wrapper – free Vietnamese neural voices.

Returns audio file path + measured duration.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import edge_tts
from moviepy import AudioFileClip

from core.exceptions import TTSError
from core.logging import get_logger
from utils.paths import outputs_dir, job_output_dir

logger = get_logger(__name__)

# Friendly name → edge-tts voice id
VOICES: dict[str, str] = {
    "Nữ dễ thương (Hoài My)": "vi-VN-HoaiMyNeural",
    "Nữ miền Bắc (Hương Hạnh)": "vi-VN-HuongHanhNeural",
    "Nam miền Bắc (Nam Minh)": "vi-VN-NamMinhNeural",
    "Nữ miền Nam (Hoài My)": "vi-VN-HoaiMyNeural",  # alias
}

DEFAULT_VOICE = "vi-VN-HoaiMyNeural"


def resolve_voice(voice_name_or_id: str) -> str:
    """Accept friendly name or raw voice id."""
    if voice_name_or_id in VOICES:
        return VOICES[voice_name_or_id]
    if voice_name_or_id.startswith("vi-VN-"):
        return voice_name_or_id
    return DEFAULT_VOICE


async def _synthesize(text: str, voice: str, output_path: Path, rate: str = "+0%", volume: str = "+0%") -> None:
    communicate = edge_tts.Communicate(text, voice, rate=rate, volume=volume)
    await communicate.save(str(output_path))


def generate_tts(
    text: str,
    *,
    voice: str = DEFAULT_VOICE,
    output_path: Optional[Path] = None,
    job_id: Optional[str] = None,
    rate: str = "+0%",
    volume: str = "+0%",
) -> tuple[Path, float]:
    """
    Generate TTS audio.

    Returns
    -------
    (audio_path, duration_seconds)
    """
    if not text or not text.strip():
        raise TTSError("TTS text is empty")

    voice_id = resolve_voice(voice)

    if output_path is None:
        base = job_output_dir(job_id) if job_id else outputs_dir()
        output_path = base / f"tts_{voice_id.replace('-', '_')}.mp3"

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("TTS start | voice=%s | chars=%d | out=%s", voice_id, len(text), output_path.name)

    try:
        asyncio.run(_synthesize(text.strip(), voice_id, output_path, rate=rate, volume=volume))
    except Exception as e:
        raise TTSError(f"edge-tts failed: {e}", details=str(e)) from e

    if not output_path.is_file() or output_path.stat().st_size < 100:
        raise TTSError("TTS output file missing or too small")

    # Measure real duration
    try:
        clip = AudioFileClip(str(output_path))
        duration = float(clip.duration)
        clip.close()
    except Exception as e:
        logger.warning("Could not measure audio duration: %s", e)
        duration = max(8.0, len(text) / 12.0)  # rough estimate ~12 chars/sec

    logger.info("TTS done | duration=%.2fs", duration)
    return output_path, duration


def list_voices() -> dict[str, str]:
    """Return friendly_name → voice_id mapping for UI."""
    return dict(VOICES)
