"""Presets and data structures for Kids Education videos."""

from __future__ import annotations

from pydantic import BaseModel, Field


class KidsCard(BaseModel):
    """A single flashcard scene in a kids education video."""
    title: str = Field(description="Tiêu đề chính (ví dụ: 'Quả Táo - Apple' hoặc 'Số 1')")
    subtitle: str = Field(default="", description="Phụ đề phiên âm hoặc giải thích ngắn")
    spoken_text: str = Field(description="Nội dung giọng đọc chuẩn tiếng Việt / Anh")
    image_prompt: str = Field(description="Prompt sinh ảnh hoạt họa rực rỡ")
    emoji: str = Field(default="✨", description="Icon hoặc emoji đại diện")
    theme_color: str = Field(default="#4ECDC4", description="Mã màu chủ đạo của thẻ")


_PRESETS_DATA: dict[str, dict] = {
    "vocabulary": {
        "id": "vocabulary",
        "name": "🍎 Bé Học Từ Vựng Song Ngữ",
        "description": "Các từ vựng tiếng Anh - Việt gần gũi với hình ảnh sinh động",
        "cards": [
            KidsCard(
                title="Quả Táo - Apple",
                subtitle="/ˈæp.əl/ • Quả táo màu đỏ ngọt lịm",
                spoken_text="Quả táo. Tiếng Anh đọc là Apple. Apple!",
                image_prompt="a cute glossy red cartoon apple smiling with cute eyes in a basket, 3d pixar style, vibrant colors",
                emoji="🍎",
                theme_color="#FF6B6B",
            ),
            KidsCard(
                title="Quả Chuối - Banana",
                subtitle="/bəˈnæn.ə/ • Quả chuối màu vàng cong cong",
                spoken_text="Quả chuối. Tiếng Anh đọc là Banana. Banana!",
                image_prompt="a cute friendly cartoon yellow banana waving hand, 3d pixar style, vibrant pastel colors",
                emoji="🍌",
                theme_color="#FFE66D",
            ),
            KidsCard(
                title="Xe Hơi - Car",
                subtitle="/kɑːr/ • Chiếc xe ô tô chạy bon bon",
                spoken_text="Xe hơi. Tiếng Anh đọc là Car. Car!",
                image_prompt="a cute colorful red toy car cartoon with friendly headlights, 3d pixar style, soft background",
                emoji="🚗",
                theme_color="#4D96FF",
            ),
            KidsCard(
                title="Mặt Trời - Sun",
                subtitle="/sʌn/ • Mặt trời tỏa ánh nắng ấm áp",
                spoken_text="Mặt trời. Tiếng Anh đọc là Sun. Sun!",
                image_prompt="a smiling happy cartoon sun wearing sunglasses, bright warm morning sky, 3d pixar style",
                emoji="☀️",
                theme_color="#FFB300",
            ),
        ],
    },
    "numbers": {
        "id": "numbers",
        "name": "🔢 Bé Học Đếm Số 1 Đến 5",
        "description": "Học đếm số vui nhộn cùng các con vật và đồ vật dễ thương",
        "cards": [
            KidsCard(
                title="Số 1 - One",
                subtitle="Một chú mèo con đáng yêu",
                spoken_text="Số một. One. Có một chú mèo con!",
                image_prompt="one cute fluffy kitten playing with yarn ball, bright colorful nursery background, 3d pixar style",
                emoji="🐱",
                theme_color="#FF8E72",
            ),
            KidsCard(
                title="Số 2 - Two",
                subtitle="Hai chú thỏ ngọc trắng tinh",
                spoken_text="Số hai. Two. Có hai chú thỏ trắng!",
                image_prompt="two adorable cute white bunnies holding carrots, green grass meadow, 3d pixar style",
                emoji="🐰",
                theme_color="#6BCB77",
            ),
            KidsCard(
                title="Số 3 - Three",
                subtitle="Ba chú cún con tung tăng",
                spoken_text="Số ba. Three. Có ba chú cún con!",
                image_prompt="three playful cute puppies smiling together, sunny park background, 3d pixar style",
                emoji="🐶",
                theme_color="#4D96FF",
            ),
            KidsCard(
                title="Số 4 - Four",
                subtitle="Bốn quả bóng bay rực rỡ",
                spoken_text="Số bốn. Four. Có bốn quả bóng bay nhiều màu!",
                image_prompt="four colorful bright balloons floating in blue sky, 3d pixar style",
                emoji="🎈",
                theme_color="#9D4EDD",
            ),
            KidsCard(
                title="Số 5 - Five",
                subtitle="Năm ngôi sao lấp lánh",
                spoken_text="Số năm. Five. Bé đã đếm được năm ngôi sao rồi!",
                image_prompt="five glowing cute smiling stars in gentle night sky, 3d pixar style",
                emoji="⭐",
                theme_color="#FFD93D",
            ),
        ],
    },
    "animals": {
        "id": "animals",
        "name": "🦁 Khám Phá Thế Giới Động Vật",
        "description": "Nhận biết các loài động vật hoang dã và vật nuôi thân quen",
        "cards": [
            KidsCard(
                title="Sư Tử - Lion",
                subtitle="/ˈlaɪ.ən/ • Chúa sơn lâm oai phong",
                spoken_text="Sư tử. Tiếng Anh là Lion. Chú sư tử dũng mãnh gầm vang!",
                image_prompt="a cute friendly baby lion with small fluffy mane sitting on rock, savannah, 3d pixar style",
                emoji="🦁",
                theme_color="#F4A261",
            ),
            KidsCard(
                title="Chú Voi - Elephant",
                subtitle="/ˈel.ɪ.fənt/ • Chú voi có chiếc vòi dài",
                spoken_text="Chú voi. Tiếng Anh là Elephant. Voi có chiếc vòi dài thông minh!",
                image_prompt="a cute baby elephant spraying water happily, sunny safari river, 3d pixar style",
                emoji="🐘",
                theme_color="#48CAE4",
            ),
            KidsCard(
                title="Cá Heo - Dolphin",
                subtitle="/ˈdɒl.fɪn/ • Bạn cá heo thích bơi lội",
                spoken_text="Cá heo. Tiếng Anh là Dolphin. Cá heo bơi lội và nhảy múa trên biển!",
                image_prompt="a joyful cute cartoon dolphin jumping out of crystal blue ocean, 3d pixar style",
                emoji="🐬",
                theme_color="#0077B6",
            ),
            KidsCard(
                title="Khỉ Con - Monkey",
                subtitle="/ˈmʌŋ.ki/ • Chú khỉ tinh nghịch leo trèo",
                spoken_text="Khỉ con. Tiếng Anh là Monkey. Chú khỉ thích ăn chuối và leo trèo!",
                image_prompt="a cute cheeky little monkey hanging on jungle branch holding banana, 3d pixar style",
                emoji="🐒",
                theme_color="#E76F51",
            ),
        ],
    },
    "riddles": {
        "id": "riddles",
        "name": "🧩 Câu Đố Vui Cho Bé",
        "description": "Những câu đố thông minh kích thích trí tưởng tượng của bé",
        "cards": [
            KidsCard(
                title="Con gì mào đỏ gáy vang?",
                subtitle="Gợi ý: Đánh thức mọi người thức dậy mỗi sáng!",
                spoken_text="Đố bé: Con gì mào đỏ, gáy ò ó o gọi mặt trời thức giấc?",
                image_prompt="a cute colorful cartoon rooster crowing on a wooden fence at sunrise, 3d pixar style",
                emoji="❓",
                theme_color="#E63946",
            ),
            KidsCard(
                title="Đáp Án: Chú Gà Trống!",
                subtitle="Đúng rồi, bé thật thông minh!",
                spoken_text="Đáp án chính xác: Đó là Chú Gà Trống! Hoan hô bé đã đoán đúng!",
                image_prompt="a happy handsome cartoon rooster smiling with golden trophy, confetti, 3d pixar style",
                emoji="🎉",
                theme_color="#52B788",
            ),
            KidsCard(
                title="Quả gì vỏ xanh ruột đỏ?",
                subtitle="Gợi ý: Hạt đen nhánh, ăn vào mát ngọt mùa hè!",
                spoken_text="Đố bé tiếp nè: Quả gì vỏ màu xanh, ruột màu đỏ thắm, nhiều hạt đen nhỏ?",
                image_prompt="a big juicy green striped watermelon sliced in half, 3d pixar style, sunny summer picnic",
                emoji="❓",
                theme_color="#2A9D8F",
            ),
            KidsCard(
                title="Đáp Án: Quả Dưa Hấu!",
                subtitle="Dưa hấu mát ngọt giải nhiệt!",
                spoken_text="Đáp án là: Quả Dưa Hấu! Bé rất giỏi!",
                image_prompt="a smiling cartoon slice of watermelon with sunglasses, tropical beach, 3d pixar style",
                emoji="🍉",
                theme_color="#E76F51",
            ),
        ],
    },
    "moral_stories": {
        "id": "moral_stories",
        "name": "📖 Bài Học Bé Ngoan",
        "description": "Câu chuyện rèn luyện thói quen tốt và lòng biết ơn cho bé",
        "cards": [
            KidsCard(
                title="Nói Lời Cảm Ơn",
                subtitle="Khi được người khác giúp đỡ",
                spoken_text="Khi được ông bà, cha mẹ hoặc bạn bè giúp đỡ, bé hãy nhớ mỉm cười và nói: Con cảm ơn ạ!",
                image_prompt="a polite cute little child bowing and saying thank you to parents, cozy warm home, 3d pixar style",
                emoji="🙏",
                theme_color="#F77F00",
            ),
            KidsCard(
                title="Biết Nói Xin Lỗi",
                subtitle="Khi lỡ làm điều chưa đúng",
                spoken_text="Khi vô tình làm vỡ đồ chơi hay làm bạn buồn, một lời xin lỗi chân thành sẽ giúp mọi người vui vẻ trở lại.",
                image_prompt="a cute gentle child apologizing to friend with a hug, colorful playroom, 3d pixar style",
                emoji="🤝",
                theme_color="#00A896",
            ),
            KidsCard(
                title="Biết Chia Sẻ",
                subtitle="Cùng chơi với bạn bè",
                spoken_text="Đồ chơi và niềm vui khi được chia sẻ cùng bạn bè sẽ nhân đôi niềm hạnh phúc!",
                image_prompt="two adorable happy kids sharing colorful wooden building blocks together, bright smiling, 3d pixar style",
                emoji="💖",
                theme_color="#FCBF49",
            ),
        ],
    },
}


def get_available_presets() -> list[dict]:
    """Return all preset summaries for UI dropdowns."""
    return [
        {
            "id": p["id"],
            "name": p["name"],
            "description": p["description"],
            "count": len(p["cards"]),
        }
        for p in _PRESETS_DATA.values()
    ]


def get_preset_cards(preset_id: str) -> list[KidsCard]:
    """Retrieve the cards for a specific preset ID."""
    preset = _PRESETS_DATA.get(preset_id)
    if preset:
        return list(preset["cards"])
    return list(_PRESETS_DATA["vocabulary"]["cards"])
