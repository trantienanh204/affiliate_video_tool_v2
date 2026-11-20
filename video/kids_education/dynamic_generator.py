"""Dynamic and AI-driven Kids Card Generator (prevents repetitive videos)."""

from __future__ import annotations

import json
import random
import re
from typing import Optional

from ai.llm.client import OllamaClient
from core.logging import get_logger
from video.kids_education.presets import KidsCard, get_preset_cards

logger = get_logger(__name__)

_KIDS_PROMPT_SYSTEM = """Bạn là biên kịch video hoạt hình thiếu nhi vui nhộn hàng đầu (phong cách BabyBus, CoComelon, hoạt hình vui nhộn).
Nhiệm vụ của bạn là tạo ra 4 phân cảnh/thẻ học SIÊU HẤP DẪN, HÀI HƯỚC VÀ THU HÚT TRẺ EM.
Yêu cầu:
1. Lời thoại phải có cảm xúc, giàu năng lượng, biểu cảm vui vẻ, có từ cảm thán (Wow, Oa, Haha, Tuyệt vời!).
2. Kết hợp từ vựng tiếng Anh đơn giản để bé vừa xem vừa học phát âm.
3. Hình ảnh mô tả phong cách 3D hoạt hình Pixar tươi sáng, dễ thương, rực rỡ sắc màu.
4. Trả về đúng định dạng JSON:
[
  {
    "title": "Tiêu đề ngắn gọn, bắt mắt (VD: Quả Táo - Apple 🍎)",
    "subtitle": "Phụ đề vui nhộn giải thích",
    "spoken_text": "Lời thoại vui nhộn, phát âm rõ ràng tiếng Anh lẫn tiếng Việt",
    "image_prompt": "Mô tả hình ảnh hoạt hình 3d pixar style",
    "emoji": "Icon",
    "theme_color": "#MãMàu"
  }
]
"""

# Dynamic variations to guarantee unique generation even without LLM
_FUNNY_SURPRISES = [
    ("🎉 Bất Ngờ Chưa!", "Bé có biết điều kỳ diệu này không?"),
    ("🚀 Cùng Khám Phá Nào!", "Một điều siêu thú vị đang chờ bé!"),
    ("⭐ Bé Đoán Xem Nào!", "Thử tài thông minh của bé yêu nhé!"),
    ("🌟 Cười Lên Nào Bé Ơi!", "Haha, vui quá là vui!"),
]


def generate_dynamic_kids_cards(
    preset_id: str = "vocabulary",
    custom_topic: str = "",
    client: Optional[OllamaClient] = None,
) -> list[KidsCard]:
    """
    Generates dynamic, non-repetitive educational cards.
    If custom_topic is given, generates custom cards tailored to the topic.
    Otherwise, picks and shuffles dynamic variations from the preset pool.
    """
    custom_topic = (custom_topic or "").strip()

    if custom_topic:
        # 1. Try LLM first if available
        if client and client.is_available():
            try:
                user_msg = f"Chủ đề bé yêu cầu: {custom_topic}\nHãy tạo đúng 4 thẻ học/hoạt hình thật vui nhộn cho bé."
                raw = client.chat(
                    messages=[
                        {"role": "system", "content": _KIDS_PROMPT_SYSTEM},
                        {"role": "user", "content": user_msg},
                    ],
                    format_json=True,
                    max_tokens=1200,
                    temperature=0.85,
                )
                cleaned = raw.strip()
                if cleaned.startswith("```json"):
                    cleaned = cleaned[7:]
                elif cleaned.startswith("```"):
                    cleaned = cleaned[3:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                data = json.loads(cleaned.strip())
                if isinstance(data, dict):
                    data = data.get("cards", data.get("scenes", [data]))
                if isinstance(data, list) and len(data) >= 2:
                    cards = []
                    colors = ["#FF6B6B", "#4ECDC4", "#FFE66D", "#9B5DE5", "#FF9F1C"]
                    for idx, item in enumerate(data[:4]):
                        cards.append(
                            KidsCard(
                                title=str(item.get("title", f"Phần {idx+1}")).strip(),
                                subtitle=str(item.get("subtitle", "")).strip(),
                                spoken_text=str(item.get("spoken_text", item.get("title", ""))).strip(),
                                image_prompt=str(item.get("image_prompt", f"{custom_topic}, cute 3d pixar style")).strip(),
                                emoji=str(item.get("emoji", "✨")).strip(),
                                theme_color=str(item.get("theme_color", colors[idx % len(colors)])).strip(),
                            )
                        )
                    if len(cards) >= 2:
                        return cards
            except Exception as e:
                logger.warning("Dynamic LLM generation failed for topic '%s' (%s); using dynamic synthesizer", custom_topic, e)

        # 2. Dynamic synthesizer for custom topic without LLM
        colors = ["#FF6B6B", "#4ECDC4", "#FFE66D", "#9B5DE5", "#06D6A0"]
        emojis = ["🚀", "🎈", "⭐", "🎉", "🌈"]
        cards = []
        topic_words = re.findall(r"\w+", custom_topic)
        topic_clean = " ".join(topic_words[:4]) if topic_words else "Điều Kỳ Diệu"

        variations = [
            (f"Chào mừng bé đến với: {topic_clean}!", f"Oa, bé ơi! Hôm nay chúng mình cùng khám phá {topic_clean} cực kỳ vui nhộn nhé!", "welcome and fun discovery"),
            (f"Khám Phá Số 1: {topic_clean}", f"Bé hãy nhìn xem nè! Wow, {topic_clean} thật là tuyệt vời và nhiều màu sắc!", "colorful magical animated scene"),
            (f"Điều Kỳ Thú Về {topic_clean}", f"Haha, buồn cười quá đi mất! Bé có thấy điều bất ngờ này không nè?", "funny comical cheerful animation"),
            (f"Hoan Hô Bé Thông Minh!", f"Bé giỏi quá! Bé hãy nhớ chia sẻ niềm vui về {topic_clean} cùng ba mẹ và bạn bè nhé!", "celebration stars and confetti happy ending"),
        ]
        for i, (title, spoken, prompt_extra) in enumerate(variations):
            cards.append(
                KidsCard(
                    title=title,
                    subtitle=f"Cùng vui học mỗi ngày • {emojis[i]}",
                    spoken_text=spoken,
                    image_prompt=f"{custom_topic}, {prompt_extra}, joyful cartoon, vibrant colors, 3d pixar style",
                    emoji=emojis[i],
                    theme_color=colors[i % len(colors)],
                )
            )
        return cards

    # If no custom topic, load preset pool and add randomized freshness!
    pool = get_preset_cards(preset_id)
    if not pool:
        pool = get_preset_cards("vocabulary")

    # Shuffle or pick randomized order with varied energy
    selected = list(pool)
    random.shuffle(selected)
    cards = selected[:min(4, len(selected))]

    # Inject dynamic surprise into spoken text or subtitle so it feels fresh every time
    surprise_title, surprise_sub = random.choice(_FUNNY_SURPRISES)
    if cards:
        # Give the first card an exciting randomized intro hook
        intro_phrases = [
            "Oa, chào bé yêu! Cùng bắt đầu nào! ",
            "Bé ơi, xem nè, vui ơi là vui! ",
            "Haha, hôm nay có điều bất ngờ cho bé nè! ",
            "1, 2, 3, cùng khám phá nào các bạn nhỏ ơi! ",
        ]
        cards[0] = cards[0].model_copy(
            update={
                "spoken_text": random.choice(intro_phrases) + cards[0].spoken_text,
            }
        )

    return cards
