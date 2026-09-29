"""Create a stylized fictional product-presenter keyframe on Hugging Face."""

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


def _save_image(value, destination: Path) -> Path:
    if isinstance(value, (tuple, list)):
        value = value[0] if value else None
    if isinstance(value, dict):
        value = value.get("path") or value.get("url")
    if not value:
        raise VideoRenderError("Qwen Image không trả ảnh keyframe.")
    source = str(value)
    if source.startswith(("http://", "https://")):
        response = httpx.get(source, timeout=180.0, follow_redirects=True)
        response.raise_for_status()
        destination.write_bytes(response.content)
    else:
        path = Path(source)
        if not path.is_file():
            raise VideoRenderError("Không tìm thấy ảnh keyframe trả về từ Qwen Image.")
        shutil.copy2(path, destination)
    if destination.stat().st_size < 10_000:
        raise VideoRenderError("Qwen Image trả ảnh keyframe rỗng hoặc không hợp lệ.")
    return destination


def create_character_keyframe(
    image_path: Path,
    *,
    product_name: str,
    category: str,
    description: str = "",
    job_id: str,
    progress_callback=None,
) -> Path:
    """Restyle a product reference into a clean animated-commercial keyframe."""
    image_path = Path(image_path)
    if not image_path.is_file():
        raise VideoRenderError(f"Không tìm thấy ảnh sản phẩm: {image_path}")
    try:
        from gradio_client import Client, handle_file
    except ImportError as exc:
        raise VideoRenderError("Thiếu gradio_client cho bước tạo hình nhân vật.") from exc

    apparel = category.strip().casefold() in {"áo", "quần", "thời trang", "quần áo", "đồ mặc"}
    if apparel:
        prompt = (
            "Edit the input into one polished, attractive 3D animated fashion-advertisement keyframe. "
            "Show a fictional adult woman character, not a real identifiable person, wearing the same garment "
            "as the reference. Carefully preserve the garment's dominant color, crew neckline, short sleeves, "
            "fit, plain fabric and visible construction; keep it blank with no logo, print, lettering or new pattern. "
            "Pair it with simple light blue jeans. Full-body portrait 9:16 composition, natural proportions, "
            "relaxed friendly pose, modern bright boutique, warm soft light, tasteful clean color palette, "
            "high-quality stylized 3D animation, appealing commercial art direction. Remove any watermark or "
            "text visible in the reference. No captions, typography, logo, UI, frame or collage. "
        )
    else:
        prompt = (
            "Edit the input into one polished, attractive 3D animated product-advertisement keyframe. "
            "Show a fictional adult presenter naturally demonstrating the same product. Preserve its visible "
            "shape, color and construction. Use a bright, tasteful lifestyle setting, soft cinematic light, "
            "portrait 9:16 composition and appealing stylized 3D animation. Remove all watermarks and visible text; "
            "no captions, typography, extra logo, UI, frame or collage. "
        )
    prompt += f"Product: {product_name[:100]}. Product details: {description[:180] or 'follow the visual reference'}."
    negative = (
        "photorealistic real person, watermark, text, captions, letters, logo, added graphic, wrong garment color, "
        "wrong neckline, long sleeves, added pattern, deformed hands, extra fingers, bad anatomy, collage, split screen"
    )

    if progress_callback:
        progress_callback(0.50, "Tạo khung hình nhân vật hoạt hình từ ảnh sản phẩm...")
    try:
        client = Client(
            settings.hf_character_space,
            token=os.getenv("HF_TOKEN") or None,
            verbose=False,
        )
        result = client.predict(
            prompt,
            [{"image": handle_file(str(image_path)), "caption": None}],
            negative,
            1.0,
            max(8, min(settings.hf_character_steps, 16)),
            42,
            # This Space exposes the resolution selector as a string choice
            # in its current Gradio API. Passing an integer (1024) can be
            # rejected by Gradio even though 1024 appears in the choices.
            "1024",
            "9:16",
            api_name="/generate",
        )
        destination = job_output_dir(job_id) / f"character_keyframe_{job_id}.png"
        return _save_image(result, destination)
    except VideoRenderError:
        raise
    except Exception as exc:
        logger.exception("Hugging Face Qwen Image keyframe generation failed")
        raise VideoRenderError(
            "Không tạo được keyframe hoạt hình bằng Qwen Image. Có thể Space đang bận hoặc quota ZeroGPU đã hết: "
            f"{exc}"
        ) from exc
