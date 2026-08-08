"""
Gradio application entrypoint.

Run:
    python -m app.main
    # or
    python run.py
"""

from __future__ import annotations

import sys
import traceback
import uuid
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import gradio as gr

from core.config import settings
from core.exceptions import AVAError, BatchError, ProductValidationError
from core.logging import get_logger
from models.product import ProductInput
from services.history import clear_history, list_jobs, save_result
from services.product.batch import create_sample_excel, load_batch_file, run_batch
from tts.edge import resolve_voice
from video.engine import render_product

from app.ui.theme import build_theme
from app.ui.layout import (
    build_header,
    build_single_tab,
    build_batch_tab,
    build_history_tab,
)

logger = get_logger("app.main")


def _save_uploaded_images(files: list | None, job_id: str) -> list[Path]:
    if not files:
        return []
    out_dir = settings.project_root / settings.outputs_dir / job_id / "images"
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for i, f in enumerate(files):
        src = Path(f) if not isinstance(f, Path) else f
        if not src.is_file():
            continue
        dest = out_dir / f"img_{i:02d}{src.suffix or '.png'}"
        try:
            dest.write_bytes(src.read_bytes())
            paths.append(dest)
        except Exception as e:
            logger.warning("Skip image %s: %s", src, e)
    return paths


# ---------------------------------------------------------------------------
# Single product
# ---------------------------------------------------------------------------


def process_single(
    category, product_name, description, price, target, images, duration, voice_name,
    progress=gr.Progress(track_tqdm=False),
):
    if not product_name or not str(product_name).strip():
        return None, "⚠️ Nhập **Tên sản phẩm**!", "", "", {}

    job_id = uuid.uuid4().hex[:10]

    def prog_cb(value: float, stage: str) -> None:
        progress(value, desc=stage)

    try:
        image_paths = _save_uploaded_images(images, job_id)
        product = ProductInput(
            name=product_name.strip(),
            description=(description or "").strip(),
            category=category or "Khác",
            price=(price or "").strip() or None,
            target_audience=(target or "").strip() or None,
            image_paths=image_paths,
            duration=int(duration),
            voice=resolve_voice(voice_name),
            render_mode=settings.render_mode.value,
        )

        result = render_product(product, job_id=job_id, progress_callback=prog_cb)
        result.meta = {
            **(result.meta or {}),
            "product_name": product.name,
            "category": product.category,
        }
        save_result(result)

        mode = result.meta.get("render_mode", "cpu")
        tip = ""
        if mode == "cpu":
            tip = (
                "\n\n⚠️ **Đây là bản Preview (CPU)** — chưa phải video AI chuyển động thật.\n"
                "Muốn **AI Image-to-Video** (Wan / LTX): cần GPU + ComfyUI.\n"
                "→ Xem hướng dẫn: `docs/AI_VIDEO_SETUP.md`"
            )
            if not image_paths:
                tip += (
                    "\n\n⚠️ Chưa upload ảnh. I2V **bắt buộc** có ảnh sản phẩm "
                    "(nên ảnh có người mặc/cầm SP)."
                )
        elif not image_paths:
            tip = "\n\n⚠️ GPU mode nhưng không có ảnh — đã fallback. Upload ảnh để I2V."

        info = f"""✅ **Video sẵn sàng** ({'AI I2V / GPU' if mode == 'gpu' else 'Preview CPU'})

**Concept:** {result.meta.get('concept', '—')}  
**Scenes:** {result.meta.get('scenes', '—')}  
**Duration:** {result.duration:.1f}s  
**Render:** `{mode}`

**Cách đăng Affiliate:**
1. Tải video → TikTok → Upload  
2. Bấm **Giỏ hàng** → chọn sản phẩm Showcase  
3. Dán caption → Đăng
{tip}
"""
        return (
            str(result.video_path),
            info,
            result.caption,
            result.script_text,
            result.meta,
        )

    except ProductValidationError as e:
        return None, f"⚠️ {e.message}", "", "", {}
    except AVAError as e:
        logger.exception("Pipeline error")
        return None, f"❌ Lỗi: {e.message}", "", "", {}
    except Exception as e:
        logger.exception("Unexpected error")
        return None, f"❌ Lỗi không xác định: {e}\n```\n{traceback.format_exc()[-400:]}\n```", "", "", {}


