"""Tests for Kids Education Video Engine."""

import pytest
from pathlib import Path
from video.kids_education.presets import get_available_presets, get_preset_cards, KidsCard
from video.kids_education.canvas import create_flashcard_image
from video.kids_education.generator import render_kids_education_video


def test_get_available_presets():
    presets = get_available_presets()
    assert len(presets) >= 4
    preset_ids = [p["id"] for p in presets]
    assert "vocabulary" in preset_ids
    assert "animals" in preset_ids
    assert "numbers" in preset_ids


def test_get_preset_cards():
    cards = get_preset_cards("animals")
    assert len(cards) >= 3
    card = cards[0]
    assert isinstance(card, KidsCard)
    assert card.title
    assert card.spoken_text
    assert card.image_prompt


def test_create_flashcard_image(tmp_path):
    card = KidsCard(
        title="Quả Táo - Apple",
        subtitle="/ˈæp.əl/ - Trái cây thơm ngon giàu vitamin",
        spoken_text="Quả táo, tiếng Anh là Apple.",
        image_prompt="cute red apple cartoon",
        emoji="🍎",
        theme_color="#FF6B6B",
    )
    out_file = tmp_path / "card_test.png"
    result = create_flashcard_image(card, out_file, width=540, height=960)
    assert result.is_file()
    assert result.stat().st_size > 1000


def test_render_kids_video_offline(tmp_path):
    """Test rendering a quick 2-card video in silent/offline mode."""
    cards = [
        KidsCard(
            title="Số 1 - One",
            subtitle="Một chú mèo con",
            spoken_text="Số một, One",
            image_prompt="cute cat",
            emoji="🐱",
            theme_color="#FF8E72",
        ),
        KidsCard(
            title="Số 2 - Two",
            subtitle="Hai chú thỏ ngọc",
            spoken_text="Số hai, Two",
            image_prompt="cute bunny",
            emoji="🐰",
            theme_color="#6BCB77",
        ),
    ]
    out_mp4 = tmp_path / "kids_test.mp4"
    res = render_kids_education_video(
        cards,
        output_path=out_mp4,
        enable_tts=False,
    )
    assert res.is_file()
    assert res.stat().st_size > 5000


def test_save_result_flexible_signature():
    """Verify save_result can be called with kwargs without raising TypeError."""
    from services.history import save_result
    # Should not raise TypeError: save_result() got an unexpected keyword argument 'job_id'
    save_result(
        job_id="test_job_12345",
        status="completed",
        video_path="outputs/test.mp4",
        product_name="Test Product",
        category="Kids",
        concept="Preset english_basics",
        scenes_count=4,
        duration=14.0,
        meta={"preset": "english_basics"},
    )


def test_new_fun_and_english_presets():
    """Verify new English learning and funny cartoon presets exist."""
    presets = get_available_presets()
    preset_ids = [p["id"] for p in presets]
    assert "english_basics" in preset_ids
    assert "english_phonics" in preset_ids
    assert "funny_cartoons" in preset_ids
    assert "happy_dance" in preset_ids

    funny_cards = get_preset_cards("funny_cartoons")
    assert len(funny_cards) >= 4
    assert any("Mèo" in c.title or "Cún" in c.title for c in funny_cards)

    english_cards = get_preset_cards("english_basics")
    assert len(english_cards) >= 4
    assert any("Hello" in c.title or "Thank You" in c.title for c in english_cards)


def test_english_voice_resolution():
    """Verify that English neural voices resolve properly."""
    from tts.edge import resolve_voice, VOICES
    assert "Bé gái Mỹ dễ thương (Ana US - Tiếng Anh)" in VOICES
    assert resolve_voice("Bé gái Mỹ dễ thương (Ana US - Tiếng Anh)") == "en-US-AnaNeural"
    assert resolve_voice("en-US-JennyNeural") == "en-US-JennyNeural"


