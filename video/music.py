"""
Background music mixer.

Looks for royalty-free tracks in assets/music/.
If none found, skips BGM silently.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Optional

from core.config import settings
from core.logging import get_logger
from utils.paths import assets_dir

logger = get_logger(__name__)

_AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".ogg", ".aac"}


def list_bgm_tracks() -> list[Path]:
    music_dir = assets_dir() / "music"
    if not music_dir.is_dir():
        return []
    return sorted(
        p for p in music_dir.iterdir()
        if p.suffix.lower() in _AUDIO_EXTS and p.is_file()
    )


def pick_bgm(prefer: Optional[str] = None) -> Optional[Path]:
    tracks = list_bgm_tracks()
    if not tracks:
        return None
    if prefer:
        for t in tracks:
            if prefer.lower() in t.stem.lower():
                return t
    return random.choice(tracks)


def mix_bgm(
    video_path: Path | str,
    output_path: Path | str,
    *,
    bgm_path: Optional[Path | str] = None,
    volume: float | None = None,
) -> Path:
    """
    Mix background music under existing voice audio.

    Returns output path. If no BGM available, copies original video.
    """
    from moviepy import VideoFileClip, AudioFileClip, CompositeAudioClip

    video_path = Path(video_path)
    output_path = Path(output_path)
    volume = volume if volume is not None else settings.bgm_volume

    if not settings.enable_bgm:
        output_path.write_bytes(video_path.read_bytes())
        return output_path

    track = Path(bgm_path) if bgm_path else pick_bgm()
    if track is None or not Path(track).is_file():
        logger.info("No BGM track found in assets/music – skip")
        output_path.write_bytes(video_path.read_bytes())
        return output_path

    clip = VideoFileClip(str(video_path))
    voice = clip.audio
    bgm = AudioFileClip(str(track))

    # Loop or trim BGM to video length
    if bgm.duration < clip.duration:
        from moviepy import concatenate_audioclips
        n = int(clip.duration / bgm.duration) + 1
        bgm = concatenate_audioclips([bgm] * n)
    bgm = bgm.subclipped(0, clip.duration).with_volume_scaled(volume)

    if voice is not None:
        mixed = CompositeAudioClip([voice, bgm])
    else:
        mixed = bgm

    final = clip.with_audio(mixed)
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
    bgm.close()
    logger.info("BGM mixed | track=%s | vol=%.2f", Path(track).name, volume)
    return output_path


def write_music_readme() -> Path:
    path = assets_dir() / "music" / "README.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """# Background Music (royalty-free)

Đặt file nhạc miễn phí bản quyền vào thư mục này (`.mp3`, `.wav`, `.m4a`).

Gợi ý nguồn:
- https://pixabay.com/music/
- https://www.bensound.com/
- https://freemusicarchive.org/

Tool sẽ tự chọn ngẫu nhiên 1 track và mix dưới voiceover (volume mặc định 0.18).
Tắt BGM: `AVA_ENABLE_BGM=false`
""",
        encoding="utf-8",
    )
    return path
