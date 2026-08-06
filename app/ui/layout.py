"""Gradio layout builders."""

from __future__ import annotations

import gradio as gr

from core.config import settings
from tts.edge import list_voices

CATEGORIES = [
    "Áo", "Quần", "Giày", "Đồ ăn", "Phụ kiện",
    "Mỹ phẩm", "Đồng hồ", "Túi", "Nhà cửa", "Khác",
]


def build_header() -> None:
    gr.Markdown(
        """
# 🎬 Affiliate Video AI
**Multi-scene · AI Script · Voice Việt · 9:16 · Free / Local**

Upload ảnh sản phẩm (nên có người) → AI tự viết script, storyboard, voiceover và dựng video.
        """
    )


def build_single_tab():
    """Single product generation tab."""
    with gr.Row():
        with gr.Column(scale=1):
            category = gr.Dropdown(CATEGORIES, value="Áo", label="Danh mục")
            product_name = gr.Textbox(
                label="Tên sản phẩm *",
                placeholder="Áo thun form rộng unisex cotton 100%",
                max_lines=1,
            )
            description = gr.Textbox(
                label="Mô tả / USP (tùy chọn)",
                placeholder="Cotton 100%, form rộng, giá 99k, màu be/đen...",
                lines=2,
            )
            price = gr.Textbox(label="Giá (tùy chọn)", placeholder="99.000đ", max_lines=1)
            target = gr.Textbox(
                label="Đối tượng khách hàng (tùy chọn)",
                placeholder="Nữ 18-25, dân văn phòng, style Hàn...",
                max_lines=1,
            )
            images = gr.File(
                label="Ảnh sản phẩm (1 hoặc nhiều)",
                file_count="multiple",
                file_types=["image"],
                type="filepath",
            )
            duration = gr.Slider(
                minimum=settings.min_duration,
                maximum=settings.max_duration,
                value=settings.default_duration,
                step=5,
                label="Độ dài mục tiêu (giây)",
            )
            voice = gr.Dropdown(
                choices=list(list_voices().keys()),
                value="Nữ dễ thương (Hoài My)",
                label="Giọng đọc",
            )
            btn = gr.Button("🚀 Tạo video ngay", variant="primary", size="lg")

        with gr.Column(scale=1):
            video_out = gr.Video(label="Video kết quả (9:16)", height=420)
            info_out = gr.Markdown()
            with gr.Accordion("Caption & Script", open=True):
                caption_out = gr.Textbox(label="📋 Caption sẵn đăng (copy)", lines=6)
                script_out = gr.Textbox(label="Script voiceover", lines=3)
            with gr.Accordion("Meta", open=False):
                meta_out = gr.JSON(label="Metadata")

    return {
        "inputs": [category, product_name, description, price, target, images, duration, voice],
        "btn": btn,
        "outputs": [video_out, info_out, caption_out, script_out, meta_out],
    }


def build_batch_tab():
    """Batch Excel import tab."""
    gr.Markdown(
        """
Upload file **Excel (.xlsx)** hoặc **CSV** với các cột:
`name` (bắt buộc), `category`, `description`, `price`, `target_audience`, `image_path`, `duration`, `voice`.

`image_path` có thể nhiều ảnh, cách nhau bởi `;`. Đường dẫn tương đối tính từ thư mục chứa file Excel.
        """
    )
    with gr.Row():
        batch_file = gr.File(
            label="File Excel / CSV",
            file_types=[".xlsx", ".xls", ".csv"],
            type="filepath",
        )
        sample_btn = gr.Button("📥 Tải template mẫu", size="sm")
    sample_file = gr.File(label="Template mẫu", visible=True, interactive=False)
    batch_btn = gr.Button("🚀 Chạy batch", variant="primary")
    batch_log = gr.Markdown()
    batch_gallery = gr.Gallery(label="Video đã tạo (preview)", columns=3, height=280)

    return {
        "batch_file": batch_file,
        "sample_btn": sample_btn,
        "sample_file": sample_file,
        "batch_btn": batch_btn,
        "batch_log": batch_log,
        "batch_gallery": batch_gallery,
    }


def build_history_tab():
    """History list tab."""
    refresh_btn = gr.Button("🔄 Làm mới", size="sm")
    clear_btn = gr.Button("🗑️ Xóa history", size="sm", variant="stop")
    history_table = gr.Dataframe(
        headers=["id", "status", "product_name", "category", "concept", "scenes", "duration", "created_at"],
        datatype=["str"] * 8,
        label="Jobs gần đây",
        interactive=False,
        wrap=True,
    )
    return {
        "refresh_btn": refresh_btn,
        "clear_btn": clear_btn,
        "history_table": history_table,
    }
