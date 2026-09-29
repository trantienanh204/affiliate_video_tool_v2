"""
MoviePy compositor: assemble multi-scene clips + text overlays + audio → final video.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter
from moviepy import (
    AudioFileClip,
    CompositeVideoClip,
    ImageClip,
    VideoClip,
    VideoFileClip,
    concatenate_videoclips,
    ColorClip,
    vfx,
)

from core.config import settings
from core.exceptions import VideoRenderError
from core.logging import get_logger
from models.storyboard import Scene, Storyboard
from video.kenburns import make_kenburns_clip

logger = get_logger(__name__)


def compose_ai_character_video(
    ai_video_path: Path | str,
    audio_path: Path | str,
    output_path: Path | str,
) -> Path:
    """Compose an AI-animated hero clip over a soft full-bleed backdrop.

    The generative clip stays visible as the main scene. No product cutout or
    text is pasted over the character; voiceover carries the sales message.
    """
    width = min(settings.video_width, 720)
    height = round(width * 16 / 9)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    audio = AudioFileClip(str(audio_path))
    duration = float(audio.duration)
    source = VideoFileClip(str(ai_video_path)).without_audio()
    source_duration = max(float(source.duration), 0.2)

    def loop_time(t: float) -> float:
        # Ping-pong looping avoids a hard jump at the end of the short I2V clip.
        phase = t % (source_duration * 2)
        sample_t = phase if phase <= source_duration else source_duration * 2 - phase
        return min(sample_t, max(0.0, source_duration - 1.0 / max(settings.video_fps, 1)))

    # Full-bleed, blurred copy of the animated scene provides a coherent canvas.
    def ambient_frame(t: float) -> np.ndarray:
        frame = source.get_frame(loop_time(t))
        backdrop = Image.fromarray(frame.astype(np.uint8)).convert("RGB")
        # Build/blur at half resolution to keep the CPU compositor responsive.
        small_size = (max(1, width // 2), max(1, height // 2))
        scale = max(small_size[0] / backdrop.width, small_size[1] / backdrop.height)
        backdrop = backdrop.resize((round(backdrop.width * scale), round(backdrop.height * scale)), Image.Resampling.BILINEAR)
        left = (backdrop.width - small_size[0]) // 2
        top = (backdrop.height - small_size[1]) // 2
        backdrop = backdrop.crop((left, top, left + small_size[0], top + small_size[1]))
        backdrop = ImageEnhance.Brightness(backdrop.filter(ImageFilter.GaussianBlur(24))).enhance(0.34)
        # Slow ambient color movement gives the loop distinct light and depth.
        glow = Image.new("RGBA", small_size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(glow)
        cx = int(small_size[0] * (0.20 + 0.60 * ((t / 8.0) % 1.0)))
        draw.ellipse((cx - small_size[0], -small_size[1] // 3, cx + small_size[0], small_size[1] // 2), fill=(124, 58, 237, 46))
        glow = glow.filter(ImageFilter.GaussianBlur(45))
        frame = Image.alpha_composite(backdrop.convert("RGBA"), glow).resize((width, height), Image.Resampling.BILINEAR)
        return np.asarray(frame.convert("RGB"), dtype=np.uint8)

    ambient = VideoClip(frame_function=ambient_frame, duration=duration)
    layers = [ambient]

    # Reuse the same generated clip at full width, with a feathered perimeter so
    # the square I2V frame blends into the portrait background instead of looking
    # like a still-image card. The clip shows the animated character/product.
    hero = VideoClip(frame_function=lambda t: source.get_frame(loop_time(t)), duration=duration)
    hero_h = max(1, round(width * source.h / source.w))
    hero = hero.resized(width=width)
    feather = max(18, round(width * 0.065))
    mask = np.ones((hero_h, width), dtype=np.float32)
    fade_x = np.clip(np.arange(width, dtype=np.float32) / feather, 0.0, 1.0)
    fade_y = np.clip(np.arange(hero_h, dtype=np.float32) / feather, 0.0, 1.0)
    mask *= np.minimum(fade_x, fade_x[::-1])[None, :]
    mask *= np.minimum(fade_y, fade_y[::-1])[:, None]
    mask_clip = ImageClip(mask, is_mask=True).with_duration(duration)
    hero = hero.with_mask(mask_clip).with_position(("center", (height - hero_h) // 2))
    layers.append(hero)

    video = CompositeVideoClip(layers, size=(width, height)).with_duration(duration)
    video = video.with_audio(audio.subclipped(0, duration))
    try:
        video.write_videofile(
            str(output), fps=min(settings.video_fps, 15), codec="libx264", audio_codec="aac",
            threads=4, logger=None, preset="ultrafast", bitrate=settings.video_bitrate,
        )
    finally:
        video.close()
        source.close()
        audio.close()
        hero.close()
        mask_clip.close()
        for layer in layers:
            try:
                layer.close()
            except Exception:
                pass
    return output


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

    # Narration carries the message; keep the video image uncluttered.

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
