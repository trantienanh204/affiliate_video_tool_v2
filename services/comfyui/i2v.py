"""
Image-to-Video via ComfyUI workflows.

Provides a stable interface:
  render_scene_i2v(image_path, prompt, duration, ...) → Path to mp4/webm

When ComfyUI is offline or workflow missing → raises ComfyUIError
so the engine can fall back to Ken Burns.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Optional

from core.config import settings
from core.exceptions import ComfyUIError
from core.logging import get_logger
from services.comfyui.client import ComfyUIClient, get_comfyui_client
from utils.paths import cache_dir, job_output_dir

logger = get_logger(__name__)

# Built-in minimal workflow template (LTX-Video / generic I2V style placeholders).
# Users should replace workflows/i2v_ltx.json with their actual exported ComfyUI workflow.
# Node IDs below are conventional placeholders – real workflow JSON overrides them.

_DEFAULT_WORKFLOW: dict[str, Any] = {
    "_meta": {
        "note": (
            "Placeholder workflow. Export your real I2V workflow from ComfyUI "
            "(Save API Format) to workflows/i2v_ltx.json and map load/save nodes."
        )
    }
}


def _load_workflow_template(name: str = "i2v_ltx") -> dict[str, Any]:
    path = settings.project_root / settings.workflows_dir / f"{name}.json"
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        logger.info("Loaded ComfyUI workflow: %s", path.name)
        return data
    # also check services/comfyui/workflows
    alt = Path(__file__).parent / "workflows" / f"{name}.json"
    if alt.is_file():
        data = json.loads(alt.read_text(encoding="utf-8"))
        logger.info("Loaded ComfyUI workflow: %s", alt.name)
        return data
    logger.warning("No workflow JSON found for '%s' – using empty placeholder", name)
    return copy.deepcopy(_DEFAULT_WORKFLOW)


def _inject_inputs(
    workflow: dict[str, Any],
    *,
    image_name: str,
    positive: str,
    negative: str,
    width: int,
    height: int,
    frames: int,
    seed: int,
) -> dict[str, Any]:
    """
    Heuristic injection into common ComfyUI node patterns.

    Looks for nodes by class_type and patches inputs.
    Safe no-op if structure unknown – user must supply correct workflow.
    """
    wf = copy.deepcopy(workflow)
    # Remove meta
    wf.pop("_meta", None)

    for node_id, node in list(wf.items()):
        if not isinstance(node, dict):
            continue
        ctype = node.get("class_type", "")
        inputs = node.setdefault("inputs", {})

        # Load image
        if ctype in ("LoadImage", "LoadImageMask"):
            inputs["image"] = image_name

        # CLIP / text encode
        if ctype in ("CLIPTextEncode", "CLIPTextEncodeSDXL"):
            # prefer positive on first empty or "text" field
            if "text" in inputs:
                # crude: if current text looks like placeholder / empty → positive
                cur = str(inputs.get("text") or "")
                if not cur or "positive" in cur.lower() or "prompt" in cur.lower():
                    inputs["text"] = positive
                elif "negative" in cur.lower():
                    inputs["text"] = negative

        # Empty latent / video latent size
        if ctype in ("EmptyLatentImage", "EmptyLTXVLatentVideo", "EmptyHunyuanLatentVideo"):
            if "width" in inputs:
                inputs["width"] = width
            if "height" in inputs:
                inputs["height"] = height
            if "length" in inputs:
                inputs["length"] = frames
            if "batch_size" in inputs:
                inputs["batch_size"] = 1

        # KSampler seed
        if "seed" in inputs and ctype in (
            "KSampler", "KSamplerAdvanced", "SamplerCustom", "RandomNoise"
        ):
            inputs["seed"] = seed

        # VHS / video combine frame rate etc. left as-is from template

    return wf


def render_scene_i2v(
    image_path: Path | str,
    prompt: str,
    *,
    negative_prompt: str = "blurry, deformed, text, watermark, color change, logo change",
    duration: float = 4.0,
    fps: int = 24,
    width: int | None = None,
    height: int | None = None,
    seed: int = 42,
    job_id: Optional[str] = None,
    workflow_name: str = "i2v_ltx",
    client: Optional[ComfyUIClient] = None,
) -> Path:
    """
    Run one Image-to-Video scene through ComfyUI.

    Returns path to the downloaded video file.
    Raises ComfyUIError on any failure.
    """
    image_path = Path(image_path)
    if not image_path.is_file():
        raise ComfyUIError(f"Scene image missing: {image_path}")

    use_client = client or get_comfyui_client()
    if not use_client.is_available():
        raise ComfyUIError("ComfyUI server not reachable")

    width = width or settings.video_width
    height = height or settings.video_height
    frames = max(8, int(duration * fps))

    # Upload source image
    server_name = use_client.upload_image(image_path)

    # Load + patch workflow
    template = _load_workflow_template(workflow_name)
    if not template or template.keys() == {"_meta"}:
        raise ComfyUIError(
            f"Workflow '{workflow_name}' chưa được cấu hình. "
            f"Export API workflow từ ComfyUI vào workflows/{workflow_name}.json"
        )
    if not any(isinstance(node, dict) and node.get("class_type") in ("LoadImage", "LoadImageMask") for node in template.values()):
        raise ComfyUIError(
            f"Workflow '{workflow_name}' không có node LoadImage tiêu chuẩn; "
            "không thể đảm bảo ảnh sản phẩm là nguồn của video."
        )

    workflow = _inject_inputs(
        template,
        image_name=server_name,
        positive=prompt,
        negative=negative_prompt,
        width=width,
        height=height,
        frames=frames,
        seed=seed,
    )

    prompt_id = use_client.queue_prompt(workflow)
    entry = use_client.wait_for_completion(prompt_id)
    outputs = use_client.extract_video_outputs(entry)

    if not outputs:
        # fallback: try any image sequence as last resort
        raise ComfyUIError(
            "ComfyUI finished but no video/gif outputs found. "
            "Check SaveVideo / VHS_VideoCombine node in workflow."
        )

    # Prefer first video-like output
    out_info = outputs[0]
    dest_dir = job_output_dir(job_id) if job_id else cache_dir() / "comfyui"
    dest = dest_dir / f"i2v_{prompt_id[:8]}_{out_info['filename']}"
    return use_client.download_output(
        out_info["filename"],
        subfolder=out_info.get("subfolder", ""),
        folder_type=out_info.get("type", "output"),
        dest=dest,
    )


def write_workflow_readme() -> Path:
    """Write instructions for placing real workflow JSON."""
    path = settings.project_root / settings.workflows_dir / "README.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """# ComfyUI Workflows

Đặt file workflow API format vào đây.

## Cách export từ ComfyUI

1. Mở ComfyUI, load workflow I2V (LTX-Video / Wan 2.1 / CogVideoX…).
2. Bật **Enable Dev mode Options** (settings).
3. Click **Save (API Format)** – không phải Save thường.
4. Đổi tên thành `i2v_ltx.json` (hoặc `i2v_wan.json`) và copy vào thư mục này.

## Node cần có

- `LoadImage` – nhận ảnh sản phẩm
- Text encode positive / negative
- Sampler + model I2V
- Node xuất video (`VHS_VideoCombine`, `SaveVideo`, …)

Hệ thống sẽ tự inject:
- image filename
- positive / negative prompt
- width / height / frame length
- seed

Nếu class_type khác chuẩn, chỉnh `_inject_inputs` trong `services/comfyui/i2v.py`.
""",
        encoding="utf-8",
    )
    return path
