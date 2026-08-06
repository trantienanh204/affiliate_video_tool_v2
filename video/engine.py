"""
Video engine orchestrator.

CPU path: storyboard → Ken Burns scenes → compositor → MP4
GPU path: storyboard → ComfyUI I2V per scene → compositor (fallback Ken Burns)
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from core.config import settings, RenderMode
from core.exceptions import ComfyUIError, ProductValidationError, VideoRenderError
from core.logging import get_logger
from models.job import JobResult
from models.product import ProductInput
from models.storyboard import Scene, Storyboard

from ai.llm.analyzer import analyze_and_script
from ai.storyboard.generator import generate_storyboard
from tts.edge import generate_tts
from utils.paths import job_output_dir
from video.compositor import compose_video
from video.kenburns import make_kenburns_clip

logger = get_logger(__name__)

ProgressCb = Optional[Callable[[float, str], None]]


def _progress(cb: ProgressCb, value: float, stage: str) -> None:
    if cb:
        try:
            cb(value, stage)
        except Exception:
            pass
    logger.info("Progress %.0f%% | %s", value * 100, stage)


def _try_gpu_scenes(
    storyboard: Storyboard,
    image_paths: list[Path],
    job_id: str,
    progress_callback: ProgressCb,
) -> list[Path] | None:
    """
    Attempt ComfyUI I2V for each scene.

    Returns list of per-scene video paths, or None if GPU path unavailable
    (caller should fall back to CPU Ken Burns).
    """
    if not settings.comfyui_enabled and settings.render_mode != RenderMode.GPU:
        return None

    try:
        from services.comfyui.client import get_comfyui_client
        from services.comfyui.i2v import render_scene_i2v
    except ImportError as e:
        logger.warning("ComfyUI module import failed: %s", e)
        return None

    client = get_comfyui_client()
    if not client.is_available():
        logger.warning("ComfyUI not reachable → CPU fallback")
        return None

    if not image_paths:
        logger.warning("No images for I2V → CPU fallback")
        return None

    scene_videos: list[Path] = []
    n = max(1, len(storyboard.scenes))

    for i, scene in enumerate(storyboard.scenes):
        frac = 0.55 + 0.30 * (i / n)
        _progress(
            progress_callback,
            frac,
            f"GPU I2V scene {i+1}/{n} ({scene.role})...",
        )
        img = image_paths[scene.image_index % len(image_paths)]
        try:
            clip_path = render_scene_i2v(
                img,
                scene.i2v_prompt or f"Product showcase, {scene.camera}, {scene.location}",
                negative_prompt=scene.negative_prompt,
                duration=min(scene.duration, 5.0),  # keep I2V clips short
                job_id=job_id,
                client=client,
            )
            scene_videos.append(clip_path)
        except ComfyUIError as e:
            logger.warning("I2V scene %s failed (%s) → abort GPU path", scene.scene_id, e.message)
            return None

    return scene_videos


def _compose_from_scene_videos(
    scene_videos: list[Path],
    storyboard: Storyboard,
    audio_path: Path,
    output_path: Path,
) -> Path:
    """Concatenate pre-rendered scene videos + audio (GPU path result)."""
    from moviepy import VideoFileClip, concatenate_videoclips, AudioFileClip

    clips = []
    for p, scene in zip(scene_videos, storyboard.scenes):
        clip = VideoFileClip(str(p))
        # trim / pad to scene duration
        if clip.duration > scene.duration + 0.15:
            clip = clip.subclipped(0, scene.duration)
        clips.append(clip)

    video = concatenate_videoclips(clips, method="compose")
    audio = AudioFileClip(str(audio_path))
    final_dur = min(float(video.duration), float(audio.duration))
    video = video.subclipped(0, final_dur).with_audio(audio.subclipped(0, final_dur))

    video.write_videofile(
        str(output_path),
        fps=settings.video_fps,
        codec="libx264",
        audio_codec="aac",
        threads=4,
        logger=None,
        preset="ultrafast",
        bitrate=settings.video_bitrate,
    )
    video.close()
    audio.close()
    for c in clips:
        c.close()
    return output_path


def render_product(
    product: ProductInput,
    *,
    job_id: Optional[str] = None,
    progress_callback: ProgressCb = None,
) -> JobResult:
    """
    Full pipeline for one product.

    Auto-selects GPU (ComfyUI I2V) when enabled & available, else CPU Ken Burns.
    """
    if not product.name or not product.name.strip():
        raise ProductValidationError("Tên sản phẩm không được để trống")

    jid = job_id or "single"
    out_dir = job_output_dir(jid)

    # 1. AI content
    _progress(progress_callback, 0.10, "Phân tích sản phẩm & viết script...")
    analysis, script = analyze_and_script(product)

    # 2. Storyboard
    _progress(progress_callback, 0.30, "Tạo storyboard multi-scene...")
    storyboard = generate_storyboard(product, analysis, script)

    # 3. TTS
    _progress(progress_callback, 0.45, "Tạo voiceover tiếng Việt...")
    audio_path, audio_dur = generate_tts(
        script.voiceover_text(),
        voice=product.voice,
        job_id=jid,
    )

    # Align scene durations to audio if mismatch is large
    if abs(storyboard.total_duration - audio_dur) > 4:
        scale = audio_dur / max(storyboard.total_duration, 1.0)
        for sc in storyboard.scenes:
            sc.duration = round(max(2.0, sc.duration * scale), 1)
        storyboard.total_duration = sum(s.duration for s in storyboard.scenes)

    image_paths = [Path(p) for p in product.image_paths if p]
    video_path = out_dir / f"video_{jid}.mp4"
    used_mode = "cpu"

    # 4a. Try GPU path
    _progress(progress_callback, 0.55, "Chọn render mode (GPU/CPU)...")
    scene_videos = _try_gpu_scenes(storyboard, image_paths, jid, progress_callback)

    if scene_videos:
        used_mode = "gpu"
        _progress(progress_callback, 0.88, "Ghép các scene I2V...")
        try:
            _compose_from_scene_videos(scene_videos, storyboard, audio_path, video_path)
        except Exception as e:
            logger.warning("GPU compose failed (%s) → CPU fallback", e)
            scene_videos = None
            used_mode = "cpu"

    # 4b. CPU Ken Burns path
    if not scene_videos:
        _progress(progress_callback, 0.60, "Dựng video multi-scene (Ken Burns)...")
        compose_video(
            storyboard,
            image_paths,
            audio_path,
            video_path,
            job_id=jid,
            product_name=product.name,
            category=product.category,
        )

    # 5. Subtitles (optional burn-in)
    final_path = video_path
    if settings.burn_subtitles:
        try:
            from video.subtitle import generate_subtitles, burn_subtitles, write_srt

            _progress(progress_callback, 0.90, "Tạo & gắn phụ đề...")
            segs = generate_subtitles(
                audio_path,
                script_text=script.full_script,
                duration=audio_dur,
            )
            if segs:
                srt_path = out_dir / f"subs_{jid}.srt"
                write_srt(segs, srt_path)
                burned = out_dir / f"video_{jid}_sub.mp4"
                burn_subtitles(video_path, segs, burned)
                final_path = burned
        except Exception as e:
            logger.warning("Subtitle step skipped: %s", e)

    # 6. Background music
    if settings.enable_bgm:
        try:
            from video.music import mix_bgm

            _progress(progress_callback, 0.95, "Mix background music...")
            with_bgm = out_dir / f"video_{jid}_final.mp4"
            mix_bgm(final_path, with_bgm)
            final_path = with_bgm
        except Exception as e:
            logger.warning("BGM step skipped: %s", e)

    _progress(progress_callback, 1.0, "Hoàn tất")

    return JobResult(
        job_id=jid,
        video_path=final_path,
        caption=script.caption,
        script_text=script.full_script,
        duration=float(audio_dur),
        meta={
            "concept": analysis.concept,
            "mood": analysis.mood,
            "scenes": storyboard.scene_count(),
            "usp": analysis.usp,
            "hook": script.hook,
            "cta": script.cta,
            "render_mode": used_mode,
        },
    )
