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
    from core.config import settings

    mode_line = (
        "🟢 **AI Image-to-Video miễn phí: Hugging Face ZeroGPU / Wan 2.2** — quota hằng ngày, có thể phải chờ"
        if settings.video_provider == "hf_zerogpu"
        else "🟢 **AI Image-to-Video: fal.ai / Wan** — cần API key; ảnh được gửi lên cloud và tính phí theo giây"
        if settings.video_provider == "fal"
        else "🟢 **AI Image-to-Video: ComfyUI** — cần GPU NVIDIA, model và workflow local"
        if settings.video_provider == "comfyui"
        else "🟡 **CPU preview** — chỉ pan/zoom ảnh, không tạo chuyển động AI"
    )
    gr.Markdown(
        f"""
# 🎬 Affiliate Video AI
**Phân tích ảnh · Script · Storyboard · Voice Việt · 9:16**

{mode_line}

Upload ảnh sản phẩm. Backend cloud tạo clip chuyển động AI ngắn rồi ghép voiceover tiếng Việt. Hugging Face ZeroGPU có quota miễn phí và giới hạn hàng đợi; ảnh được gửi tới Space để xử lý.
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
                label="Ảnh sản phẩm — dùng để phân tích và dựng video",
                file_count="multiple",
                file_types=["image"],
                type="filepath",
            )
            gr.Markdown(
                "*Video mặc định theo phong cách quảng cáo hoạt hình 3D với nhân vật hư cấu; nội dung được truyền tải bằng voiceover, không chèn chữ trang trí. "
                "Ảnh có người mặc sản phẩm thường giúp AI tạo nhân vật và bố cục tự nhiên hơn ảnh chụp sản phẩm đặt phẳng. "
                "AI tái tạo khung hình nên màu, đường may hoặc chi tiết nhỏ vẫn có thể khác ảnh mẫu.*"
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


def build_story_tab():
    """Fictional story + voiceover creation, separate from product videos."""
    tropes = [
        "Thiên kim thật giả / tráo đổi thân phận",
        "Bị phản bội, bắt đầu lại",
        "Tái sinh và trả thù",
        "Hôn nhân hợp đồng, thân phận bí mật",
        "Chủ đề tự nhập",
    ]
    with gr.Row():
        with gr.Column(scale=1):
            trope = gr.Dropdown(tropes, value=tropes[0], label="Mô-típ truyện")
            premise = gr.Textbox(
                label="Ý tưởng thêm (tùy chọn)",
                placeholder="Ví dụ: cô gái bị tráo thân phận phát hiện người chị mới là người cứu mình năm xưa...",
                lines=3,
            )
            protagonist = gr.Textbox(label="Tên nhân vật chính", value="An Nhiên", max_lines=1)
            tone = gr.Dropdown(
                ["Kịch tính, cảm xúc", "Lãng mạn", "Bí ẩn, hồi hộp", "Ấm áp, chữa lành", "Hài hước"],
                value="Kịch tính, cảm xúc",
                label="Tông kể chuyện",
            )
            ending = gr.Dropdown(
                ["Cliffhanger tập sau", "Twist bất ngờ", "Kết có hậu", "Bi kịch cảm động"],
                value="Cliffhanger tập sau",
                label="Kiểu kết",
            )
            duration = gr.Dropdown(
                [("15 phút", 900), ("16 phút", 960), ("18 phút", 1080), ("20 phút", 1200)],
                value=960,
                label="Thời lượng tối thiểu",
            )
            voice = gr.Dropdown(
                choices=list(list_voices().keys()),
                value="Nữ miền Bắc (Hương Hạnh)",
                label="Giọng kể",
            )
            btn = gr.Button("✨ Viết truyện & tạo giọng kể", variant="primary", size="lg")
            gr.Markdown(
                "*Truyện dài nhiều chương, tối thiểu 15 phút. AI sẽ lập dàn ý từ ý tưởng của bạn trước rồi viết từng chương theo cùng cốt truyện. "
                "Cần Ollama và model qwen2.5:7b cài trong Docker. "
                "Mục này tạo truyện hư cấu, lời thoại và file giọng đọc để bạn dùng cho TikTok/YouTube. "
                "App kiểm tra dàn ý và đoạn mở đầu có giữ đúng ý tưởng hay không; nếu sai, app sẽ dừng sớm thay vì viết dài sai hướng. "
                "Câu lẫn ký tự ngoại ngữ sẽ được bỏ, không chèn câu đệm. Bản nháp được lưu sau từng chương để lần thử lại tiếp tục. "
                "Không cần ảnh sản phẩm; đầu ra là kịch bản và audio, chưa tự dựng video hình ảnh.*"
            )
        with gr.Column(scale=1):
            info = gr.Markdown()
            title = gr.Textbox(label="Tiêu đề", interactive=False)
            script = gr.Textbox(label="Kịch bản voiceover", lines=16, interactive=False)
            caption = gr.Textbox(label="Caption & hashtag", lines=4, interactive=False)
            audio = gr.Audio(label="Nghe thử giọng kể", type="filepath")
            download = gr.File(label="Tải kịch bản (.txt)", interactive=False)

    return {
        "inputs": [trope, premise, protagonist, tone, ending, duration, voice],
        "btn": btn,
        "outputs": [info, title, script, caption, audio, download],
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
