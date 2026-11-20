"""Dynamic and AI-driven Kids Card Generator (prevents repetitive videos)."""

from __future__ import annotations

import json
import random
import re
from typing import Optional

from ai.llm.client import OllamaClient
from core.logging import get_logger
from tts.edge import resolve_voice
from video.kids_education.canvas import sanitize_emoji
from video.kids_education.presets import KidsCard, get_preset_cards

logger = get_logger(__name__)

_KIDS_PROMPT_SYSTEM_VI = """Bạn là biên kịch video hoạt hình thiếu nhi vui nhộn hàng đầu (phong cách BabyBus, CoComelon, hoạt hình vui nhộn).
Nhiệm vụ của bạn là tạo ra 4 phân cảnh/thẻ học SIÊU HẤP DẪN, HÀI HƯỚC VÀ THU HÚT TRẺ EM.
Yêu cầu:
1. Lời thoại tiếng Việt giàu cảm xúc, năng lượng cao, có từ cảm thán (Wow, Oa, Haha, Tuyệt vời!), kết hợp từ vựng tiếng Anh đơn giản để bé vừa xem vừa học phát âm.
2. Tiêu đề ngắn gọn song ngữ hoặc tiếng Việt (VD: "1 Quả Táo - One Apple 🍎").
3. Emoji là ký tự Unicode thật (như 🐰, 🍎, 🐻, 🐵, 🐶, 🌟, 🎉), TUYỆT ĐỐI KHÔNG dùng dạng markdown như :frog: hay :cat:.
4. Trả về đúng định dạng JSON:
[
  {
    "title": "Tiêu đề ngắn gọn bắt mắt",
    "subtitle": "Phụ đề vui nhộn giải thích",
    "spoken_text": "Lời thoại vui nhộn, phát âm rõ ràng cho bé học",
    "image_prompt": "cute cartoon character illustration, 3d pixar style",
    "emoji": "🐰",
    "theme_color": "#FF6B6B"
  }
]
"""

