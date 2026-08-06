"""
Subtitle generation + burn-in.

Primary: faster-whisper (if installed)
Fallback: simple timing from script segments (no ASR)
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from core.config import settings
from core.exceptions import SubtitleError
from core.logging import get_logger
from utils.fonts import find_vietnamese_font

logger = get_logger(__name__)


def _transcribe_faster_whisper(audio_path: Path) -> list[dict]:
    """Return list of {start, end, text} using faster-whisper."""
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise SubtitleError(
            "faster-whisper chưa cài. pip install faster-whisper",
            details=str(e),
        ) from e

    model = WhisperModel(
        settings.whisper_model,
        device=settings.whisper_device,
        compute_type="int8" if settings.whisper_device == "cpu" else "float16",
    )
    segments, _info = model.transcribe(str(audio_path), language="vi", beam_size=3)
    result = []
    for seg in segments:
        text = (seg.text or "").strip()
        if text:
            result.append({"start": float(seg.start), "end": float(seg.end), "text": text})
    return result


def _segments_from_script(script_text: str, duration: float) -> list[dict]:
    """Naive split script into timed chunks when ASR unavailable."""
    # Split by sentence-ish delimiters
    import re

    parts = re.split(r"(?<=[!.?…])\s+", script_text.strip())
    parts = [p.strip() for p in parts if p.strip()]
    if not parts:
        return []
    chunk = duration / len(parts)
    segs = []
    for i, p in enumerate(parts):
        segs.append({
            "start": round(i * chunk, 2),
            "end": round(min(duration, (i + 1) * chunk), 2),
            "text": p[:80],
        })
    return segs


def generate_subtitles(
    audio_path: Path | str,
    *,
    script_text: str = "",
    duration: float | None = None,
) -> list[dict]:
    """
    Produce subtitle segments.

    Tries faster-whisper first; falls back to script timing.
    """
    audio_path = Path(audio_path)
    try:
        segs = _transcribe_faster_whisper(audio_path)
        if segs:
            logger.info("Subtitles via faster-whisper: %d segments", len(segs))
            return segs
    except SubtitleError as e:
        logger.warning("ASR unavailable (%s) → script-based subtitles", e.message)
    except Exception as e:
        logger.warning("ASR failed (%s) → script-based subtitles", e)

    if not script_text:
        return []
    dur = duration or 30.0
    segs = _segments_from_script(script_text, dur)
    logger.info("Subtitles via script split: %d segments", len(segs))
    return segs


def write_srt(segments: list[dict], path: Path | str) -> Path:
    """Write SRT file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for i, seg in enumerate(segments, 1):
        def ts(t: float) -> str:
            h = int(t // 3600)
            m = int((t % 3600) // 60)
            s = int(t % 60)
            ms = int((t - int(t)) * 1000)
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

        lines.append(str(i))
        lines.append(f"{ts(seg['start'])} --> {ts(seg['end'])}")
        lines.append(seg["text"])
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def burn_subtitles(
    video_path: Path | str,
    segments: list[dict],
    output_path: Path | str,
) -> Path:
    """
    Burn subtitles onto video with MoviePy TextClip overlays.
    """
    from moviepy import VideoFileClip, TextClip, CompositeVideoClip

    video_path = Path(video_path)
    output_path = Path(output_path)
    if not segments:
        # nothing to burn – copy
        output_path.write_bytes(video_path.read_bytes())
        return output_path

    clip = VideoFileClip(str(video_path))
    w, h = clip.size
    font = find_vietnamese_font()
    overlays = []

    for seg in segments:
        dur = max(0.3, seg["end"] - seg["start"])
        kwargs = dict(
            text=seg["text"][:90],
            font_size=36,
            color="white",
            stroke_color="black",
            stroke_width=2,
            method="caption",
            size=(w - 80, None),
            text_align="center",
        )
        if font:
            kwargs["font"] = font
        try:
            txt = (
                TextClip(**kwargs)
                .with_start(seg["start"])
                .with_duration(dur)
                .with_position(("center", h - 220))
            )
            overlays.append(txt)
        except Exception as e:
            logger.debug("Skip subtitle segment: %s", e)

    final = CompositeVideoClip([clip, *overlays], size=clip.size)
    final = final.with_audio(clip.audio).with_duration(clip.duration)
    final.write_videofile(
        str(output_path),
        fps=settings.video_fps,
        codec="libx264",
        audio_codec="aac",
        threads=4,
        logger=None,
        preset="ultrafast",
        bitrate=settings.video_bitrate,
    )
    final.close()
    clip.close()
    return output_path
