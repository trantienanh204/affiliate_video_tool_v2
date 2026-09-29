"""
Video engine orchestrator.

CPU path: storyboard → Ken Burns scenes → compositor → MP4
GPU path: storyboard → ComfyUI I2V per scene → compositor (fallback Ken Burns)
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional
import os

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

logger = get_logger(__name__)

ProgressCb = Optional[Callable[[float, str], None]]


def _progress(cb: ProgressCb, value: float, stage: str) -> None:
    if cb:
        try:
            cb(value, stage)
        except Exception:
            pass
    logger.info("Progress %.0f%% | %s", value * 100, stage)


def _character_video_prompt(product: ProductInput, scene_prompt: str) -> tuple[str, str]:
    """Prompt a fictional animated presenter to demonstrate the referenced item."""
    apparel = product.category.strip().casefold() in {"áo", "quần", "thời trang", "quần áo", "đồ mặc"}
    context = (product.description or product.image_description or "").strip()[:220]
    if apparel:
        positive = (
            "Create a polished, pleasant stylized 3D animated fashion commercial, clearly animated and fictional, "
            "not a real identifiable person. Show one adult character wearing the garment in the reference image. "
            "Keep its visible garment design faithful: same dominant color, neckline, sleeve length, fit and plain/printed pattern; "
            "do not invent logos, words, graphics, seams or accessories on the shirt. The character makes a natural small turn, "
            "takes one relaxed step and smiles; subtle hair and fabric movement, hands stay away from the shirt. "
            "Warm modern boutique or bright lifestyle setting, tasteful colors, soft cinematic light, medium full-body framing "
            "with the shirt always clearly visible. Smooth character animation and gentle scene motion; no zoom-only animation, "
            "no camera shake. No on-screen copy, captions, signs, watermark or UI. "
        )
    else:
        positive = (
            "Create a polished, pleasant stylized 3D animated product commercial with one clearly fictional adult presenter. "
            "The presenter naturally demonstrates or wears the product from the reference; preserve its visible design, color, "
            "shape and markings without adding text or logos. Use a tasteful lifestyle setting, soft cinematic light, "
            "natural small gestures and smooth character animation; no zoom-only animation or camera shake. "
            "No on-screen copy, captions, signs, watermark or UI. "
        )
    positive += f"Product context: {context or product.name}. Scene idea: {scene_prompt[:160]}"
    negative = (
        "photorealistic real person, text, captions, subtitles, watermark, brand logo, extra lettering, UI, "
        "changed shirt color, changed neckline, changed sleeves, changed pattern, added print, melted fabric, "
        "deformed body, extra fingers, fused hands, bad anatomy, camera zoom, camera shake, blurry"
    )
    return positive, negative


def _try_gpu_scenes(
    storyboard: Storyboard,
    image_paths: list[Path],
    job_id: str,
    progress_callback: ProgressCb,
    product: ProductInput,
) -> list[Path] | None:
    """
    Attempt ComfyUI I2V for each scene.

    Returns I2V scene clips. In required mode, unavailable I2V raises an error.
    """
    if not settings.comfyui_enabled and settings.render_mode != RenderMode.GPU:
        if settings.require_ai_video:
            raise ComfyUIError("AI video chưa bật. Đặt AVA_RENDER_MODE=gpu và AVA_COMFYUI_ENABLED=true, sau đó khởi động ComfyUI.")
        return None

    try:
        from services.comfyui.client import get_comfyui_client
        from services.comfyui.i2v import render_scene_i2v
    except ImportError as e:
        logger.warning("ComfyUI module import failed: %s", e)
        if settings.require_ai_video:
            raise ComfyUIError(f"Không nạp được module ComfyUI: {e}") from e
        return None

    client = get_comfyui_client()
    if not client.is_available():
        logger.warning("ComfyUI không truy cập được")
        if settings.require_ai_video:
            raise ComfyUIError(f"Không kết nối được ComfyUI tại {settings.comfyui_url}. Hãy khởi động ComfyUI.")
        return None

    if not image_paths:
        logger.warning("Không có ảnh cho I2V")
        if settings.require_ai_video:
            raise ComfyUIError("AI video cần ít nhất một ảnh sản phẩm.")
        return None

    scene_videos: list[Path] = []
    selected_scenes = storyboard.scenes[:max(1, settings.i2v_max_scenes)]
    n = max(1, len(selected_scenes))

    for i, scene in enumerate(selected_scenes):
        frac = 0.55 + 0.30 * (i / n)
        _progress(
            progress_callback,
            frac,
            f"GPU I2V scene {i+1}/{n} ({scene.role})...",
        )
        img = image_paths[scene.image_index % len(image_paths)]
        prompt, negative = _character_video_prompt(product, scene.i2v_prompt or scene.description)
        try:
            clip_path = render_scene_i2v(
                img,
                prompt,
                negative_prompt=negative,
                duration=min(scene.duration, settings.i2v_scene_duration),
                job_id=job_id,
                client=client,
            )
            scene_videos.append(clip_path)
        except ComfyUIError as e:
            logger.warning("I2V scene %s failed (%s)", scene.scene_id, e.message)
            if settings.require_ai_video:
                raise
            return None

    return scene_videos


def _try_fal_scene(
    storyboard: Storyboard,
    image_paths: list[Path],
    job_id: str,
    progress_callback: ProgressCb,
    product: ProductInput,
) -> list[Path]:
    """Generate one cloud I2V clip to keep cost and generation time bounded."""
    if not image_paths:
        raise VideoRenderError("AI video cần ít nhất một ảnh sản phẩm.")
    if not storyboard.scenes:
        raise VideoRenderError("Storyboard không có cảnh để tạo video.")
    from services.fal_video import render_image_to_video

    scene = storyboard.scenes[0]
    image_path = image_paths[scene.image_index % len(image_paths)]
    _progress(progress_callback, 0.56, "Gửi ảnh và prompt đến dịch vụ AI video...")
    prompt, negative_prompt = _character_video_prompt(product, scene.i2v_prompt or scene.description)
    clip = render_image_to_video(
        image_path,
        prompt,
        negative_prompt=negative_prompt,
        job_id=job_id,
        progress_callback=progress_callback,
    )
    return [clip]


def _try_hf_zero_scene(
    storyboard: Storyboard,
    image_paths: list[Path],
    job_id: str,
    progress_callback: ProgressCb,
    product: ProductInput,
) -> list[Path]:
    """Generate one short product clip using Hugging Face's shared ZeroGPU quota."""
    if not image_paths:
        raise VideoRenderError("AI video cần ít nhất một ảnh sản phẩm.")
    if not storyboard.scenes:
        raise VideoRenderError("Storyboard không có cảnh để tạo video.")
    from services.hf_video import render_image_to_video

    scene = storyboard.scenes[0]
    image_path = image_paths[scene.image_index % len(image_paths)]
    prompt, negative_prompt = _character_video_prompt(product, scene.i2v_prompt or scene.description)
    clip = render_image_to_video(
        image_path,
        prompt,
        negative_prompt=negative_prompt,
        job_id=job_id,
        progress_callback=progress_callback,
    )
    return [clip]


