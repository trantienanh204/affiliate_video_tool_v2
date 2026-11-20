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

from ai.llm.client import OllamaClient
from ai.story.fast_generator import generate_fast_story
from core.config import settings
from core.logging import get_logger
from models.product import ProductInput
from models.story import FastStoryInput, StoryLength
from services.history import clear_history, list_jobs, save_result
from tts.edge import resolve_voice
from video.custom.generator import parse_prompt_to_scenes, render_custom_video
from video.engine import render_product
from video.kids_education.generator import render_kids_education_video
from video.kids_education.presets import get_preset_cards
from video.kids_education.dynamic_generator import generate_dynamic_kids_cards

from app.ui.theme import build_theme
from app.ui.layout import (
    build_header,
    build_custom_video_tab,
    build_kids_tab,
    build_fast_story_tab,
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
# Tab 1: Custom Video & Affiliate
# ---------------------------------------------------------------------------

def process_custom_video(
    prompt: str,
    duration: int,
    voice_name: str,
    enable_tts: bool,
    progress=gr.Progress(track_tqdm=False),
):
    if not prompt or not str(prompt).strip():
        return None, "⚠️ Vui lòng nhập **Ý tưởng / Yêu cầu video**!", ""

    job_id = uuid.uuid4().hex[:10]
    out_dir = settings.project_root / settings.outputs_dir / f"custom_{job_id}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_video = out_dir / "custom_video.mp4"

    def prog_cb(val: float, desc: str):
        progress(val, desc=desc)

    try:
        prog_cb(0.05, "Đang phân tích kịch bản từ ý tưởng...")
        client = OllamaClient() if OllamaClient().is_available() else None
        target_scenes = max(3, int(duration) // 8)
        scenes = parse_prompt_to_scenes(prompt, target_scenes=target_scenes, client=client)

        script_lines = []
        for i, s in enumerate(scenes):
            script_lines.append(f"**Cảnh {i+1}: {s.title}**\n- Lời thoại: {s.script}\n- Hình ảnh: *{s.image_prompt}*\n")
        full_script = "\n".join(script_lines)

        render_custom_video(
            scenes=scenes,
            output_path=out_video,
            voice_name=voice_name,
            enable_tts=enable_tts,
            progress_cb=prog_cb,
        )

        save_result(
            job_id=job_id,
            status="completed",
            video_path=str(out_video),
            product_name=prompt[:32],
            category="Custom",
            concept=scenes[0].title if scenes else "Custom Video",
            scenes_count=len(scenes),
            duration=float(duration),
            meta={"prompt": prompt, "scenes": [s.model_dump() for s in scenes]},
        )

        prog_cb(1.0, "Đã hoàn thành video theo yêu cầu!")
        info_md = f"✅ **Tạo video thành công!** · {len(scenes)} phân cảnh · Định dạng 9:16 · Chi phí 0đ"
        return str(out_video), info_md, full_script

    except Exception as e:
        logger.exception("Custom video failed: %s", e)
        return None, f"❌ Lỗi: {e}\n```\n{traceback.format_exc()[-400:]}\n```", ""


def process_single(
    category, product_name, description, price, target, images, duration, voice_name,
    progress=gr.Progress(track_tqdm=False),
):
    if not product_name or not str(product_name).strip():
        return None, "⚠️ Nhập **Tên sản phẩm**!", "", ""

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
            render_mode="cpu",
        )

        result = render_product(product, job_id=job_id, progress_callback=prog_cb)
        save_result(
            job_id=job_id,
            status="completed",
            video_path=str(result.video_path),
            product_name=product.name,
            category=product.category,
            concept=result.concept,
            scenes_count=len(result.storyboard.scenes),
            duration=result.duration,
            meta=result.meta,
        )

        info = f"✅ Video hoàn thành! Độ dài: {result.duration:.1f}s | Scenes: {len(result.storyboard.scenes)}"
        script = "\n".join(f"[{s.role}] {s.voiceover}" for s in result.storyboard.scenes)
        return str(result.video_path), info, result.caption, script
    except Exception as e:
        logger.exception("Single product render error: %s", e)
        return None, f"❌ Lỗi: {e}", "", ""


# ---------------------------------------------------------------------------
# Tab 2: Kids Education Video
# ---------------------------------------------------------------------------

def process_kids_video(
    preset_id: str,
    custom_topic: str,
    voice_name: str,
    enable_tts: bool,
    progress=gr.Progress(track_tqdm=False),
):
    job_id = uuid.uuid4().hex[:10]
    out_dir = settings.project_root / settings.outputs_dir / f"kids_{job_id}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_video = out_dir / "kids_education.mp4"

    def prog_cb(val: float, desc: str):
        progress(val, desc=desc)

    try:
        prog_cb(0.05, "Đang tạo nội dung thẻ học phong phú...")
        client = OllamaClient(timeout=20) if OllamaClient(timeout=4).is_available() else None
        cards = generate_dynamic_kids_cards(
            preset_id=preset_id,
            custom_topic=custom_topic,
            client=client,
            voice_name=voice_name,
        )

        card_md_lines = []
        for i, c in enumerate(cards):
            card_md_lines.append(f"### {c.emoji} Cảnh {i+1}: {c.title}\n- **Phụ đề:** {c.subtitle}\n- **Giọng phát âm:** \"{c.spoken_text}\"\n")
        preview_md = "\n".join(card_md_lines)

        render_kids_education_video(
            cards_or_preset_id=cards,
            output_path=out_video,
            voice_name=voice_name,
            enable_tts=enable_tts,
            progress_cb=prog_cb,
        )

        topic_label = custom_topic.strip()[:30] if custom_topic and custom_topic.strip() else f"Preset {preset_id}"
        save_result(
            job_id=job_id,
            status="completed",
            video_path=str(out_video),
            product_name=cards[0].title if cards else "Kids Video",
            category="Kids",
            concept=topic_label,
            scenes_count=len(cards),
            duration=len(cards) * 3.8,
            meta={"preset": preset_id, "custom_topic": custom_topic, "cards_count": len(cards)},
        )

        prog_cb(1.0, "Đã hoàn thành video hoạt hình cho bé!")
        info_md = (
            f"🎉 **Đã tạo xong video hoạt hình cho bé!** · {len(cards)} phân cảnh hoạt hình 2D sống động "
            f"· Nhân vật nhún nhảy theo nhạc · Phụ đề khớp 100% giọng phát âm · Nhạc nền vui nhộn · Định dạng 9:16"
        )
        return str(out_video), info_md, preview_md

    except Exception as e:
        logger.exception("Kids video failed: %s", e)
        return None, f"❌ Lỗi tạo video: {e}\n```\n{traceback.format_exc()[-400:]}\n```", ""


# ---------------------------------------------------------------------------
# Tab 3: Fast Story Generator (Text-only, no TTS)
# ---------------------------------------------------------------------------

def process_fast_story(
    trope: str,
    premise: str,
    protagonist: str,
    length: str,
    tone: str,
    ending: str,
    progress=gr.Progress(track_tqdm=False),
):
    story_id = uuid.uuid4().hex[:10]
    output_dir = settings.project_root / settings.outputs_dir / f"story_{story_id}"
    output_dir.mkdir(parents=True, exist_ok=True)

    def prog_cb(val: float, desc: str):
        progress(val, desc=desc)

    try:
        story_len = StoryLength.MEDIUM
        if length == "short":
            story_len = StoryLength.SHORT
        elif length == "long":
            story_len = StoryLength.LONG

        inp = FastStoryInput(
            trope=trope,
            premise=premise or "",
            protagonist=protagonist or "An Nhiên",
            length=story_len,
            tone=tone,
            ending=ending,
        )

        client = OllamaClient() if OllamaClient().is_available() else None
        res = generate_fast_story(inp, client=client, progress_callback=prog_cb)

        script_path = output_dir / "story_script.txt"
        script_path.write_text(
            f"{res.title}\n\n{res.hook}\n\n{res.content}\n\n{res.caption}\n{' '.join(res.hashtags)}\n",
            encoding="utf-8",
        )

        mode_str = "AI 1-Shot (Ollama)" if res.mode == "ollama" else "Mẫu Sáng Tạo Tức Thì (Instant Template)"
        info_md = (
            f"✅ **Đã viết xong truyện bằng {mode_str}!**\n"
            f"- Số từ: **{res.word_count:,} từ**\n"
            f"- Thời gian đọc ước tính: **~{res.estimated_read_time_minutes} phút**\n"
            f"- Liền mạch 100%, không tốn thời gian tạo audio."
        )

        return (
            info_md,
            res.title,
            res.hook,
            res.content,
            f"{res.caption}\n\n{' '.join(res.hashtags)}",
            str(script_path),
        )

    except Exception as e:
        logger.exception("Fast story generation failed: %s", e)
        return (
            f"❌ Không tạo được truyện: {e}",
            "",
            "",
            "",
            "",
            None,
        )


# ---------------------------------------------------------------------------
# Tab 4: History
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
    clear_history()
    return []


# ---------------------------------------------------------------------------
# App construction
# ---------------------------------------------------------------------------

def create_app() -> gr.Blocks:
    with gr.Blocks(title="AI Video Studio & Fast Story") as demo:
        build_header()

        with gr.Tabs():
            with gr.Tab("🎬 Video Theo Yêu Cầu & Affiliate"):
                custom_aff = build_custom_video_tab()
                custom_aff["custom"]["btn"].click(
                    fn=process_custom_video,
                    inputs=custom_aff["custom"]["inputs"],
                    outputs=custom_aff["custom"]["outputs"],
                )
                custom_aff["affiliate"]["btn"].click(
                    fn=process_single,
                    inputs=custom_aff["affiliate"]["inputs"],
                    outputs=custom_aff["affiliate"]["outputs"],
                )

            with gr.Tab("🧸 Video Trẻ Em & Giáo Dục"):
                kids = build_kids_tab()
                kids["btn"].click(
                    fn=process_kids_video,
                    inputs=kids["inputs"],
                    outputs=kids["outputs"],
                )

            with gr.Tab("📖 Viết Truyện Nhanh"):
                fast_story = build_fast_story_tab()
                fast_story["btn"].click(
                    fn=process_fast_story,
                    inputs=fast_story["inputs"],
                    outputs=fast_story["outputs"],
                )

            with gr.Tab("📜 Lịch Sử & Quản Lý"):
                hist = build_history_tab()
                hist["refresh_btn"].click(fn=refresh_history, outputs=hist["history_table"])
                hist["clear_btn"].click(fn=do_clear_history, outputs=hist["history_table"])
                demo.load(fn=refresh_history, outputs=hist["history_table"])

        gr.Markdown(
            """
---
**Hệ thống AI Video Studio:** MoviePy 2.5D · Chi phí 0đ · Edge-TTS Neural Voice · 1-Shot Storytelling
            """
        )

    return demo


def main() -> None:
    settings.ensure_dirs()
    demo = create_app()
    theme = build_theme()
    logger.info(
        "Launching Gradio | %s:%s | mode=cpu",
        settings.gradio_server_name,
        settings.gradio_server_port,
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
