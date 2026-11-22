"""
Video engine orchestrator.

CPU path: storyboard -> Ken Burns scenes -> compositor -> MP4
GPU path: storyboard -> ComfyUI I2V per scene -> compositor (fallback Ken Burns)
AI fallback: per-scene provider (HF ZeroGPU / fal.ai / ComfyUI) -> 4-6 clips
             -> compose_ai_scene_clips -> MP4 + audio

PO acceptance (AC1/AC3):
- AI video path now emits 4-6 AI clips per product (one per storyboard scene),
  each clip keeps the same product identity, no clip is a raw repeat of clip 0.
- Final video length is clamped to [30s, 45s] (user override via ProductInput.duration).
"""

from __future__ import annotations

import math
import os
import time
from pathlib import Path
from typing import Callable, Optional

from core.config import settings
from core.exceptions import ProductValidationError, VideoRenderError
from core.logging import get_logger
from models.job import JobResult
from models.script import ScriptPackage
from models.product import ProductInput
from models.storyboard import Storyboard

from ai.llm.analyzer import analyze_and_script
from ai.storyboard.generator import generate_storyboard
from tts.edge import generate_tts
from utils.paths import job_output_dir
from video.compositor import compose_video, compose_ai_scene_clips

logger = get_logger(__name__)

ProgressCb = Optional[Callable[[float, str], None]]


def _progress(cb: ProgressCb, value: float, stage: str) -> None:
    if cb:
        try:
            cb(value, stage)
        except Exception:
            pass
    logger.info("Progress %.0f%% | %s", value * 100, stage)


def _target_scene_count(storyboard: Storyboard) -> int:
    """Number of AI clips to generate for a storyboard.

    PO acceptance: 4-6 AI clips per affiliate video. Storyboard already
    produces 4 scenes (<=25s), 5 scenes (<=40s), 6 scenes (>40s); we cap at
    i2v_max_scenes and never produce fewer than 4 clips for a valid storyboard.
    """
    n = len(storyboard.scenes)
    if n == 0:
        return 0
    max_clips = max(1, settings.i2v_max_scenes)
    if n >= 4:
        return max(4, min(n, max_clips))
    return n




def _render_one_scene(
    provider: str,
    image_path: Path,
    prompt: str,
    scene: object,
    job_id: str,
    progress_callback: ProgressCb,
    product: ProductInput,
) -> Path:
    """Dispatch a single scene to the chosen AI video backend."""
    if provider == "hf_zerogpu":
        from services.hf_video import render_image_to_video

        return render_image_to_video(
            image_path, prompt, job_id=job_id, progress_callback=progress_callback
        )
    if provider == "fal":
        from services.fal_video import render_image_to_video

        return render_image_to_video(
            image_path, prompt, job_id=job_id, progress_callback=progress_callback
        )
    if provider == "comfyui":
        from services.comfyui.i2v import render_scene_i2v

        duration = min(getattr(scene, "duration", 3.0), settings.i2v_scene_duration)
        return render_scene_i2v(image_path, prompt, duration=duration, job_id=job_id)

    raise VideoRenderError(f"Nhà cung cấp video không hợp lệ: {provider}")


def _render_provider_scenes(
    provider: str,
    storyboard: Storyboard,
    image_sources: list[Path],
    job_id: str,
    progress_callback: ProgressCb,
    product: ProductInput,
    n: int,
    failures: list[str],
):
    """Generate up to n AI clips, one per storyboard scene.

    Policy:
      - require_ai_video_active (GPU mode / explicit): any scene failure ->
        the whole provider fails; engine moves to the next provider.
      - Normal CPU mode: a failed scene is skipped and the remaining scenes
        are still composited (best-effort), because the UI always falls back
        to Ken Burns instead of showing a black screen.
    """
    if not image_sources:
        raise VideoRenderError("AI video cần ít nhất một ảnh sản phẩm để tạo chuyển động.")

    scenes = storyboard.scenes[:n]
    clips: list[Path] = []
    scene_failed: list[str] = []
    required = settings.require_ai_video_active

    for scene in scenes:
        try:
            img = image_sources[scene.image_index % len(image_sources)]
            prompt = (getattr(scene, "i2v_prompt", "") or "").strip()
            if not prompt:
                msg = f"Cảnh {getattr(scene, 'scene_id', '?')}: prompt trống, bỏ qua"
                logger.warning(msg)
                scene_failed.append(msg)
                if required:
                    raise VideoRenderError(msg)
                continue
            clip = _render_one_with_retry(
                provider, img, prompt, scene, job_id, progress_callback, product
            )
            clips.append(clip)
            if progress_callback:
                frac = 0.48 + 0.02 * (len(clips) / max(1, n))
                _progress(progress_callback, frac, f"Đang tạo ảnh AI cảnh {len(clips)}/{n}...")
        except Exception as exc:  # noqa: BLE001
            msg = f"Cảnh {getattr(scene, 'scene_id', '?')}: {getattr(exc, 'message', str(exc))[:200]}"
            logger.warning(msg)
            scene_failed.append(msg)
            if required:
                raise
    if clips:
        return clips, scene_failed
    return [], scene_failed


