"""Free-quota Hugging Face ZeroGPU image-to-video Space adapter."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import httpx

from core.config import settings
from core.exceptions import VideoRenderError
from core.logging import get_logger
from utils.paths import job_output_dir

logger = get_logger(__name__)


def _save_result_file(value, destination: Path) -> Path:
    """Normalize Gradio FileData/string outputs into a local MP4 file."""
    if isinstance(value, dict):
        value = value.get("path") or value.get("url")
    if not value:
        raise VideoRenderError("Hugging Face Space không trả video đầu ra.")

    source = str(value)
    if source.startswith(("http://", "https://")):
        response = httpx.get(source, timeout=180.0, follow_redirects=True)
        response.raise_for_status()
        destination.write_bytes(response.content)
    else:
        local_path = Path(source)
        if not local_path.is_file():
            raise VideoRenderError(f"Không tải được video từ Hugging Face: {source}")
        shutil.copy2(local_path, destination)
    if destination.stat().st_size < 10_000:
        raise VideoRenderError("Hugging Face Space trả video rỗng hoặc không hợp lệ.")
    return destination


def render_image_to_video(
    image_path: Path,
    prompt: str,
    *,
    negative_prompt: str = "",
    job_id: str,
    progress_callback=None,
) -> Path:
    """Call the public Wan 2.2 ZeroGPU demo; free quota/queue are controlled by HF."""
    image_path = Path(image_path)
    if not image_path.is_file():
        raise VideoRenderError(f"Không tìm thấy ảnh sản phẩm: {image_path}")
    try:
        from gradio_client import Client, handle_file
    except ImportError as e:
        raise VideoRenderError("Thiếu gradio_client. Hãy rebuild Docker image.") from e

    if progress_callback:
        progress_callback(0.60, "Gửi ảnh tới Hugging Face ZeroGPU (quota miễn phí, có thể cần chờ hàng đợi)...")
    try:
        # Gradio 6 renamed Client(hf_token=...) to Client(token=...).
        client = Client(settings.hf_video_space, token=os.getenv("HF_TOKEN") or None, verbose=False)
        result = client.predict(
            handle_file(str(image_path)),
            prompt[:900],
            4,  # fast 4-step preset to minimize ZeroGPU quota consumption
            (negative_prompt or "text, watermark, changed product design, deformed anatomy, blur")[:500],
            settings.hf_video_duration,
            1.0,
            1.0,
            42,  # Space validates the seed even when randomize_seed is enabled.
            True,
            api_name="/generate_video",
        )
        video_value = result[0] if isinstance(result, (tuple, list)) else result
        destination = job_output_dir(job_id) / f"hf_i2v_{job_id}.mp4"
        return _save_result_file(video_value, destination)
    except VideoRenderError:
        raise
    except Exception as e:
        logger.exception("Hugging Face ZeroGPU I2V failed")
        raise VideoRenderError(
            "Hugging Face ZeroGPU không tạo được clip. Space có thể đang bận, hết quota miễn phí, "
            f"hoặc đã đổi API: {e}"
        ) from e