# ---------------------------------------------------------------------------
# Batch
# ---------------------------------------------------------------------------


def process_batch(batch_file, progress=gr.Progress(track_tqdm=False)):
    if not batch_file:
        return "⚠️ Upload file Excel/CSV trước.", None

    def prog_cb(value: float, stage: str) -> None:
        progress(value, desc=stage)

    try:
        products = load_batch_file(batch_file)
        results = run_batch(products, progress_callback=prog_cb)
        ok = len(results)
        total = len(products)
        lines = [
            f"✅ **Batch xong: {ok}/{total} thành công**\n",
        ]
        gallery = []
        for r in results:
            lines.append(
                f"- `{r.job_id}` · {r.meta.get('product_name', '?')} · "
                f"{r.duration:.0f}s · scenes={r.meta.get('scenes')}"
            )
            if r.video_path and Path(r.video_path).is_file():
                gallery.append(str(r.video_path))
        return "\n".join(lines), gallery or None
    except BatchError as e:
        return f"❌ {e.message}", None
    except Exception as e:
        logger.exception("Batch failed")
        return f"❌ Batch error: {e}", None


def download_sample():
    path = settings.project_root / "assets" / "templates" / "sample_batch.xlsx"
    create_sample_excel(path)
    return str(path)


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


def refresh_history():
    jobs = list_jobs(limit=50)
    if not jobs:
        return []
    rows = []
    for j in jobs:
        rows.append([
            j.get("id", ""),
            j.get("status", ""),
            j.get("product_name", ""),
            j.get("category", ""),
            j.get("concept", ""),
            j.get("scenes", ""),
            j.get("duration", ""),
            (j.get("created_at") or "")[:19],
        ])
    return rows


def do_clear_history():
    n = clear_history()
    return [], f"Đã xóa {n} bản ghi."


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------


def create_app() -> gr.Blocks:
    with gr.Blocks(title="Affiliate Video AI") as demo:
        build_header()

        with gr.Tabs():
            with gr.Tab("🎬 Tạo video"):
                single = build_single_tab()
                single["btn"].click(
                    fn=process_single,
                    inputs=single["inputs"],
                    outputs=single["outputs"],
                )

            with gr.Tab("📦 Batch Excel"):
                batch = build_batch_tab()
                batch["sample_btn"].click(fn=download_sample, outputs=batch["sample_file"])
                batch["batch_btn"].click(
                    fn=process_batch,
                    inputs=batch["batch_file"],
                    outputs=[batch["batch_log"], batch["batch_gallery"]],
                )

            with gr.Tab("📜 History"):
                hist = build_history_tab()
                hist["refresh_btn"].click(fn=refresh_history, outputs=hist["history_table"])
                hist["clear_btn"].click(fn=do_clear_history, outputs=[hist["history_table"], gr.Textbox(visible=False)])
                demo.load(fn=refresh_history, outputs=hist["history_table"])

        gr.Markdown(
            """
---
**Mode:** CPU multi-scene (Ken Burns) · Ollama optional · edge-tts  
Batch tối đa: {} sản phẩm / lần · Queue concurrency: {}
            """.format(settings.max_batch_size, settings.parallel_workers)
        )

    return demo


def main() -> None:
    settings.ensure_dirs()
    demo = create_app()
    theme = build_theme()
    logger.info(
        "Launching Gradio | %s:%s | mode=%s",
        settings.gradio_server_name,
        settings.gradio_server_port,
        settings.render_mode.value,
    )
    demo.queue(default_concurrency_limit=settings.parallel_workers)
    demo.launch(
        server_name=settings.gradio_server_name,
        server_port=settings.gradio_server_port,
        share=settings.gradio_share,
        theme=theme,
        css="""
        .gradio-container {
            max-width: 1100px !important;
            margin-left: auto !important;
            margin-right: auto !important;
            padding-left: 16px !important;
            padding-right: 16px !important;
        }
        footer { display: none !important; }
        .main, .wrap { justify-content: center !important; }
        """,
    )


if __name__ == "__main__":
    main()