def _generate_video_with_fallbacks(
    storyboard: Storyboard,
    image_paths: list[Path],
    job_id: str,
    progress_callback: ProgressCb,
    product: ProductInput,
    *,
    hf_token_invalid: bool = False,
) -> tuple[list[Path] | None, str, list[str]]:
    """Try the primary AI backend, then the configured alternatives.

    Unlike the previous version (which rendered a single clip and looped it),
    this now renders one clip per storyboard scene: 4-6 clips, each generated
    from the scene's own prompt and image index.
    """
    configured = [settings.video_provider]
    configured.extend(
        name.strip().lower()
        for name in settings.video_provider_fallbacks.split(",")
        if name.strip()
    )
    providers = list(dict.fromkeys(configured))
    failures: list[str] = []

    # Decide which image the AI clips animate.
    #  - HF keyframe (stylized cartoon character) -> the SAME character is reused
    #    across all scenes (consistent presenter), product identity stays in the
    #    prompt so every clip shows the product.
    #  - Otherwise -> the user's product photo is animated directly.
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

    n = _target_scene_count(storyboard)
    if n == 0:
        return None, "", failures

    for provider in providers:
        if provider == "cpu":
            continue
        if provider == "hf_zerogpu" and hf_token_invalid:
            failures.append("hf_zerogpu: HF_TOKEN không hợp lệ; đã bỏ qua từ bước kiểm tra sớm")
            continue
        if provider == "hf_zerogpu" and settings.hf_character_enabled and not keyframe_ready:
            failures.append("hf_zerogpu: bỏ qua để tránh xuất clip chụp thật không đúng phong cách hoạt hình")
            continue
        if provider == "fal":
            fal_key = os.getenv("FAL_KEY", "").strip()
            # HF token pasted into FAL_KEY only causes a slow, confusing auth
            # failure; never mistake it for a valid fal.ai key.
            if not fal_key or fal_key.lower().startswith("hf_"):
                failures.append(
                    "fal.ai: chưa có FAL_KEY fal.ai hợp lệ. HF_TOKEN (key Hugging Face) "
                    "không dùng được cho fal.ai; backend fal.ai có thể tính phí"
                )
                continue

        _progress(progress_callback, 0.45, f"Đang thử AI video (4-6 cảnh): {provider}...")
        try:
            scene_videos, scene_failures = _render_provider_scenes(
                provider,
                storyboard,
                video_images,
                job_id,
                progress_callback,
                product,
                n,
                failures,
            )
            if scene_videos:
                return scene_videos, provider, failures
            failures.extend(scene_failures)
        except Exception as exc:
            message = getattr(exc, "message", str(exc))
            logger.warning("AI video provider %s failed: %s", provider, message)
            failures.append(f"{provider}: {message[:240]}")

    return None, "", failures


def _compose_ai_scene_clips(
    scene_videos: list[Path],
    storyboard: Storyboard,
    audio_path: Path,
    output_path: Path,
    *,
    provider: Optional[str] = None,
    target_duration: Optional[float] = None,
) -> Path:
    """Assemble N AI scene clips + voiceover into a final 9:16 MP4 (30-45s).

    Delegates to video.compositor.compose_ai_scene_clips so the feathered-hero
    composite, concat, 30-45s clamp and closed-clip cleanup live in one place.
    """
    return compose_ai_scene_clips(
        scene_videos,
        storyboard,
        audio_path,
        output_path,
        provider=provider,
        target_duration=target_duration,
    )




