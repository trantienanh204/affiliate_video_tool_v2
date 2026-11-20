"""Custom Prompt Video Engine (0đ cost, MoviePy 2D/2.5D, Edge-TTS)."""

from __future__ import annotations

import io
import json
import re
import urllib.parse
from pathlib import Path
from typing import Callable, Optional

import httpx
from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel, Field

from core.config import settings
from core.logging import get_logger
from tts.edge import generate_tts, resolve_voice

logger = get_logger(__name__)

ProgressCb = Optional[Callable[[float, str], None]]


class CustomScene(BaseModel):
    title: str = Field(description="Tiêu đề phân cảnh (ví dụ: 'Mẹo 1: Lập Ngân Sách')")
    script: str = Field(description="Lời thoại thuyết minh cho phân cảnh")
    image_prompt: str = Field(default="", description="Prompt mô tả hình ảnh minh họa")
    user_image_path: Optional[str] = Field(default=None, description="Đường dẫn ảnh người dùng tự upload (nếu có)")


def _get_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    font_candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for p in font_candidates:
        if Path(p).is_file():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    try:
        return ImageFont.truetype("arial.ttf", size)
    except Exception:
        return ImageFont.load_default()


def parse_prompt_to_scenes(prompt: str, target_scenes: int = 4, client=None) -> list[CustomScene]:
    """
    Parses a user's prompt or requirement into cohesive visual scenes.
    Uses Ollama if reachable; otherwise uses intelligent syntactic rule breakdown.
    """
    clean_prompt = prompt.strip()
    if not clean_prompt:
        clean_prompt = "Khám phá những mẹo hữu ích trong cuộc sống hàng ngày."

    if client and client.is_available():
        try:
            sys_msg = (
                "Bạn là chuyên gia biên kịch video ngắn TikTok 9:16. "
                "Hãy chia chủ đề của người dùng thành các phân cảnh liền mạch. "
                "Trả về duy nhất JSON: [{\"title\": \"...\", \"script\": \"...\", \"image_prompt\": \"...\"}]"
            )
            raw = client.chat(
                messages=[
                    {"role": "system", "content": sys_msg},
                    {"role": "user", "content": f"Chủ đề: {clean_prompt}\nSố cảnh: {target_scenes}"},
                ],
                format_json=True,
                max_tokens=1000,
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
                data = data.get("scenes", [data])
            if isinstance(data, list) and len(data) > 0:
                scenes = []
                for item in data[:target_scenes]:
                    scenes.append(
                        CustomScene(
                            title=str(item.get("title", f"Cảnh {len(scenes) + 1}")).strip(),
                            script=str(item.get("script", clean_prompt)).strip(),
                            image_prompt=str(item.get("image_prompt", clean_prompt)).strip(),
                        )
                    )
                if scenes:
                    return scenes
        except Exception as exc:
            logger.warning("LLM scene parsing failed (%s); falling back to rule parser", exc)

    # Fallback rule-based scene breakdown
    sentences = [s.strip() for s in re.split(r"[.\n;!?]+", clean_prompt) if len(s.strip()) > 5]
    if not sentences:
        sentences = [clean_prompt]

    scenes = []
    if len(sentences) >= target_scenes:
        step = max(1, len(sentences) // target_scenes)
        for i in range(min(target_scenes, len(sentences))):
            idx = min(i * step, len(sentences) - 1)
            scenes.append(
                CustomScene(
                    title=f"Phần {i + 1}: {sentences[idx][:28]}",
                    script=sentences[idx],
                    image_prompt=f"{sentences[idx]}, cinematic lighting, high quality 4k wallpaper",
                )
            )
    else:
        # Pad with engaging hooks
        hooks = [
            f"Bí Quyết: {clean_prompt[:30]}",
            "Điểm Mấu Chốt Cần Nhớ",
            "Hành Động Ngay Hôm Nay",
            "Lời Khuyên Dành Cho Bạn",
        ]
        for i in range(target_scenes):
            sent = sentences[i % len(sentences)]
            scenes.append(
                CustomScene(
                    title=hooks[i % len(hooks)],
                    script=f"{hooks[i % len(hooks)]}. {sent}",
                    image_prompt=f"{sent}, clean minimalist artistic photography",
                )
            )

    return scenes


def create_custom_scene_image(
    scene: CustomScene,
    output_path: Path,
    width: int = 1080,
    height: int = 1920,
    center_img: Image.Image | None = None,
) -> Path:
    """Renders a sleek cinematic 9:16 slide with text overlay."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Dark modern canvas
    img = Image.new("RGB", (width, height), (15, 23, 42))
    draw = ImageDraw.Draw(img)

    # Illustration / Center Image
    inner_w = int(width * 0.90)
    inner_h = int(height * 0.52)
    inner_x = (width - inner_w) // 2
    inner_y = int(height * 0.18)

    if center_img:
        try:
            resized = center_img.convert("RGB").resize((inner_w, inner_h), Image.Resampling.LANCZOS)
            img.paste(resized, (inner_x, inner_y))
            draw.rectangle([(inner_x, inner_y), (inner_x + inner_w, inner_y + inner_h)], outline=(56, 189, 248), width=4)
        except Exception:
            center_img = None

    if center_img is None:
        draw.rounded_rectangle(
            [(inner_x, inner_y), (inner_x + inner_w, inner_y + inner_h)],
            radius=int(width * 0.03),
            fill=(30, 41, 59),
            outline=(56, 189, 248),
            width=4,
        )
        c_x = inner_x + inner_w // 2
        c_y = inner_y + inner_h // 2
        draw.ellipse([(c_x - 120, c_y - 120), (c_x + 120, c_y + 120)], fill=(56, 189, 248))
        f_icon = _get_font(110, bold=True)
        draw.text((c_x, c_y), "💡", font=f_icon, fill=(255, 255, 255), anchor="mm")

    # Header Badge
    badge_w = int(width * 0.65)
    badge_h = int(height * 0.055)
    bx1 = (width - badge_w) // 2
    by1 = int(height * 0.08)
    draw.rounded_rectangle([(bx1, by1), (bx1 + badge_w, by1 + badge_h)], radius=badge_h // 2, fill=(30, 41, 59), outline=(56, 189, 248), width=2)
    b_font = _get_font(int(height * 0.024), bold=True)
    draw.text((width // 2, by1 + badge_h // 2), scene.title, font=b_font, fill=(56, 189, 248), anchor="mm")

    # Script Box at bottom
    box_y1 = inner_y + inner_h + int(height * 0.04)
    box_y2 = int(height * 0.90)
    draw.rounded_rectangle([(inner_x, box_y1), (inner_x + inner_w, box_y2)], radius=int(width * 0.03), fill=(30, 41, 59))

    # Wrapped text
    script_font = _get_font(int(height * 0.028), bold=False)
    # Simple word wrap
    words = scene.script.split()
    lines = []
    cur_line = ""
    for w in words:
        test_line = f"{cur_line} {w}".strip()
        if len(test_line) > 36:
            lines.append(cur_line)
            cur_line = w
        else:
            cur_line = test_line
    if cur_line:
        lines.append(cur_line)

    text_y = box_y1 + int(height * 0.04)
    for line in lines[:4]:
        draw.text((width // 2, text_y), line, font=script_font, fill=(241, 245, 249), anchor="mm")
        text_y += int(height * 0.045)

    img.save(output_path, quality=95)
    return output_path


def download_or_fetch_scene_image(scene: CustomScene, output_path: Path) -> Path:
    """Fetch image from user upload, Pollinations AI, or fallback to canvas."""
    if scene.user_image_path and Path(scene.user_image_path).is_file():
        try:
            user_img = Image.open(scene.user_image_path)
            return create_custom_scene_image(scene, output_path, center_img=user_img)
        except Exception:
            pass

    center_img: Image.Image | None = None
    if scene.image_prompt:
        try:
            prompt_enc = urllib.parse.quote(scene.image_prompt[:150])
            url = f"https://image.pollinations.ai/prompt/{prompt_enc}?width=768&height=768&nologo=true"
            with httpx.Client(timeout=6.0) as client:
                r = client.get(url)
                if r.status_code == 200 and len(r.content) > 1000:
                    center_img = Image.open(io.BytesIO(r.content))
        except Exception as e:
            logger.warning("Custom image generation skipped (%s)", e)

    return create_custom_scene_image(scene, output_path, center_img=center_img)


def render_custom_video(
    scenes: list[CustomScene],
    output_path: Path,
    voice_name: str = "vi-VN-HoaiMyNeural",
    enable_tts: bool = True,
    progress_cb: ProgressCb = None,
) -> Path:
    """Assembles Custom Video with MoviePy."""
    from moviepy import AudioFileClip, ImageClip, concatenate_videoclips

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    temp_dir = output_path.parent / "custom_assets"
    temp_dir.mkdir(parents=True, exist_ok=True)

    clips = []
    total = len(scenes)

    for i, scene in enumerate(scenes):
        if progress_cb:
            progress_cb(0.1 + 0.7 * (i / total), f"Đang dựng cảnh {i + 1}/{total}: {scene.title}...")

        img_path = temp_dir / f"scene_{i:02d}.png"
        download_or_fetch_scene_image(scene, img_path)

        duration = 3.5
        audio_clip = None

        if enable_tts and scene.script:
            audio_path = temp_dir / f"audio_{i:02d}.mp3"
            try:
                voice_id = resolve_voice(voice_name)
                aud_p, measured_dur = generate_tts(
                    scene.script,
                    voice=voice_id,
                    output_path=audio_path,
                )
                if aud_p and Path(aud_p).is_file():
                    audio_clip = AudioFileClip(str(aud_p))
                    duration = max(3.0, measured_dur + 0.6)
            except Exception as exc:
                logger.warning("TTS failed for custom scene %s (%s)", scene.title, exc)

        clip = ImageClip(str(img_path)).with_duration(duration)
        if audio_clip:
            clip = clip.with_audio(audio_clip)
        clips.append(clip)

    if progress_cb:
        progress_cb(0.85, "Đang kết xuất video theo yêu cầu (MoviePy)...")

    final_video = concatenate_videoclips(clips, method="compose")
    final_video.write_videofile(
        str(output_path),
        fps=16,
        codec="libx264",
        audio_codec="aac" if enable_tts else None,
        preset="fast",
        logger=None,
    )

    for c in clips:
        try:
            c.close()
        except Exception:
            pass
    try:
        final_video.close()
    except Exception:
        pass

    if progress_cb:
        progress_cb(1.0, "Đã hoàn thành video theo yêu cầu!")

    return output_path
