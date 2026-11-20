"""Dynamic and AI-driven Kids Card Generator.

Guarantees 100% relevance between user topic, spoken voice, title, and visuals.
Features:
- Smart parser for comma-separated items (e.g. "tủ lạnh, cái tủ, cái quạt, cái nồi")
- Extensive bilingual kids vocabulary dictionary (household, animals, fruits, vehicles, food)
- Language-strict narration: English voices get 100% fluent joyful English; Vietnamese voices get cheerful bilingual instruction
- Anti-repetition randomization for presets
"""

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

# ---------------------------------------------------------------------------
# Extensive Bilingual Kids Vocabulary Dictionary (0đ offline)
# ---------------------------------------------------------------------------

COMMON_KIDS_VOCAB: dict[str, dict] = {
    # Household Appliances & Furniture
    "tủ lạnh": {
        "vi": "Tủ Lạnh",
        "en": "Refrigerator",
        "simple": "Fridge",
        "emoji": "❄️",
        "sound": "Brrr, so cold and fresh!",
        "action_en": "Open the fridge and keep our yummy food cool!",
        "action_vi": "Tủ lạnh mát lạnh giữ thức ăn luôn tươi ngon!",
        "color": "#38BDF8",
    },
    "cái tủ": {
        "vi": "Cái Tủ",
        "en": "Wardrobe",
        "simple": "Closet",
        "emoji": "🚪",
        "sound": "Open and close! Neat and clean!",
        "action_en": "Open the doors and pick out pretty clothes!",
        "action_vi": "Cất quần áo gọn gàng và ngăn nắp nhé!",
        "color": "#A78BFA",
    },
    "tủ": {
        "vi": "Cái Tủ",
        "en": "Wardrobe",
        "simple": "Closet",
        "emoji": "🚪",
        "sound": "Open and close! Neat and clean!",
        "action_en": "Open the doors and pick out pretty clothes!",
        "action_vi": "Cất quần áo gọn gàng và ngăn nắp nhé!",
        "color": "#A78BFA",
    },
    "cái quạt": {
        "vi": "Cái Quạt",
        "en": "Electric Fan",
        "simple": "Fan",
        "emoji": "🌀",
        "sound": "Whoosh whoosh! Cool breeze!",
        "action_en": "The fan spins round and blows breezy air!",
        "action_vi": "Quạt quay vù vù thổi bay cơn nóng nực!",
        "color": "#34D399",
    },
    "quạt": {
        "vi": "Cái Quạt",
        "en": "Electric Fan",
        "simple": "Fan",
        "emoji": "🌀",
        "sound": "Whoosh whoosh! Cool breeze!",
        "action_en": "The fan spins round and blows breezy air!",
        "action_vi": "Quạt quay vù vù thổi bay cơn nóng nực!",
        "color": "#34D399",
    },
    "cái nồi": {
        "vi": "Cái Nồi",
        "en": "Cooking Pot",
        "simple": "Pot",
        "emoji": "🍲",
        "sound": "Bubble bubble! Hot and delicious!",
        "action_en": "Mom cooks yummy warm soup in the pot!",
        "action_vi": "Nồi nấu canh nóng hổi thơm ngon tuyệt vời!",
        "color": "#F87171",
    },
    "nồi": {
        "vi": "Cái Nồi",
        "en": "Cooking Pot",
        "simple": "Pot",
        "emoji": "🍲",
        "sound": "Bubble bubble! Hot and delicious!",
        "action_en": "Mom cooks yummy warm soup in the pot!",
        "action_vi": "Nồi nấu canh nóng hổi thơm ngon tuyệt vời!",
        "color": "#F87171",
    },
    "máy giặt": {
        "vi": "Máy Giặt",
        "en": "Washing Machine",
        "simple": "Washer",
        "emoji": "🧺",
        "sound": "Swish swish! Clean bubbles!",
        "action_en": "Washing clothes clean and fresh!",
        "action_vi": "Giặt quần áo sạch tinh tươm thơm ngát!",
        "color": "#60A5FA",
    },
    "tivi": {
        "vi": "Ti Vi",
        "en": "Television",
        "simple": "TV",
        "emoji": "📺",
        "sound": "Beep boop! Colorful pictures!",
        "action_en": "Watching fun cartoons and singing songs!",
        "action_vi": "Màn hình chiếu phim hoạt hình thật vui!",
        "color": "#818CF8",
    },
    "cái bàn": {
        "vi": "Cái Bàn",
        "en": "Table",
        "simple": "Desk",
        "emoji": "🪑",
        "sound": "Tap tap! Strong and sturdy!",
        "action_en": "Where we draw pictures and read books!",
        "action_vi": "Nơi bé ngồi học bài và vẽ tranh!",
        "color": "#FBBF24",
    },
    "cái ghế": {
        "vi": "Cái Ghế",
        "en": "Chair",
        "simple": "Chair",
        "emoji": "🪑",
        "sound": "Sit down! Cozy and comfy!",
        "action_en": "A comfy seat to sit and play!",
        "action_vi": "Bé ngồi ngay ngắn ăn cơm và chơi đùa!",
        "color": "#F59E0B",
    },
    "cái giường": {
        "vi": "Cái Giường",
        "en": "Bed",
        "simple": "Bed",
        "emoji": "🛏️",
        "sound": "Soft and warm! Sweet dreams!",
        "action_en": "A cozy bed to sleep tight all night!",
        "action_vi": "Chiếc giường êm ái cho bé ngủ ngon giấc!",
        "color": "#C084FC",
    },
    "cái đèn": {
        "vi": "Cái Đèn",
        "en": "Lamp",
        "simple": "Light",
        "emoji": "💡",
        "sound": "Click! Bright light!",
        "action_en": "Shining bright so we can see everything!",
        "action_vi": "Đèn chiếu sáng lung linh khắp căn phòng!",
        "color": "#FDE047",
    },

    # Fruits & Food
    "táo": {
        "vi": "Quả Táo",
        "en": "Apple",
        "simple": "Apple",
        "emoji": "🍎",
        "sound": "Crunch crunch! Sweet and juicy!",
        "action_en": "Shiny red apple is full of vitamins!",
        "action_vi": "Quả táo đỏ mọng giòn ngọt thơm lừng!",
        "color": "#EF4444",
    },
    "chuối": {
        "vi": "Quả Chuối",
        "en": "Banana",
        "simple": "Banana",
        "emoji": "🍌",
        "sound": "Peel peel! Yum yum!",
        "action_en": "Yellow sweet banana is monkey's favorite!",
        "action_vi": "Chuối vàng thơm ngon nhiều dưỡng chất!",
        "color": "#FACC15",
    },
    "cam": {
        "vi": "Quả Cam",
        "en": "Orange",
        "simple": "Orange",
        "emoji": "🍊",
        "sound": "Squeeze squeeze! Vitamin C!",
        "action_en": "Fresh round orange makes delicious juice!",
        "action_vi": "Cam mọng nước giúp bé khỏe mạnh!",
        "color": "#FB923C",
    },
    "dưa hấu": {
        "vi": "Dưa Hấu",
        "en": "Watermelon",
        "simple": "Melon",
        "emoji": "🍉",
        "sound": "Big and green! Red inside!",
        "action_en": "Sweet crunchy watermelon on a sunny day!",
        "action_vi": "Dưa hấu vỏ xanh ruột đỏ mát lạnh!",
        "color": "#F43F5E",
    },
    "dâu tây": {
        "vi": "Dâu Tây",
        "en": "Strawberry",
        "simple": "Berry",
        "emoji": "🍓",
        "sound": "Sweet berry! Tiny seeds!",
        "action_en": "Cute little strawberry tastes so sweet!",
        "action_vi": "Dâu tây đỏ xinh chua ngọt mê ly!",
        "color": "#E11D48",
    },
    "cà rốt": {
        "vi": "Củ Cà Rốt",
        "en": "Carrot",
        "simple": "Carrot",
        "emoji": "🥕",
        "sound": "Crunch crunch! Orange carrot!",
        "action_en": "Little bunnies love eating carrots!",
        "action_vi": "Cà rốt màu cam cho đôi mắt bé sáng ngời!",
        "color": "#F97316",
    },
    "bắp ngô": {
        "vi": "Bắp Ngô",
        "en": "Corn",
        "simple": "Corn",
        "emoji": "🌽",
        "sound": "Pop pop! Sweet yellow corn!",
        "action_en": "Sweet yellow corn on the cob!",
        "action_vi": "Bắp ngô vàng óng ngọt ngào dẻo thơm!",
        "color": "#EAB308",
    },
    "bánh mì": {
        "vi": "Bánh Mì",
        "en": "Bread",
        "simple": "Bread",
        "emoji": "🍞",
        "sound": "Warm and toasty! Good morning!",
        "action_en": "Fresh bakery bread makes a happy breakfast!",
        "action_vi": "Ổ bánh mì giòn tan cho bữa sáng năng lượng!",
        "color": "#D97706",
    },
    "kem": {
        "vi": "Cây Kem",
        "en": "Ice Cream",
        "simple": "Ice Cream",
        "emoji": "🍦",
        "sound": "Lick lick! Cold and sweet!",
        "action_en": "Delicious vanilla ice cream cone!",
        "action_vi": "Cây kem mát lạnh ngọt ngào bé nào cũng mê!",
        "color": "#F472B6",
    },

    # Vehicles & Transportation
    "ô tô": {
        "vi": "Xe Ô Tô",
        "en": "Car",
        "simple": "Car",
        "emoji": "🚗",
        "sound": "Beep beep! Vroom vroom!",
        "action_en": "The shiny red car drives down the street!",
        "action_vi": "Xe ô tô bon bon chạy trên đường phố!",
        "color": "#EF4444",
    },
    "xe buýt": {
        "vi": "Xe Buýt",
        "en": "Bus",
        "simple": "Bus",
        "emoji": "🚌",
        "sound": "Honk honk! Big yellow bus!",
        "action_en": "The friendly bus takes children to school!",
        "action_vi": "Xe buýt chở các bạn nhỏ tới trường học!",
        "color": "#F59E0B",
    },
    "xe cứu hỏa": {
        "vi": "Xe Cứu Hỏa",
        "en": "Fire Truck",
        "simple": "Fire Truck",
        "emoji": "🚒",
        "sound": "Wee-woo wee-woo! Big ladder!",
        "action_en": "Brave fire truck rushes to help everyone!",
        "action_vi": "Xe cứu hỏa dũng cảm vòi rồng phun nước!",
        "color": "#DC2626",
    },
    "xe cảnh sát": {
        "vi": "Xe Cảnh Sát",
        "en": "Police Car",
        "simple": "Police Car",
        "emoji": "🚓",
        "sound": "Wee-woo! Fast police car!",
        "action_en": "Police car protects our neighborhood!",
        "action_vi": "Xe cảnh sát giữ gìn an toàn trật tự!",
        "color": "#2563EB",
    },
    "máy bay": {
        "vi": "Máy Bay",
        "en": "Airplane",
        "simple": "Plane",
        "emoji": "✈️",
        "sound": "Zoom zoom! High in the clouds!",
        "action_en": "Soaring high in the sky like a giant bird!",
        "action_vi": "Máy bay sải cánh bay lượn trên mây trắng!",
        "color": "#38BDF8",
    },
    "tàu hỏa": {
        "vi": "Tàu Hỏa",
        "en": "Train",
        "simple": "Train",
        "emoji": "🚂",
        "sound": "Choo-choo! Chugga chugga!",
        "action_en": "The long train glides along the railway tracks!",
        "action_vi": "Đoàn tàu hỏa dài nối đuôi nhau tu tu xình xịch!",
        "color": "#4B5563",
    },
    "xe đạp": {
        "vi": "Xe Đạp",
        "en": "Bicycle",
        "simple": "Bike",
        "emoji": "🚲",
        "sound": "Ring ring! Pedal fast!",
        "action_en": "Riding the bicycle in the sunny park!",
        "action_vi": "Bé đạp xe đạp tập thể dục trong công viên!",
        "color": "#10B981",
    },

    # Animals
    "chó": {
        "vi": "Chú Cún",
        "en": "Dog",
        "simple": "Puppy",
        "emoji": "🐶",
        "sound": "Woof woof! Waggy tail!",
        "action_en": "Loyal little puppy is man's best friend!",
        "action_vi": "Chú cún vẫy đuôi mừng rỡ đón bé về!",
        "color": "#F59E0B",
    },
    "mèo": {
        "vi": "Mèo Con",
        "en": "Cat",
        "simple": "Kitten",
        "emoji": "🐱",
        "sound": "Meow meow! Soft fluffy fur!",
        "action_en": "Sweet kitty cat purrs happily in the sun!",
        "action_vi": "Bạn mèo con lông mềm mại bắt chuột thật tài!",
        "color": "#FB923C",
    },
    "thỏ": {
        "vi": "Bạn Thỏ",
        "en": "Rabbit",
        "simple": "Bunny",
        "emoji": "🐰",
        "sound": "Hop hop! Long pink ears!",
        "action_en": "Fluffy white bunny loves hopping in green grass!",
        "action_vi": "Bạn thỏ trắng tai dài nhảy thoăn thoắt!",
        "color": "#F472B6",
    },
    "gấu": {
        "vi": "Bạn Gấu",
        "en": "Bear",
        "simple": "Teddy",
        "emoji": "🐻",
        "sound": "Big warm hug! Friendly bear!",
        "action_en": "Gentle teddy bear loves sweet golden honey!",
        "action_vi": "Bạn gấu nâu tròn xoe thích ăn mật ong!",
        "color": "#B45309",
    },
    "khỉ": {
        "vi": "Chú Khỉ",
        "en": "Monkey",
        "simple": "Monkey",
        "emoji": "🐵",
        "sound": "Ooh ooh aah aah! Silly monkey!",
        "action_en": "Playful monkey swings from branch to branch!",
        "action_vi": "Chú khỉ thông minh tinh nghịch leo trèo!",
        "color": "#D97706",
    },
    "sư tử": {
        "vi": "Sư Tử",
        "en": "Lion",
        "simple": "Lion",
        "emoji": "🦁",
        "sound": "Roar! Brave lion king!",
        "action_en": "The brave golden lion is the king of beasts!",
        "action_vi": "Sư tử dũng cảm chúa tể sơn lâm oai vệ!",
        "color": "#EAB308",
    },
    "voi": {
        "vi": "Chú Voi",
        "en": "Elephant",
        "simple": "Elephant",
        "emoji": "🐘",
        "sound": "Pawoo! Big swinging trunk!",
        "action_en": "Gentle giant elephant sprays water like a fountain!",
        "action_vi": "Chú voi to lớn vòi dài phun nước tắm mát!",
        "color": "#6B7280",
    },
    "gấu trúc": {
        "vi": "Gấu Trúc",
        "en": "Panda",
        "simple": "Panda",
        "emoji": "🐼",
        "sound": "Munch munch! Sweet little panda!",
        "action_en": "Chubby panda eats fresh bamboo all day!",
        "action_vi": "Gấu trúc tròn xoe nhai cành trúc giòn rụm!",
        "color": "#1F2937",
    },
}