def _condense_script(script: ScriptPackage, max_chars: int) -> str:
    """Trim a story down to a narration chunk that fits the render window.

    Keeps the emotional arc (hook -> conflict -> climax -> closing). If the
    full script is already within the budget, return it unchanged. Long story
    is condensed (never duplicated raw) so the video reads a coherent spine.
    """
    full = (script.full_script or "").strip()
    if not full:
        return (script.hook or "").strip()
    if len(full) <= max_chars:
        return full

    hook = (script.hook or "").strip()
    body = (script.body or "").strip()
    cta = (script.cta or "").strip()

    # Drop a repeated lead-in of the hook inside body (if any).
    if hook and body.startswith(hook[:16]):
        space = hook[:16].rfind(" ")
        if space != -1:
            body = body[space + 1:].strip()

    budget = max_chars - len(hook) - (len(cta) if cta else 0)
    budget = max(0, budget)
    if budget <= 0:
        return hook[:max_chars]

    chosen = hook
    if body:
        chunk = body if len(body) <= budget else body[:budget].rstrip()
        chosen = f"{chosen} {chunk}".strip()
    if cta:
        chosen = f"{chosen} {cta}".strip()
    return chosen[:max_chars]


def _normalize_audio_duration(audio_path: Path, target_dur: float, out_path: Path) -> None:
    """Force real TTS audio to exactly *target_dur* seconds (AC3 + AV sync).

    Short narration: loop the track (audio-only; never replicates a visual
    clip). Long narration: trim to *target_dur*. Subtitle always comes from
    this same normalized audio.
    """
    import math

    from moviepy import AudioClip, AudioFileClip, concatenate_audioclips

    src = AudioFileClip(str(audio_path))
    try:
        src_dur = float(src.duration)
    except Exception:
        src.close()
        raise

    out_path.parent.mkdir(parents=True, exist_ok=True)

    if src_dur >= target_dur - 0.05:
        clipped = src.subclipped(0, target_dur).with_duration(target_dur)
        clipped.write_audiofile(str(out_path))
        clipped.close()
        return

    # Short narration: repeat until the window, then trim exactly.
    try:
        looped = concatenate_audioclips(
            [src] * (int(math.ceil(target_dur / max(src_dur, 1e-6))) + 1),
            method="compose", padding=0.0,
        )
    except Exception:
        # Frame-safe wrap: guarantee target_dur seconds of valid frames so that
        # write_audiofile() never reads beyond the source clip (original bug:
        # src.duration < target_dur while metadata claimed otherwise).
        def _wrap_make_frame(t: float):
            return src.get_frame(t % src.duration)

        looped = AudioClip(
            frame_function=_wrap_make_frame,
            duration=target_dur,
            fps=src.fps,
        )
    looped = looped.with_duration(target_dur)
    out = looped.subclipped(0, target_dur)
    out.write_audiofile(str(out_path))
    out.close()


