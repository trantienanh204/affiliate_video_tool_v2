"""Tests for Fast Story Generator."""

import pytest
from unittest.mock import MagicMock
from models.story import FastStoryInput, FastStoryResult, StoryLength
from ai.story.fast_generator import generate_fast_story, get_instant_template_story


def test_fast_story_input_defaults():
    inp = FastStoryInput(premise="Cô bé tìm thấy chiếc chìa khóa thần kỳ")
    assert inp.protagonist == "An Nhiên"
    assert inp.length == StoryLength.MEDIUM
    assert "chìa khóa thần kỳ" in inp.premise


def test_instant_template_story():
    inp = FastStoryInput(
        trope="Thiên kim thật giả / tráo đổi thân phận",
        premise="Cô gái phát hiện gia đình tỷ phú nhận nhầm con",
        protagonist="Bảo Ngọc",
        length=StoryLength.SHORT,
    )
    result = get_instant_template_story(inp)
    assert isinstance(result, FastStoryResult)
    assert result.title
    assert result.hook
    assert result.content
    assert result.word_count > 50
    assert result.mode == "template"
    assert "Bảo Ngọc" in result.content or "Bảo Ngọc" in result.hook


def test_fast_story_generator_with_fallback():
    """When client is unavailable, generate_fast_story should fallback smoothly to template."""
    mock_client = MagicMock()
    mock_client.is_available.return_value = False

    inp = FastStoryInput(
        trope="Bị phản bội, bắt đầu lại",
        premise="Người thừa kế bị hãm hại nhưng bí mật phục thù",
        protagonist="Minh Triết",
        length=StoryLength.MEDIUM,
    )
    result = generate_fast_story(inp, client=mock_client)
    assert isinstance(result, FastStoryResult)
    assert len(result.content) > 100
    assert result.word_count > 0
    assert result.mode == "template"


def test_fast_story_generator_with_llm_success():
    """When LLM returns valid JSON, generate_fast_story parses and returns it."""
    mock_client = MagicMock()
    mock_client.is_available.return_value = True
    mock_client.chat.return_value = '''```json
    {
        "title": "Bão Tố Gia Tộc",
        "hook": "An Nhiên đứng trước cánh cổng gia tộc với bí mật kinh hoàng.",
        "content": "An Nhiên bước vào phòng khách. Mọi ánh mắt đổ dồn về phía cô.\\n\\nCuối cùng sự thật cũng sáng tỏ.",
        "caption": "Bí mật gia tộc hé lộ",
        "hashtags": ["#drama", "#story"]
    }
    ```'''

    inp = FastStoryInput(
        trope="Gia đình",
        premise="Bí mật gia tộc",
        protagonist="An Nhiên",
        length=StoryLength.SHORT,
    )
    result = generate_fast_story(inp, client=mock_client)
    assert isinstance(result, FastStoryResult)
    assert result.title == "Bão Tố Gia Tộc"
    assert result.mode == "ollama"
    assert result.word_count > 0