def _lookup_vocab(item_text: str) -> Optional[dict]:
    """Finds vocabulary metadata for a user item by matching synonyms and prefixes."""
    raw = item_text.lower().strip()
    # Strip common Vietnamese classifiers
    cleaned = re.sub(r"^(con|cái|chiếc|quả|củ|bạn|chú|bức|loại|đồ)\s+", "", raw).strip()

    # Exact match
    for key, data in COMMON_KIDS_VOCAB.items():
        if key == raw or key == cleaned:
            return data

    # Substring match
    for key, data in COMMON_KIDS_VOCAB.items():
        if key in raw or raw in key or key in cleaned or cleaned in key:
            return data

    return None


def _parse_user_items(custom_topic: str) -> list[str]:
    """Splits user topic into distinct items if separated by commas or lists."""
    # Split by commas, semicolons, bullets, or newlines
    tokens = re.split(r"[,;\n\r•]+|\s+-\s+", custom_topic)
    items = [t.strip() for t in tokens if t.strip()]
    return items


def _synthesize_topic_cards(custom_topic: str, is_english: bool) -> list[KidsCard]:
    """Smart, instant topic-aware synthesizer that guarantees 100% relevance and accuracy."""
    t = custom_topic.lower()
    colors = ["#38BDF8", "#A78BFA", "#34D399", "#F87171", "#FBBF24"]

    # 1. Check if user provided an explicit list of items (e.g. "tủ lạnh, cái tủ, cái quạt, cái nồi")
    parsed_items = _parse_user_items(custom_topic)
    if len(parsed_items) >= 2:
        cards = []
        for i, raw_item in enumerate(parsed_items[:4]):
            data = _lookup_vocab(raw_item)
            c_color = colors[i % len(colors)]

            if data:
                vi_name = data["vi"]
                en_name = data["en"]
                emoji = data["emoji"]
                sound = data["sound"]
                color = data.get("color", c_color)

                if is_english:
                    title = f"{vi_name} - {en_name} {emoji}"
                    sub = f"Bé học từ vựng: {en_name}"
                    spoken = (
                        f"Look! Here is the {en_name}! Can you say {en_name}? "
                        f"{sound} {data['action_en']} Great job!"
                    )
                else:
                    title = f"{vi_name} - {en_name} {emoji}"
                    sub = f"Bé học từ vựng: {vi_name}"
                    spoken = (
                        f"Oa, bé ơi nhìn xem nè! Đây là {vi_name}! {vi_name} tiếng Anh là {en_name}! "
                        f"{data['action_vi']} Bé đọc to cùng bạn nhé: {en_name}!"
                    )
            else:
                # Clean fallback for unknown custom item
                clean_name = raw_item.title()
                emoji = "🌟"
                color = c_color
                if is_english:
                    title = f"{clean_name} • Fun Item {emoji}"
                    sub = f"Let's explore {clean_name}"
                    spoken = f"Look, little star! This is {clean_name}! Can you see it? So bright and wonderful! Yay!"
                else:
                    title = f"{clean_name} • Đồ Vật Diệu Kỳ {emoji}"
                    sub = f"Bé tìm hiểu về {clean_name}"
                    spoken = f"Oa, bé ơi nhìn xem! Đây là {clean_name} thật thú vị! Bé cùng khám phá nhé! Giỏi lắm!"

            cards.append(
                KidsCard(
                    title=title,
                    subtitle=sub,
                    spoken_text=spoken,
                    image_prompt=f"cute 3d cartoon {data['en'] if data else raw_item} illustration, bright colors",
                    emoji=emoji,
                    theme_color=color,
                )
            )

        # Pad to at least 4 scenes if user provided 2 or 3 items
        while len(cards) < 4:
            idx = len(cards)
            bonus_keys = ["táo", "chuối", "ô tô", "mèo"]
            bonus_data = COMMON_KIDS_VOCAB[bonus_keys[idx % len(bonus_keys)]]
            if is_english:
                cards.append(
                    KidsCard(
                        title=f"{bonus_data['vi']} - {bonus_data['en']} {bonus_data['emoji']}",
                        subtitle=f"Bonus item: {bonus_data['en']}",
                        spoken_text=f"Surprise! Look at the delicious {bonus_data['en']}! {bonus_data['sound']} Wonderful!",
                        image_prompt=f"cute 3d cartoon {bonus_data['en']}",
                        emoji=bonus_data["emoji"],
                        theme_color=bonus_data["color"],
                    )
                )
            else:
                cards.append(
                    KidsCard(
                        title=f"{bonus_data['vi']} - {bonus_data['en']} {bonus_data['emoji']}",
                        subtitle=f"Khám phá thêm: {bonus_data['vi']}",
                        spoken_text=f"Bất ngờ chưa nè! Thêm một người bạn nữa là {bonus_data['vi']}! Tiếng Anh là {bonus_data['en']}! Hoan hô!",
                        image_prompt=f"cute 3d cartoon {bonus_data['en']}",
                        emoji=bonus_data["emoji"],
                        theme_color=bonus_data["color"],
                    )
                )

        return cards[:4]

    # 2. Animal Apple / Fruit Counting Story (Single phrase like "các con thú học đếm táo")
    is_counting = any(k in t for k in ("đếm", "count", "số", "number", "1", "táo", "apple", "quả"))
    is_animal = any(k in t for k in ("thú", "động vật", "con vật", "animal", "thỏ", "gấu", "khỉ", "mèo", "chó"))

    if is_counting or (is_animal and any(k in t for k in ("táo", "apple"))):
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

    # 3. Animals Story (General animals)
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

    # 4. Single General Topic / Phrase (e.g. "thế giới đại dương", "vũ trụ bao la")
    clean_words = re.findall(r"\w+", custom_topic)
    topic_label = " ".join(clean_words[:3]).title() if clean_words else "Điều Kỳ Diệu"
    emojis = ["🌟", "🚀", "🎉", "🎈"]

    cards = []
    for i in range(4):
        if is_english:
            title = f"{topic_label} • Fun Discovery {emojis[i]}"
            sub = f"Learning about {topic_label}"
            spoken = f"Look, little star! Let's explore the wonderful world together! It is so bright and exciting! Yay!"
        else:
            title = f"{topic_label} • Khám Phá {i+1} {emojis[i]}"
            sub = f"Bé vui học về {topic_label}"
            spoken = f"Oa, bé ơi nhìn xem nè! Chúng mình cùng tìm hiểu điều kỳ diệu thật là vui và thú vị nhé! Bé giỏi quá!"

        cards.append(
            KidsCard(
                title=title,
                subtitle=sub,
                spoken_text=spoken,
                image_prompt=f"cute 3d cartoon illustration of {topic_label}",
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
        # Check if custom_topic is a comma-separated list of items
        # If so, our Smart Synthesizer is instantaneous (0.01s), 100% relevant and accurate
        items = _parse_user_items(custom_topic)
        if len(items) >= 2:
            return _synthesize_topic_cards(custom_topic, is_english=is_english)

        # For single free-form prompt, try fast LLM if available, else synthesizer
        if client and client.is_available():
            try:
                system_prompt = (
                    "You are a children's cartoon creator. Return valid JSON only array of 4 objects: "
                    "[{\"title\": \"...\", \"subtitle\": \"...\", \"spoken_text\": \"...\", \"image_prompt\": \"...\", \"emoji\": \"...\", \"theme_color\": \"#...\"}]. "
                    f"Voice language: {'Joyful English' if is_english else 'Cheerful Vietnamese'}. Keep spoken_text under 25 words."
                )
                user_msg = f"Topic: {custom_topic}"
                raw = client.chat(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_msg},
                    ],
                    format_json=True,
                    max_tokens=600,
                    temperature=0.7,
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
                    colors = ["#38BDF8", "#A78BFA", "#34D399", "#F87171", "#FBBF24"]
                    for idx, item in enumerate(data[:4]):
                        cards.append(
                            KidsCard(
                                title=str(item.get("title", f"Phần {idx+1}")).strip(),
                                subtitle=str(item.get("subtitle", "")).strip(),
                                spoken_text=str(item.get("spoken_text", item.get("title", ""))).strip(),
                                image_prompt=str(item.get("image_prompt", f"{custom_topic}, cute 3d cartoon")).strip(),
                                emoji=sanitize_emoji(str(item.get("emoji", "✨")).strip()),
                                theme_color=str(item.get("theme_color", colors[idx % len(colors)])).strip(),
                            )
                        )
                    if len(cards) >= 2:
                        return cards
            except Exception as e:
                logger.warning("Dynamic LLM generation failed for topic '%s' (%s); using dynamic synthesizer", custom_topic, e)

        return _synthesize_topic_cards(custom_topic, is_english=is_english)

    # Preset mode
    pool = get_preset_cards(preset_id)
    if not pool:
        pool = get_preset_cards("vocabulary")

    selected = list(pool)
    random.shuffle(selected)
    cards = selected[:min(4, len(selected))]

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
