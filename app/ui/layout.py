"""Gradio layout builders: Zero-Cost Video, Kids Education & Fast Story."""

from __future__ import annotations

import gradio as gr

from core.config import settings
from tts.edge import list_voices
from video.kids_education.presets import get_available_presets

CATEGORIES = [
    "Áo", "Quần", "Giày", "Đồ ăn", "Phụ kiện",
    "Mỹ phẩm", "Đồng hồ", "Túi", "Nhà cửa", "Khác",
]


def build_header() -> None:
    gr.Markdown(
        """
# 🎬 AI Video Studio & Fast Story
**Video AI 0đ (MoviePy 2.5D) · Video Trẻ Em & Giáo Dục · Viết Truyện Siêu Tốc 1-Shot**

🟢 **Chi phí 0đ:** Vận hành mượt mà trên CPU / Docker, không tốn phí API, tích hợp giọng đọc chuẩn miễn phí (`edge-tts`).
        """
    )


def build_custom_video_tab():
    """Tab 1: Custom Prompt Video & Affiliate Product Video."""
    with gr.Tabs():
        with gr.TabItem("💡 Tạo Theo Prompt Tự Do"):
            with gr.Row():
                with gr.Column(scale=1):
                    prompt = gr.Textbox(
                        label="Yêu cầu / Ý tưởng video của bạn *",
                        placeholder="Ví dụ: 3 mẹo tiết kiệm tiền cho sinh viên trong thời bão giá...",
                        lines=4,
                    )
                    duration = gr.Slider(
                        minimum=15,
                        maximum=60,
                        value=30,
                        step=5,
                        label="Thời lượng mục tiêu (giây)",
                    )
                    voice = gr.Dropdown(
                        choices=list(list_voices().keys()),
                        value="Nữ dễ thương (Hoài My)",
                        label="Giọng đọc thuyết minh",
                    )
                    enable_tts = gr.Checkbox(value=True, label="Bật giọng đọc thuyết minh (Edge-TTS 0đ)")
                    custom_btn = gr.Button("🚀 Tạo video theo yêu cầu", variant="primary", size="lg")

                with gr.Column(scale=1):
                    video_out = gr.Video(label="Video kết quả (9:16)", height=450)
                    info_out = gr.Markdown()
                    with gr.Accordion("Kịch bản phân cảnh", open=True):
                        script_out = gr.Textbox(label="Kịch bản chi tiết", lines=6)

        with gr.TabItem("🛍️ Sản Phẩm Affiliate & Batch"):
            with gr.Row():
                with gr.Column(scale=1):
                    category = gr.Dropdown(CATEGORIES, value="Áo", label="Danh mục")
                    product_name = gr.Textbox(
                        label="Tên sản phẩm *",
                        placeholder="Áo thun form rộng unisex cotton 100%",
                        max_lines=1,
                    )
                    description = gr.Textbox(
                        label="Mô tả / USP",
                        placeholder="Cotton 100%, form rộng, thoáng mát...",
                        lines=2,
                    )
                    price = gr.Textbox(label="Giá", placeholder="99.000đ", max_lines=1)
                    target = gr.Textbox(
                        label="Đối tượng khách hàng",
                        placeholder="Giới trẻ, sinh viên...",
                        max_lines=1,
                    )
                    images = gr.File(
                        label="Ảnh sản phẩm",
                        file_count="multiple",
                        file_types=["image"],
                        type="filepath",
                    )
                    aff_duration = gr.Slider(
                        minimum=15,
                        maximum=60,
                        value=30,
                        step=5,
                        label="Độ dài (giây)",
                    )
                    aff_voice = gr.Dropdown(
                        choices=list(list_voices().keys()),
                        value="Nữ dễ thương (Hoài My)",
                        label="Giọng đọc",
                    )
                    aff_btn = gr.Button("🚀 Tạo video sản phẩm", variant="primary")

                with gr.Column(scale=1):
                    aff_video_out = gr.Video(label="Video sản phẩm (9:16)", height=400)
                    aff_info_out = gr.Markdown()
                    with gr.Accordion("Caption & Script", open=True):
                        aff_caption = gr.Textbox(label="Caption sẵn đăng", lines=4)
                        aff_script = gr.Textbox(label="Script voiceover", lines=3)

    return {
        "custom": {
            "inputs": [prompt, duration, voice, enable_tts],
            "btn": custom_btn,
            "outputs": [video_out, info_out, script_out],
        },
        "affiliate": {
            "inputs": [category, product_name, description, price, target, images, aff_duration, aff_voice],
            "btn": aff_btn,
            "outputs": [aff_video_out, aff_info_out, aff_caption, aff_script],
        },
    }