def _run_video_provider(
    provider: str,
    storyboard: Storyboard,
    image_paths: list[Path],
    job_id: str,
    progress_callback: ProgressCb,
    product: ProductInput,
) -> list[Path]:
    """Dispatch one configured provider, keeping provider errors for failover."""
    if provider == "hf_zerogpu":
        return _try_hf_zero_scene(storyboard, image_paths, job_id, progress_callback, product)
    if provider == "fal":
        return _try_fal_scene(storyboard, image_paths, job_id, progress_callback, product)
    if provider == "comfyui":
        clips = _try_gpu_scenes(storyboard, image_paths, job_id, progress_callback, product)
        if not clips:
            raise VideoRenderError("ComfyUI không tạo được cảnh AI.")
        return clips
    raise VideoRenderError(f"Nhà cung cấp video không hợp lệ: {provider}")


def _generate_video_with_fallbacks(
    storyboard: Storyboard,
    image_paths: list[Path],
    job_id: str,
    progress_callback: ProgressCb,
    product: ProductInput,
    *,
    hf_token_invalid: bool = False,
) -> tuple[list[Path] | None, str, list[str]]:
    """Try the primary video backend, then explicitly configured alternatives."""
    configured = [settings.video_provider]
    configured.extend(
        name.strip().lower()
        for name in settings.video_provider_fallbacks.split(",")
        if name.strip()
    )
    providers = list(dict.fromkeys(configured))
    failures: list[str] = []
    video_images = image_paths
    keyframe_ready = not settings.hf_character_enabled or not image_paths
    if settings.hf_character_enabled and image_paths and not hf_token_invalid:
        try:
            from services.hf_character import create_character_keyframe

            keyframe = create_character_keyframe(
                image_paths[0],
                product_name=product.name,
                category=product.category,
                description=product.description or product.image_description,
                job_id=job_id,
                progress_callback=progress_callback,
            )
            video_images = [keyframe]
            keyframe_ready = True
        except Exception as exc:
            message = getattr(exc, "message", str(exc))
            logger.warning("Stylized keyframe unavailable; continue with original product image: %s", message)
            failures.append(f"Qwen keyframe: {message[:180]}")

    for provider in providers:
        if provider == "cpu":
            continue  # AI-video-required mode must never degrade to photo zoom.
        if provider == "hf_zerogpu" and hf_token_invalid:
            failures.append("hf_zerogpu: HF_TOKEN không hợp lệ; đã bỏ qua từ bước kiểm tra sớm")
            continue
        if provider == "hf_zerogpu" and settings.hf_character_enabled and not keyframe_ready:
            failures.append("hf_zerogpu: bỏ qua để tránh xuất clip chụp thật không đúng phong cách hoạt hình")
            continue
        if provider == "fal":
            fal_key = os.getenv("FAL_KEY", "").strip()
            # Avoid accidentally treating an HF token pasted into FAL_KEY as
            # valid; that only causes a slow, confusing auth failure.
            if not fal_key or fal_key.lower().startswith("hf_"):
                failures.append(
                    "fal.ai: chưa có FAL_KEY fal.ai hợp lệ. HF_TOKEN (key Hugging Face) "
                    "không dùng được cho fal.ai; backend fal.ai có thể tính phí"
                )
                continue
        _progress(progress_callback, 0.48, f"Đang thử AI video: {provider}...")
        try:
            return _run_video_provider(provider, storyboard, video_images, job_id, progress_callback, product), provider, failures
        except Exception as exc:
            message = getattr(exc, "message", str(exc))
            logger.warning("Video provider %s failed; trying next configured fallback: %s", provider, message)
            failures.append(f"{provider}: {message[:240]}")
    return None, "", failures