def render_product(
    product: ProductInput,
    *,
    job_id: Optional[str] = None,
    progress_callback: ProgressCb = None,
) -> JobResult:
    """Full pipeline for one product.

    AI video path now produces 4-6 AI clips (per storyboard scene) instead of
    looping a single clip. CPU mode always degrades to Ken Burns preview instead
    of raising when AI backends are unavailable (AC2).
    """
    if not product.name or not product.name.strip():
        raise ProductValidationError("Tên sản phẩm không được để trống")

    jid = job_id or "single"
    out_dir = job_output_dir(jid)
    video_path = out_dir / f"video_{jid}.mp4"

    # Resolve render mode: UI ProductInput field > global settings.
    mode = str(getattr(product, "render_mode", None) or "").lower()
    if mode not in ("cpu", "gpu"):
        mode = "cpu"
    render_mode = mode

    # Affiliate target length must stay inside 30-45s (AC3).
    target_dur = float(product.duration or settings.default_duration)
    target_dur = max(30.0, min(45.0, target_dur))

    # --- Validate HF_TOKEN before starting expensive work (unchanged) ---
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
            has_fal_key = bool(os.getenv("FAL_KEY", "").strip()) and not os.getenv(
                "FAL_KEY", ""
            ).strip().lower().startswith("hf_")
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

    # Narration excerpt for the 30-45s render window: long story is condensed
    # to its spine (hook -> conflict -> climax -> closing), not cut at a hard
    # char-rate boundary, so the voiceover stays coherent.
    narration = _condense_script(script, int(target_dur) * 12)

    # 2. Storyboard 4-6 cảnh, mỗi cảnh có prompt I2V riêng.
    _progress(progress_callback, 0.30, "Tạo storyboard multi-scene...")
    storyboard = generate_storyboard(product, analysis, script)

    image_paths = [Path(p) for p in product.image_paths if p]
    used_mode = "cpu"

    # 3. TTS + AI video chạy song song.
    _progress(progress_callback, 0.45, "Tạo voiceover và video AI...")
    from concurrent.futures import ThreadPoolExecutor

    pool = ThreadPoolExecutor(max_workers=2)
    tts_future = pool.submit(generate_tts, narration, voice=product.voice, job_id=jid)

    try:
        scene_videos, used_provider, provider_failures = _generate_video_with_fallbacks(
            storyboard,
            image_paths,
            jid,
            progress_callback,
            product,
            hf_token_invalid=hf_token_invalid,
        )
    except Exception:
        pool.shutdown(wait=True)
        raise

    # TTS + audio chạy song song với AI; chuẩn hóa audio đến target_dur để
    # subtitle + voiceover luôn khớp (tránh ghép script thu gọn với audio gốc).
    audio_path, audio_dur = tts_future.result()
    _normalize_audio_duration(audio_path, target_dur, out_dir / f"audio_{jid}.mp3")
    audio_path = out_dir / f"audio_{jid}.mp3"
    audio_dur = target_dur

    if scene_videos:
        used_mode = used_provider
        pool.shutdown(wait=True)
        _progress(progress_callback, 0.90, "Ghép các cảnh AI + audio...")
        # AI path always uses the multi-clip composer (no single-clip looping).
        video_path = _compose_ai_scene_clips(
            scene_videos,
            storyboard,
            audio_path,
            video_path,
            provider=used_provider,
            target_duration=target_dur,
        )
    else:
        # AI produced nothing -> fall back to Ken Burns instead of crashing.
        if settings.require_ai_video_active:
            detail = " | ".join(provider_failures) or "Không có backend AI video khả dụng."
            raise VideoRenderError(
                "Không tạo được clip AI sau khi thử các backend dự phòng. "
                f"Chi tiết: {detail}. Để có backup tự động, cấu hình FAL_KEY (dịch vụ có thể tính phí) "
                "hoặc bật ComfyUI; không có dịch vụ video miễn phí nào bảo đảm quota luôn sẵn có."
            )
        _progress(progress_callback, 0.60, "Dựng video multi-scene (Ken Burns preview)...")
        video_path = compose_video(
            storyboard,
            image_paths,
            audio_path,
            video_path,
            job_id=jid,
            product_name=product.name,
            category=product.category,
            target_duration=target_dur,
        )

    # 4. Subtitles (optional burn-in)
    final_path = video_path
    if settings.burn_subtitles:
        try:
            from video.subtitle import generate_subtitles, burn_subtitles, write_srt

            _progress(progress_callback, 0.92, "Tạo & gắn phụ đề...")
            # Subtitle dùng cùng audio thực tế (khớp AV sync), không ghép
            # script gốc câu chuyện.
            if narration != script.full_script:
                logger.info("Narration condensed from %d to %d chars for %ds render",
                            len(script.full_script), len(narration), target_dur)
            segs = generate_subtitles(
                audio_path,
                script_text=narration,
                duration=audio_dur,
            )
            if segs:
                srt_path = out_dir / f"subs_{jid}.srt"
                write_srt(segs, srt_path)
                burned = out_dir / f"video_{jid}_sub.mp4"
                burn_subtitles(video_path, segs, burned)
                final_path = burned
        except Exception as e:  # noqa: BLE001
            logger.warning("Subtitle step skipped: %s", e)

    # 5. Background music
    if settings.enable_bgm:
        try:
            from video.music import mix_bgm

            _progress(progress_callback, 0.96, "Mix background music...")
            with_bgm = out_dir / f"video_{jid}_final.mp4"
            mix_bgm(final_path, with_bgm)
            final_path = with_bgm
        except Exception as e:  # noqa: BLE001
            logger.warning("BGM step skipped: %s", e)

    _progress(progress_callback, 1.0, "Hoàn tất")

    return JobResult(
        job_id=jid,
        video_path=final_path,
        caption=script.caption,
        script_text=script.full_script,
        duration=final_dur,
        meta={
            "concept": analysis.concept,
            "mood": analysis.mood,
            "scenes": storyboard.scene_count(),
            "usp": analysis.usp,
            "hook": script.hook,
            "cta": script.cta,
            "render_mode": render_mode,
            "provider": used_mode,
            "ai_clips": len(scene_videos) if scene_videos else 0,
            "image_analysis": "vision" if product.image_description else ("image_uploaded_but_vision_unavailable" if image_paths else "no_image"),
            "image_description": product.image_description,
            "story_words": len(script.full_script.split()) if script.full_script else 0,
            "narration_words": len(narration.split()),
            "narration_chars": len(narration),
        },
    )