def build_kids_tab():
    """Tab 2: Kids & Education Video."""
    presets = get_available_presets()
    preset_choices = [(p["name"], p["id"]) for p in presets]

    with gr.Row():
        with gr.Column(scale=1):
            preset_dd = gr.Dropdown(
                choices=preset_choices,
                value="vocabulary",
                label="Chọn chủ đề giáo dục mẫu",
            )
            custom_topic = gr.Textbox(
                label="💡 Hoặc nhập ý tưởng / chủ đề riêng cho bé (tùy chọn)",
                placeholder="Ví dụ: Bé học về các loại xe cứu hộ, câu chuyện hài hước chú thỏ tinh nghịch, học tiếng Anh về siêu nhân, đếm các loại quả...",
                lines=2,
            )
            gr.Markdown(
                "*Mỗi chủ đề gồm 4–5 thẻ học hoạt hình sinh động, hình ảnh rực rỡ, chữ to dễ đọc, hiệu ứng chuyển động Ken Burns và nhạc nền thiếu nhi vui nhộn.*"
            )
            voice_dd = gr.Dropdown(
                choices=list(list_voices().keys()),
                value="Nữ dễ thương (Hoài My)",
                label="Giọng đọc phát âm",
            )
            enable_tts_cb = gr.Checkbox(
                value=True,
                label="Bật giọng đọc phát âm chuẩn (Edge-TTS 0đ)",
            )
            kids_btn = gr.Button("🚀 Tạo video giáo dục cho bé", variant="primary", size="lg")

        with gr.Column(scale=1):
            kids_video_out = gr.Video(label="Video giáo dục cho bé (9:16)", height=450)
            kids_info_out = gr.Markdown()
            with gr.Accordion("Xem trước nội dung các thẻ học", open=True):
                kids_cards_preview = gr.Markdown()

    return {
        "inputs": [preset_dd, custom_topic, voice_dd, enable_tts_cb],
        "btn": kids_btn,
        "outputs": [kids_video_out, kids_info_out, kids_cards_preview],
        "preset_dd": preset_dd,
    }


def build_fast_story_tab():
    """Tab 3: Ultra-Fast Coherent Story (Text-only, no TTS)."""
    tropes = [
        "Thiên kim thật giả / tráo đổi thân phận",
        "Bị phản bội, bắt đầu lại",
        "Tái sinh và phục thù",
        "Hôn nhân hợp đồng, thân phận bí mật",
        "Gia đình & Đời sống kịch tính",
        "Chủ đề tự do",
    ]
    with gr.Row():
        with gr.Column(scale=1):
            trope = gr.Dropdown(tropes, value=tropes[0], label="Mô-típ truyện")
            premise = gr.Textbox(
                label="Ý tưởng thêm / Tình tiết cốt lõi (tùy chọn)",
                placeholder="Ví dụ: Đại tiểu thư thật sự sau 20 năm trở về với bằng chứng kiểm toán vạch trần kẻ mạo danh...",
                lines=3,
            )
            protagonist = gr.Textbox(label="Tên nhân vật chính", value="An Nhiên", max_lines=1)
            length = gr.Dropdown(
                [
                    ("Ngắn (~350 từ - đọc lướt TikTok/Shorts)", "short"),
                    ("Vừa (~800 từ - cốt truyện kịch tính)", "medium"),
                    ("Dài (~1800 từ - hoàn chỉnh, nhiều nút thắt)", "long"),
                ],
                value="medium",
                label="Độ dài truyện mục tiêu",
            )
            tone = gr.Dropdown(
                ["Kịch tính, cảm xúc", "Lãng mạn ngọt ngào", "Bí ẩn, hồi hộp", "Hài hước hóm hỉnh", "Ấm áp chữa lành"],
                value="Kịch tính, cảm xúc",
                label="Tông kể chuyện",
            )
            ending = gr.Dropdown(
                ["Twist bất ngờ", "Cliffhanger tập sau", "Kết có hậu viên mãn", "Bi kịch cảm động"],
                value="Twist bất ngờ",
                label="Kiểu kết thúc",
            )
            btn = gr.Button("✨ Viết truyện tức thì (1-Shot)", variant="primary", size="lg")
            gr.Markdown(
                "*Cơ chế viết 1-Shot thông minh: cốt truyện liền mạch, logic chặt chẽ, sinh cực nhanh và không tốn thời gian tạo audio.*"
            )

        with gr.Column(scale=1):
            info = gr.Markdown()
            title = gr.Textbox(label="Tiêu đề truyện", interactive=False)
            hook = gr.Textbox(label="Câu mở đầu (Hook)", interactive=False)
            content = gr.Textbox(label="Nội dung truyện hoàn chỉnh (Liền mạch)", lines=16, interactive=False)
            caption = gr.Textbox(label="Caption & Hashtag sẵn đăng bài", lines=4, interactive=False)
            download = gr.File(label="Tải kịch bản (.txt)", interactive=False)

    return {
        "inputs": [trope, premise, protagonist, length, tone, ending],
        "btn": btn,
        "outputs": [info, title, hook, content, caption, download],
    }


def build_history_tab():
    """Tab 4: History list tab."""
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
