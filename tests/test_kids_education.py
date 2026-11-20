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