def _compose_from_scene_videos(
    scene_videos: list[Path],
    storyboard: Storyboard,
    audio_path: Path,
    output_path: Path,
    *,
    provider: str | None = None,
) -> Path:
    """Concatenate pre-rendered scene videos + audio (GPU path result)."""
    from moviepy import VideoFileClip, concatenate_videoclips, AudioFileClip, vfx

    clips = []
    scenes = storyboard.scenes[:len(scene_videos)]
    for p, scene in zip(scene_videos, scenes):
        clip = VideoFileClip(str(p))
        # trim / pad to scene duration
        target_duration = (
            float(settings.fal_video_duration)
            if (provider or settings.video_provider) == "fal"
            else min(scene.duration, settings.i2v_scene_duration)
        )
        if clip.duration > target_duration + 0.15:
            clip = clip.subclipped(0, target_duration)
        clips.append(clip)

    video = concatenate_videoclips(clips, method="compose")
    audio = AudioFileClip(str(audio_path))
    final_dur = float(audio.duration)
    if video.duration < final_dur:
        video = video.with_effects([vfx.Loop(duration=final_dur)])
    else:
        video = video.subclipped(0, final_dur)
    video = video.with_audio(audio.subclipped(0, final_dur)).with_duration(final_dur)

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

    Generates AI I2V by default; photo-pan preview requires explicit opt-out.
    """
    if not product.name or not product.name.strip():
        raise ProductValidationError("Tên sản phẩm không được để trống")

    jid = job_id or "single"
    out_dir = job_output_dir(jid)

    configured_video_providers = [settings.video_provider]
    configured_video_providers.extend(
        name.strip().lower()
        for name in settings.video_provider_fallbacks.split(",")
        if name.strip()
    )
    hf_token_invalid = False
    if "hf_zerogpu" in configured_video_providers and os.getenv("HF_TOKEN", "").strip():
        from services.hf_preflight import validate_hf_token

        token_status = validate_hf_token()
        hf_token_invalid = token_status is False
        if hf_token_invalid:
            # Preserve usable fallbacks, but fail before script/TTS work if no
            # alternate backend is actually configured and reachable.
            has_fal_key = bool(os.getenv("FAL_KEY", "").strip()) and not os.getenv("FAL_KEY", "").strip().lower().startswith("hf_")
            comfy_available = False
            if "comfyui" in configured_video_providers and settings.comfyui_enabled:
                try:
                    from services.comfyui.client import get_comfyui_client

                    comfy_available = get_comfyui_client().is_available()
                except Exception:
                    comfy_available = False
            if not (has_fal_key or comfy_available):
                raise VideoRenderError(
                    "HF_TOKEN không hợp lệ hoặc đã bị thu hồi. App đã kiểm tra trước khi phân tích sản phẩm "
                    "và tạo audio/video nên chưa tiêu tốn quota AI. Cập nhật token Hugging Face read trong .env, "
                    "rồi chạy `docker compose up -d --build app`."
                )
        elif token_status is None:
            logger.warning("Could not pre-validate HF_TOKEN; network/API inconclusive, continuing")

    # 1. AI content
    _progress(progress_callback, 0.10, "Phân tích sản phẩm & viết script...")
    analysis, script = analyze_and_script(product)

    # 2. Storyboard
    _progress(progress_callback, 0.30, "Tạo storyboard multi-scene...")
    storyboard = generate_storyboard(product, analysis, script)

    image_paths = [Path(p) for p in product.image_paths if p]
    video_path = out_dir / f"video_{jid}.mp4"
    used_mode = "cpu"

    # 4a. Generate AI video through the selected backend
    _progress(progress_callback, 0.45, "Tạo voiceover và video AI...")
    from concurrent.futures import ThreadPoolExecutor
    pool = ThreadPoolExecutor(max_workers=2)
    tts_future = pool.submit(generate_tts, script.voiceover_text(), voice=product.voice, job_id=jid)
    try:
        scene_videos, used_provider, provider_failures = _generate_video_with_fallbacks(
            storyboard, image_paths, jid, progress_callback, product,
            hf_token_invalid=hf_token_invalid,
        )
    except Exception:
        pool.shutdown(wait=True)
        raise

    if scene_videos:
        used_mode = used_provider
        audio_path, audio_dur = tts_future.result()
        pool.shutdown(wait=True)
        _progress(progress_callback, 0.88, "Ghép các cảnh AI...")
        if image_paths:
            from video.compositor import compose_ai_character_video

            # Every provider uses the same compositor so the uploaded product
            # photo remains intact even if the generative model changes it.
            compose_ai_character_video(
                scene_videos[0],
                audio_path,
                video_path,
            )
        else:
            _compose_from_scene_videos(scene_videos, storyboard, audio_path, video_path, provider=used_provider)

    # 4b. CPU Ken Burns path
    if not scene_videos:
        if settings.require_ai_video:
            pool.shutdown(wait=False, cancel_futures=True)
            detail = " | ".join(provider_failures) or "Không có backend AI video khả dụng."
            raise VideoRenderError(
                "Không tạo được clip AI sau khi thử các backend dự phòng. "
                f"Chi tiết: {detail}. Để có backup tự động, cấu hình FAL_KEY (dịch vụ có thể tính phí) "
                "hoặc bật ComfyUI; không có dịch vụ video miễn phí nào bảo đảm quota luôn sẵn có."
            )
        audio_path, audio_dur = tts_future.result()
        pool.shutdown(wait=True)
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
            "image_analysis": "vision" if product.image_description else ("image_uploaded_but_vision_unavailable" if image_paths else "no_image"),
            "image_description": product.image_description,
        },
    )
