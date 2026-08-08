"""
MoviePy compositor: assemble multi-scene clips + text overlays + audio → final video.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from moviepy import (
    AudioFileClip,
    CompositeVideoClip,
    TextClip,
    concatenate_videoclips,
    ColorClip,
)

from core.config import settings
from core.exceptions import VideoRenderError
from core.logging import get_logger
from models.storyboard import Scene, Storyboard
from utils.fonts import find_vietnamese_font
from video.kenburns import make_kenburns_clip

logger = get_logger(__name__)


def _make_text(
    txt: str,
    *,
    fontsize: int = 44,
    color: str = "white",
    stroke: bool = True,
    width: int | None = None,
) -> TextClip:
    w = width or settings.video_width
    font = find_vietnamese_font()
    kwargs = dict(
        text=str(txt)[:120],
        font_size=fontsize,
        color=color,
        method="caption",
        size=(w - 120, None),
        text_align="center",
    )
    if font:
        kwargs["font"] = font
    if stroke:
        kwargs["stroke_color"] = "black"
        kwargs["stroke_width"] = 3
    try:
        return TextClip(**kwargs)
    except Exception:
        kwargs.pop("stroke_color", None)
        kwargs.pop("stroke_width", None)
        try:
            return TextClip(**kwargs)
        except Exception as e:
            logger.warning("TextClip failed: %s", e)
            return TextClip(
                text=str(txt)[:40],
                font_size=fontsize,
                color=color,
                method="caption",
                size=(w - 120, None),
            )


def _scene_clip(
    scene: Scene,
    image_paths: list[Path],
    *,
    width: int,
    height: int,
    product_name: str = "",
    category: str = "",
) -> CompositeVideoClip:
    """Render one storyboard scene (Ken Burns or rich placeholder + text)."""
    img: Optional[Path] = None
    if image_paths:
        idx = scene.image_index % len(image_paths)
        img = image_paths[idx]

    # Stronger, distinct motion per role so multi-image feels like different shots
    # (This is still photo-motion, NOT neural I2V — best free option without GPU)
    motion = {
        "hook":        (1.0, 1.18, 0.15, -0.55),   # punch-in + slight up
        "closeup":     (1.08, 1.22, -0.35, -0.25), # tight crop, drift left
        "detail":      (1.12, 1.28, 0.45, 0.20),   # extreme zoom on detail
        "showcase":    (1.0, 1.14, -0.50, 0.10),   # wide pan across product
        "lifestyle":   (1.15, 1.0, 0.55, -0.15),   # zoom-out reveal
        "social_proof":(1.02, 1.12, 0.0, 0.40),    # slow rise
        "cta":         (1.0, 1.16, 0.0, 0.30),     # settle on CTA
    }
    z0, z1, pan_x, pan_y = motion.get(scene.role, (1.0, 1.12, -0.2, 0.1))

    base = make_kenburns_clip(
        img,
        scene.duration,
        width=width,
        height=height,
        zoom_start=z0,
        zoom_end=z1,
        pan_x=pan_x,
        pan_y=pan_y,
        role=scene.role,
        product_name=product_name,
        location=scene.location,
        category=category,
    )

    layers = [base]

    # When we have a real image, burn text overlay on top.
    # When placeholder: card already has product name – still add hook/cta for emphasis.
    if scene.text_overlay:
        if scene.role == "hook":
            fs, col, y = 52, "white", 100
        elif scene.role == "cta":
            fs, col, y = 46, "#FBBF24", height - 280
        else:
            fs, col, y = 40, "#F1F5F9", 140

        # If no image, push overlay lower so it doesn't clash with card center
        if not img and scene.role not in ("cta",):
            y = height - 320

        try:
            txt = (
                _make_text(scene.text_overlay, fontsize=fs, color=col)
                .with_duration(scene.duration)
                .with_position(("center", y))
            )
            layers.append(txt)
        except Exception as e:
            logger.warning("Overlay failed for scene %s: %s", scene.scene_id, e)

    return CompositeVideoClip(layers, size=(width, height)).with_duration(scene.duration)


def compose_video(
    storyboard: Storyboard,
    image_paths: list[Path | str],
    audio_path: Path | str,
    output_path: Path | str,
    *,
    job_id: Optional[str] = None,
    product_name: str = "",
    category: str = "",
) -> Path:
    """
    Assemble all scenes + audio into final 9:16 MP4.
    """
    w = settings.video_width
    h = settings.video_height
    paths = [Path(p) for p in image_paths if p]
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    logger.info(
        "Compose start | scenes=%d | images=%d | audio=%s | product=%s",
        storyboard.scene_count(),
        len(paths),
        Path(audio_path).name,
        product_name or "?",
    )

    try:
        audio = AudioFileClip(str(audio_path))
        audio_dur = float(audio.duration)
    except Exception as e:
        raise VideoRenderError(f"Cannot load audio: {e}") from e

    scene_clips = []
    for scene in storyboard.scenes:
        try:
            clip = _scene_clip(
                scene,
                paths,
                width=w,
                height=h,
                product_name=product_name,
                category=category,
            )
            scene_clips.append(clip)
        except Exception as e:
            logger.error("Scene %s render failed: %s", scene.scene_id, e)
            scene_clips.append(
                ColorClip(size=(w, h), color=(30, 30, 50)).with_duration(scene.duration)
            )

    if not scene_clips:
        raise VideoRenderError("No scene clips produced")

    transition = (storyboard.transition or "crossfade").lower()
    try:
        if transition == "crossfade" and len(scene_clips) > 1:
            fade = 0.3
            video = concatenate_videoclips(scene_clips, method="compose", padding=-fade)
        else:
            video = concatenate_videoclips(scene_clips, method="compose")
    except Exception as e:
        logger.warning("Crossfade concat failed (%s) → hard cut", e)
        video = concatenate_videoclips(scene_clips, method="compose")

    video_dur = float(video.duration)
    final_dur = min(max(audio_dur, 8.0), max(video_dur, audio_dur))
    if video_dur < final_dur - 0.2:
        pad = ColorClip(size=(w, h), color=(20, 20, 35)).with_duration(final_dur - video_dur)
        video = concatenate_videoclips([video, pad], method="compose")
    elif video_dur > final_dur + 0.2:
        video = video.subclipped(0, final_dur)

    video = video.with_audio(audio).with_duration(final_dur)

    logger.info("Writing video → %s (%.1fs)", out.name, final_dur)
    try:
        video.write_videofile(
            str(out),
            fps=settings.video_fps,
            codec="libx264",
            audio_codec="aac",
            threads=4,
            logger=None,
            preset="ultrafast",
            bitrate=settings.video_bitrate,
        )
    except Exception as e:
        raise VideoRenderError(f"write_videofile failed: {e}") from e
    finally:
        try:
            video.close()
            audio.close()
            for c in scene_clips:
                c.close()
        except Exception:
            pass

    if not out.is_file():
        raise VideoRenderError("Output video file was not created")

    logger.info("Compose done | %s | size=%.1f MB", out.name, out.stat().st_size / 1e6)
    return out
