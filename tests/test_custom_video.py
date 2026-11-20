"""Tests for Custom Prompt Video Generator."""

import pytest
from pathlib import Path
from video.custom.generator import (
    CustomScene,
    parse_prompt_to_scenes,
    create_custom_scene_image,
    render_custom_video,
)


def test_parse_prompt_to_scenes_default():
    prompt = "3 mẹo quản lý chi tiêu thông minh cho sinh viên"
    scenes = parse_prompt_to_scenes(prompt, target_scenes=3)
    assert len(scenes) >= 3
    assert all(isinstance(s, CustomScene) for s in scenes)
    assert any("chi tiêu" in s.script.lower() or "sinh viên" in s.script.lower() or "mẹo" in s.script.lower() for s in scenes)


def test_create_custom_scene_image(tmp_path):
    scene = CustomScene(
        title="Mẹo 1: Lập Ngân Sách",
        script="Ghi chép lại mọi khoản chi tiêu nhỏ nhất mỗi ngày.",
        image_prompt="student budgeting notes, cozy cafe desk",
    )
    out_img = tmp_path / "custom_scene_test.png"
    result = create_custom_scene_image(scene, out_img, width=540, height=960)
    assert result.is_file()
    assert result.stat().st_size > 1000


def test_render_custom_video_offline(tmp_path):
    scenes = [
        CustomScene(
            title="Đà Lạt Mộng Mơ",
            script="Chào mừng bạn đến với thành phố ngàn hoa.",
            image_prompt="dalat pine forest mist morning",
        ),
        CustomScene(
            title="Hồ Xuân Hương",
            script="Mặt hồ êm đềm trong sương sớm mai.",
            image_prompt="xuan huong lake dalat sunrise",
        ),
    ]
    out_mp4 = tmp_path / "custom_video_test.mp4"
    res = render_custom_video(
        scenes=scenes,
        output_path=out_mp4,
        enable_tts=False,
    )
    assert res.is_file()
    assert res.stat().st_size > 5000