def test_dynamic_kids_cards_generation():
    """Verify dynamic cards generation for custom topic and anti-repetition."""
    from video.kids_education.dynamic_generator import generate_dynamic_kids_cards

    # 1. Custom topic
    cards = generate_dynamic_kids_cards(custom_topic="Khủng long T-Rex và các loại xe cứu hộ")
    assert len(cards) == 4
    assert any("Khủng long" in c.title or "cứu hộ" in c.title or "Khám Phá" in c.title for c in cards)

    # 2. Preset dynamic randomization
    cards_preset = generate_dynamic_kids_cards(preset_id="funny_cartoons")
    assert len(cards_preset) == 4
    assert cards_preset[0].spoken_text  # Has randomized intro hook


def test_kids_bgm_asset():
    """Verify cheerful background music asset exists."""
    bgm = Path("assets/music/kids_cheerful.wav")
    assert bgm.is_file()
    assert bgm.stat().st_size > 100000


def test_emoji_sanitization():
    """Verify Slack-style :emoji: codes are cleanly converted to true Unicode."""
    from video.kids_education.canvas import sanitize_emoji
    assert sanitize_emoji(":frog:") == "🐸"
    assert sanitize_emoji(":cat_face:") == "🐱"
    assert sanitize_emoji(":apple:") == "🍎"
    assert sanitize_emoji(":rabbit:") == "🐰"
    assert sanitize_emoji(":bear:") == "🐻"
    assert sanitize_emoji("⭐") == "⭐"
    # Unmapped colon code should not output raw code string
    res = sanitize_emoji(":unknown_code_foo:")
    assert ":" not in res


def test_title_auto_fit_no_overflow(tmp_path):
    """Verify long titles scale down and never overflow the card bounds."""
    from PIL import Image, ImageDraw
    from video.kids_education.canvas import _fit_text, create_flashcard_image

    img = Image.new("RGB", (1080, 1920), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    long_title = "4 Quả Táo - Four Apples - Bé Vui Học Đếm Cùng Muông Thú"
    font, bbox = _fit_text(draw, long_title, max_width=880, initial_size=90, min_size=20, bold=True)
    w = bbox[2] - bbox[0]
    assert w <= 880

    card = KidsCard(
        title=long_title,
        subtitle="Subtitle that is also quite long and should be wrapped automatically by textwrap",
        spoken_text="Hello apples",
        image_prompt="cute cartoon apple",
        emoji=":frog:",  # Test that :frog: is sanitized
        theme_color="#FF6B6B",
    )
    out_file = tmp_path / "long_card.png"
    result = create_flashcard_image(card, out_file)
    assert result.is_file()
    assert result.stat().st_size > 20000


def test_animals_counting_apples_topic():
    """Verify the user topic 'các con thú học đếm táo' generates matching animal & apple counting cards."""
    from video.kids_education.dynamic_generator import generate_dynamic_kids_cards

    # Vietnamese voice
    cards_vi = generate_dynamic_kids_cards(
        custom_topic="các con thú học đếm táo",
        voice_name="vi-VN-HoaiMyNeural",
    )
    assert len(cards_vi) == 4
    assert any("Thỏ" in c.title or "1 Quả Táo" in c.title for c in cards_vi)
    assert any("Gấu" in c.title or "2 Quả Táo" in c.title for c in cards_vi)
    assert any("Khỉ" in c.title or "3 Quả Táo" in c.title for c in cards_vi)
    assert any("4 Quả Táo" in c.title or "Four Apples" in c.title for c in cards_vi)
    for c in cards_vi:
        assert ":" not in c.emoji  # No slack format emojis

    # English voice (Ana US)
    cards_en = generate_dynamic_kids_cards(
        custom_topic="các con thú học đếm táo",
        voice_name="en-US-AnaNeural",
    )
    assert len(cards_en) == 4
    # Spoken text should be in joyful English
    assert any("apple" in c.spoken_text.lower() for c in cards_en)
    assert any("bunny" in c.spoken_text.lower() or "bear" in c.spoken_text.lower() for c in cards_en)
    for c in cards_en:
        assert ":" not in c.emoji