_KIDS_PROMPT_SYSTEM_EN = """You are a world-class children's educational video creator (like CoComelon, Peppa Pig, Super Simple Songs).
Your task is to create 4 SUPER ENGAGING, FUNNY, AND DELIGHTFUL educational scenes/cards for toddlers and young children.
Requirements:
1. The spoken voice is ENGLISH (en-US). Every 'spoken_text' MUST be completely in joyful, energetic, kid-friendly ENGLISH! Use simple short words, fun sound effects (Look!, Wow!, Haha!, Crunch crunch!, Yum yum!, Yay!).
2. 'title' can be bilingual or English (e.g. "1 Red Apple - Một quả táo 🍎").
3. 'emoji' MUST be an actual Unicode emoji character (such as 🐰, 🍎, 🐻, 🐵, 🐶, 🌟, 🎉). NEVER use markdown text like :frog: or :cat:.
4. Return valid JSON only:
[
  {
    "title": "Short catchy title",
    "subtitle": "Fun playful subtitle or question",
    "spoken_text": "Lively, energetic spoken words in English for kids",
    "image_prompt": "cute cartoon character illustration, 3d pixar style",
    "emoji": "🐰",
    "theme_color": "#FF6B6B"
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


def _synthesize_topic_cards(custom_topic: str, is_english: bool) -> list[KidsCard]:
    """Smart topic-aware synthesizer when LLM is unavailable or times out."""
    t = custom_topic.lower()
    colors = ["#FF6B6B", "#4ECDC4", "#FFE66D", "#9B5DE5", "#06D6A0"]

    # 1. Animal Apple / Fruit Counting
    is_counting = any(k in t for k in ("đếm", "count", "số", "number", "1", "táo", "apple", "quả", "trái"))
    is_animal = any(k in t for k in ("thú", "động vật", "con vật", "animal", "thỏ", "gấu", "khỉ", "mèo", "chó"))

    if is_counting or (is_animal and any(k in t for k in ("táo", "apple", "quả"))):
        if is_english:
            scenes = [
                (
                    "1 Apple - Một Quả Táo 🍎",
                    "Cute bunny found 1 apple!",
                    "Look! An adorable white bunny found 1 shiny red apple! Crunch crunch! Let's say: One apple! Yum yum!",
                    "cute cartoon white bunny rabbit holding 1 red apple",
                    "🐰",
                ),
                (
                    "2 Apples - Hai Quả Táo 🍎🍎",
                    "Teddy bear brings 2 apples!",
                    "Wow! Big friendly Teddy Bear brings 2 delicious red apples! One, two! Two apples! Great job!",
                    "cute cartoon brown bear holding 2 red apples",
                    "🐻",
                ),
                (
                    "3 Apples - Ba Quả Táo 🍎",
                    "Playful monkey juggles 3 apples!",
                    "Haha! Look at the silly monkey juggling 3 sweet apples! One, two, three apples! You are so smart!",
                    "cute cartoon monkey juggling 3 red apples",
                    "🐵",
                ),
                (
                    "4 Apples - Bốn Quả Táo 🎉",
                    "Animal party with 4 apples!",
                    "Hooray! All the cute animal friends are having a party with 4 yummy apples! One, two, three, four apples! Yay!",
                    "cute cartoon puppy dog with apples celebration party",
                    "🎉",
                ),
            ]
        else:
            scenes = [
                (
                    "1 Quả Táo - One Apple 🍎",
                    "Bạn Thỏ trắng tìm thấy 1 quả táo!",
                    "Oa! Bạn Thỏ trắng đáng yêu tìm thấy 1 quả táo đỏ mọng nè! Bé cùng đếm với bạn Thỏ nhé: One Apple! Táo giòn ngon quá!",
                    "cute cartoon white bunny rabbit holding 1 red apple",
                    "🐰",
                ),
                (
                    "2 Quả Táo - Two Apples 🍎🍎",
                    "Bạn Gấu mang tới 2 quả táo to!",
                    "Haha! Bạn Gấu nâu mang tới tận 2 quả táo to tròn! Bé đếm cùng bạn Gấu nào: Một, hai quả táo! Two Apples!",
                    "cute cartoon brown bear holding 2 red apples",
                    "🐻",
                ),
                (
                    "3 Quả Táo - Three Apples 🍎",
                    "Bạn Khỉ tung hứng 3 quả táo!",
                    "Ôi nhìn kìa! Chú khỉ tinh nghịch đang tung hứng 3 quả táo đỏ rực! Một, hai, ba quả táo! Three Apples! Bé giỏi quá!",
                    "cute cartoon monkey juggling 3 red apples",
                    "🐵",
                ),
                (
                    "4 Quả Táo - Four Apples 🎉",
                    "Tiệc táo liên hoan muông thú!",
                    "Hoan hô! Tất cả các bạn thú cùng mở tiệc liên hoan với 4 quả táo ngon tuyệt! Cùng đếm nào: One, Two, Three, Four! Vỗ tay!",
                    "cute cartoon puppy dog with apples celebration party",
                    "🎉",
                ),
            ]
        cards = []
        for i, (title, sub, spoken, prompt, emoji) in enumerate(scenes):
            cards.append(
                KidsCard(
                    title=title,
                    subtitle=sub,
                    spoken_text=spoken,
                    image_prompt=prompt,
                    emoji=emoji,
                    theme_color=colors[i % len(colors)],
                )
            )
        return cards

    # 2. General Animals
    if is_animal:
        if is_english:
            scenes = [
                ("Cute Cat - Chú Mèo Con 🐱", "Meow meow! Soft fluffy kitten", "Look at the cute kitty cat! Meow meow! So soft and playful! Can you say: Cat?", "cute cartoon cat kitten", "🐱"),
                ("Puppy Dog - Chú Cún Yêu 🐶", "Woof woof! Friendly puppy", "Haha, here comes happy puppy! Woof woof! Wiggling its tail! Say hello to Dog!", "cute cartoon puppy dog", "🐶"),
                ("Panda Bear - Gấu Trúc Nhỏ 🐼", "Munch munch! Sweet panda", "Wow! Adorable panda bear is eating bamboo! Munch munch! Let's say: Panda!", "cute cartoon panda bear", "🐼"),
                ("Brave Lion - Sư Tử Dũng Cảm 🦁", "Roar! King of the jungle", "Look at the proud little lion king! Roar! Strong and brave! Say: Lion! Hooray!", "cute cartoon lion cub", "🦁"),
            ]
        else:
            scenes = [
                ("Mèo Con - Cute Cat 🐱", "Meo meo! Chú mèo lông mềm mại", "Meo meo! Bạn Mèo con dễ thương đang vẫy đuôi chào bé nè! Bé đọc cùng bạn nhé: Cat!", "cute cartoon cat kitten", "🐱"),
                ("Cún Con - Puppy Dog 🐶", "Gâu gâu! Chú cún tinh nghịch", "Gâu gâu! Bạn Cún con mừng rỡ nhảy nhót chào bé yêu! Bé đọc to nào: Dog!", "cute cartoon puppy dog", "🐶"),
                ("Gấu Trúc - Panda 🐼", "Tròn xoe đáng yêu thích ăn tre", "Oa! Bạn Gấu trúc tròn xoe đang nhai cành trúc giòn rụm! Đáng yêu quá! Cùng đọc: Panda!", "cute cartoon panda bear", "🐼"),
                ("Sư Tử - Brave Lion 🦁", "Chúa sơn lâm dũng cảm", "Gầm gừ! Bạn Sư tử con dũng cảm và oai vệ! Bé cùng hô to với bạn nhé: Lion! Hoan hô!", "cute cartoon lion cub", "🦁"),
            ]
        cards = []
        for i, (title, sub, spoken, prompt, emoji) in enumerate(scenes):
            cards.append(
                KidsCard(
                    title=title,
                    subtitle=sub,
                    spoken_text=spoken,
                    image_prompt=prompt,
                    emoji=emoji,
                    theme_color=colors[i % len(colors)],
                )
            )
        return cards

    # 3. Dynamic General Topic
    clean_words = re.findall(r"\w+", custom_topic)
    topic_label = " ".join(clean_words[:4]) if clean_words else "Điều Kỳ Diệu"
    emojis = ["🌟", "🚀", "🎉", "🎈"]

    cards = []
    for i in range(4):
        if is_english:
            title = f"{topic_label.title()} • Part {i+1} {emojis[i]}"
            sub = f"Fun discovery with {topic_label}"
            spoken = f"Wow, look here! Let's explore {topic_label} together! It is so colorful and exciting! Yay!"
        else:
            title = f"{topic_label} • Khám Phá {i+1} {emojis[i]}"
            sub = f"Cùng bé vui học về {topic_label}"
            spoken = f"Oa, bé ơi nhìn xem nè! Chúng mình cùng tìm hiểu về {topic_label} thật là vui và thú vị nhé! Bé giỏi quá!"

        cards.append(
            KidsCard(
                title=title,
                subtitle=sub,
                spoken_text=spoken,
                image_prompt=f"cute cartoon {topic_label} illustration, vibrant 3d pixar style",
                emoji=emojis[i],
                theme_color=colors[i % len(colors)],
            )
        )
    return cards


def generate_dynamic_kids_cards(
    preset_id: str = "vocabulary",
    custom_topic: str = "",
    client: Optional[OllamaClient] = None,
    voice_name: str = "vi-VN-HoaiMyNeural",
) -> list[KidsCard]:
    """
    Generates dynamic, engaging educational cards for kids.
    Tailors spoken language to the chosen voice (pure joyful English for en-US voices,
    or cheerful Vietnamese with English vocabulary for vi-VN voices).
    """
    custom_topic = (custom_topic or "").strip()
    voice_id = resolve_voice(voice_name)
    is_english = voice_id.startswith("en-") or voice_id.startswith("en_")

    if custom_topic:
        # 1. Try LLM first if available
        if client and client.is_available():
            try:
                system_prompt = _KIDS_PROMPT_SYSTEM_EN if is_english else _KIDS_PROMPT_SYSTEM_VI
                user_msg = (
                    f"User Topic: {custom_topic}\n"
                    f"Voice language: {'ENGLISH (en-US)' if is_english else 'VIETNAMESE (vi-VN)'}.\n"
                    f"Create exactly 4 super funny, kid-friendly educational cards in JSON format."
                )
                raw = client.chat(
                    messages=[
                        {"role": "system", "content": system_prompt},
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
                                image_prompt=str(item.get("image_prompt", f"{custom_topic}, cute 3d cartoon style")).strip(),
                                emoji=sanitize_emoji(str(item.get("emoji", "✨")).strip()),
                                theme_color=str(item.get("theme_color", colors[idx % len(colors)])).strip(),
                            )
                        )
                    if len(cards) >= 2:
                        return cards
            except Exception as e:
                logger.warning("Dynamic LLM generation failed for topic '%s' (%s); using dynamic synthesizer", custom_topic, e)

        # 2. Smart dynamic synthesizer for custom topic
        return _synthesize_topic_cards(custom_topic, is_english=is_english)

    # If no custom topic, load preset pool and add randomized freshness!
    pool = get_preset_cards(preset_id)
    if not pool:
        pool = get_preset_cards("vocabulary")

    selected = list(pool)
    random.shuffle(selected)
    cards = selected[:min(4, len(selected))]

    # Sanitize emojis
    cards = [c.model_copy(update={"emoji": sanitize_emoji(c.emoji)}) for c in cards]

    if cards:
        intro_phrases_en = [
            "Hello little stars! Let's get started! ",
            "Look, look! Something exciting is here! ",
            "Yay! 1, 2, 3, let's explore together! ",
        ]
        intro_phrases_vi = [
            "Oa, chào bé yêu! Cùng bắt đầu nào! ",
            "Bé ơi, xem nè, vui ơi là vui! ",
            "1, 2, 3, cùng khám phá nào các bạn nhỏ ơi! ",
        ]
        chosen_intro = random.choice(intro_phrases_en if is_english else intro_phrases_vi)
        cards[0] = cards[0].model_copy(
            update={
                "spoken_text": chosen_intro + cards[0].spoken_text,
            }
        )

    return cards
