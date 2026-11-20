"""
edge-tts wrapper – free Vietnamese neural voices.

Returns audio file path + measured duration.
"""

from __future__ import annotations

import asyncio
import re
import subprocess
import tempfile
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
    # Tiếng Việt
    "Nữ dễ thương (Hoài My)": "vi-VN-HoaiMyNeural",
    "Nữ miền Bắc (Hương Hạnh)": "vi-VN-HuongHanhNeural",
    "Nam miền Bắc (Nam Minh)": "vi-VN-NamMinhNeural",
    "Nữ miền Nam (Hoài My)": "vi-VN-HoaiMyNeural",
    # Tiếng Anh (English for Kids & Bilingual)
    "Bé gái Mỹ dễ thương (Ana US - Tiếng Anh)": "en-US-AnaNeural",
    "Nữ phát âm tiếng Anh chuẩn (Jenny US)": "en-US-JennyNeural",
    "Nam phát âm tiếng Anh (Guy US)": "en-US-GuyNeural",
}

DEFAULT_VOICE = "vi-VN-HoaiMyNeural"


def resolve_voice(voice_name_or_id: str) -> str:
    """Accept friendly name or raw voice id."""
    if voice_name_or_id in VOICES:
        return VOICES[voice_name_or_id]
    if any(voice_name_or_id.startswith(prefix) for prefix in ("vi-VN-", "en-US-", "en-GB-")):
        return voice_name_or_id
    for name, vid in VOICES.items():
        if voice_name_or_id.lower() in name.lower() or voice_name_or_id.lower() in vid.lower():
            return vid
    return DEFAULT_VOICE


async def _synthesize(text: str, voice: str, output_path: Path, rate: str = "+0%", volume: str = "+0%") -> None:
    communicate = edge_tts.Communicate(text, voice, rate=rate, volume=volume)
    await communicate.save(str(output_path))


def _split_for_tts(text: str, max_chars: int = 2600) -> list[str]:
    """Split long narration at sentence boundaries for reliable TTS requests."""
    sentences = re.split(r"(?<=[.!?…])\s+|\n+", text.strip())
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        pieces = [sentence]
        if len(sentence) > max_chars:
            words = sentence.split()
            pieces = []
            piece = ""
            for word in words:
                if piece and len(piece) + len(word) + 1 > max_chars:
                    pieces.append(piece)
                    piece = word
                else:
                    piece = f"{piece} {word}".strip()
            if piece:
                pieces.append(piece)
        for piece in pieces:
            if current and len(current) + len(piece) + 1 > max_chars:
                chunks.append(current)
                current = piece
            else:
                current = f"{current} {piece}".strip()
    if current:
        chunks.append(current)
    return chunks or [text.strip()]


async def _synthesize_retry(text: str, voice: str, path: Path, rate: str, volume: str) -> None:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            await _synthesize(text, voice, path, rate=rate, volume=volume)
            if path.is_file() and path.stat().st_size >= 100:
                return
            raise RuntimeError("Edge TTS returned an empty audio chunk")
        except Exception as exc:
            last_error = exc
            if path.exists():
                path.unlink()
            if attempt < 2:
                await asyncio.sleep(0.7 * (attempt + 1))
    raise RuntimeError(f"Edge TTS failed after 3 attempts: {last_error}") from last_error


async def _synthesize_long_text(text: str, voice: str, output_path: Path, rate: str, volume: str) -> None:
    chunks = _split_for_tts(text)
    if len(chunks) == 1:
        await _synthesize_retry(chunks[0], voice, output_path, rate, volume)
        return

    import imageio_ffmpeg

    with tempfile.TemporaryDirectory(prefix="edge_tts_parts_", dir=output_path.parent) as temp_dir:
        part_paths = [Path(temp_dir) / f"part_{index:03d}.mp3" for index in range(len(chunks))]
        for part_text, part_path in zip(chunks, part_paths):
            await _synthesize_retry(part_text, voice, part_path, rate, volume)

        manifest = Path(temp_dir) / "concat.txt"
        manifest.write_text(
            "".join(
                f"file '{str(path.resolve()).replace(chr(92), '/').replace(chr(39), chr(92) + chr(39))}'\n"
                for path in part_paths
            ),
            encoding="utf-8",
        )
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        try:
            subprocess.run(
                [ffmpeg, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(manifest), "-c", "copy", str(output_path)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except Exception as exc:
            detail = getattr(exc, "stderr", "") or str(exc)
            raise RuntimeError(f"Could not join TTS audio chunks: {detail[-500:]}") from exc


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
        asyncio.run(_synthesize_long_text(text.strip(), voice_id, output_path, rate, volume))
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
