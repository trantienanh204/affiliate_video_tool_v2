"""Cloud image-to-video adapter for fal.ai."""

from __future__ import annotations

import os
from pathlib import Path

import httpx

from core.config import settings
from core.exceptions import VideoRenderError
from core.logging import get_logger
from utils.paths import job_output_dir

logger = get_logger(__name__)


def render_image_to_video(
    image_path: Path,
    prompt: str,
    *,
    negative_prompt: str = "",
    job_id: str,
    progress_callback=None,
) -> Path:
    """Generate one short product clip remotely and save it into the job folder."""
    api_key = os.getenv("FAL_KEY", "").strip()
    if not api_key:
        raise VideoRenderError(
            "Chưa có FAL_KEY. Cấu hình API key fal.ai để dùng AI video cloud; dịch vụ tính phí theo giây video."
        )
    image_path = Path(image_path)
    if not image_path.is_file():
        raise VideoRenderError(f"Không tìm thấy ảnh sản phẩm: {image_path}")

    try:
        import fal_client
    except ImportError as e:
        raise VideoRenderError("Thiếu fal-client. Hãy rebuild Docker image sau khi cập nhật requirements.txt.") from e

    try:
        image_url = fal_client.upload_file(str(image_path))
        if progress_callback:
            progress_callback(0.68, "Đã tải ảnh lên fal.ai; đang tạo clip AI...")
        result = fal_client.subscribe(
            settings.fal_model,
            arguments={
                "image_url": image_url,
                "prompt": prompt,
                "negative_prompt": negative_prompt[:500],
                "duration": str(settings.fal_video_duration),
                "resolution": settings.fal_resolution,
                "enable_prompt_expansion": True,
                "enable_safety_checker": True,
            },
            with_logs=False,
        )
        video_url = (result.get("video") or {}).get("url")
        if not video_url:
            raise VideoRenderError(f"fal.ai không trả URL video: {result}")
        response = httpx.get(video_url, timeout=180.0, follow_redirects=True)
        response.raise_for_status()
        out = job_output_dir(job_id) / f"fal_i2v_{job_id}.mp4"
        out.write_bytes(response.content)
        if out.stat().st_size < 10_000:
            raise VideoRenderError("fal.ai trả video rỗng hoặc không hợp lệ")
        return out
    except VideoRenderError:
        raise
    except Exception as e:
        logger.exception("fal.ai image-to-video failed")
        raise VideoRenderError(f"fal.ai không tạo được video: {e}") from e
