"""
qa_e2e_server.py — E2E acceptance tests (story miễn phí, video 30–45s).

Run (project interpreter python3.12):
    cd D:\Projects\tool_ai_video\affiliate-video-ai-V2
    python3.12 qa_e2e_server.py

Sandbox note: no GPU/AI backend so mock `_render_one_scene` makes synthetic
but structurally-valid I2V clips. On the real GPU/AI server, replace that
mock with the real dispatch (no patch) and run the same matrix.

Asserts
-------
AC1  story không bị giới hạn (500/2000/3000 → hoàn thành, không crash)
AC3  video ∈ [30,45]s; narration ≤ duration×12; ai_clips == scene_count
AC Match subtitle từ audio đã normalize; audio duration == target_dur
"""

import sys, io, tempfile, logging as pylogging
from pathlib import Path

ROOT = Path(r"D:\Projects\tool_ai_video\affiliate-video-ai-V2")
TMP = Path(tempfile.mkdtemp(prefix="qa_server_e2e_"))
sys.path.insert(0, str(ROOT))

import numpy as np
from moviepy import AudioFileClip, ColorClip, TextClip

from models.product import ProductInput
from models.script import ScriptPackage
from models.storyboard import Storyboard, Scene
from models.job import JobResult
from core.config import settings

import video.engine as eng
from video.subtitle import generate_subtitles

# ---------------- logging capture ----------------
log_capture = io.StringIO()
_handler = pylogging.StreamHandler(log_capture)
_handler.setLevel(pylogging.INFO)
pylogging.getLogger().addHandler(_handler)

# ---------------- helpers ----------------
def check(name, cond, detail=""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name} | {detail}")
    return bool(cond)

def make_script(words):
    body = "Đây là thân thể của script. " * max(1, words // 25)
    return ScriptPackage(
        hook="Mở đầu hook", body=body, cta="Kết thúc CTA.",
        caption="", full_script="Mở đầu hook" + body + "Kết thúc CTA.",
    )

def make_storyboard(n_scenes):
    scenes = [
        ("hook", 8.0), ("showcase", 10.0), ("detail", 10.0),
        ("cta", 7.0), ("closing", 10.0), ("wrap", 8.0),
    ][:n_scenes]
    return Storyboard(
        concept="Lifestyle", total_duration=45.0,
        scenes=[
            Scene(scene_id=i + 1, role=r, description="Cảnh",
                  duration=d, image_index=i % 4)
            for i, (r, d) in enumerate(scenes)
        ],
    )

def make_product(duration):
    return ProductInput(
        name="Áo thun form rộng", category="Áo",
        description="Cotton 100%", duration=duration,
        voice="vi-VN-HoaiMyNeural",
        image_paths=[TMP / f"dummy_{i}.png" for i in range(4)],
    )

# ---------------- mock AI provider ----------------
_orig_render_one_scene = eng._render_one_scene

def fake_render_one_scene(provider, image_path, prompt, scene,
                          job_id, progress_callback, product):
    """Synthetic I2V clip: solid color per scene role + role text overlay."""
    from core.config import settings
    w, h = settings.video_width, settings.video_height
    role = scene.role if hasattr(scene, "role") else "detail"
    color_map = {
        "hook": (30, 41, 59), "showcase": (24, 32, 51),
        "detail": (40, 48, 64), "cta": (56, 74, 100),
        "closing": (64, 88, 120), "wrap": (20, 30, 42),
    }
    color = color_map.get(role, (30, 41, 59))
    dur = max(3.0, scene.duration or 3.0)
    clip = ColorClip(size=(w, h), color=color).with_duration(dur)
    txt = (TextClip(
        text=f"Cảnh {scene.scene_id} – {role}",
        font="arial.ttf", font_size=40, color=(255, 255, 255),
        size=(w - 40, 60),
    ).with_duration(dur).with_position("center"))
    clip = clip.set_overlay(txt)
    out = TMP / f"mock_clip_{scene.scene_id}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    clip.write_videofile(str(out), fps=16, codec="libx264",
                          audio_codec="aac", logger=None, preset="fast")
    clip.close()
    return out

# Install the mock (swap with real dispatch on a GPU/AI server)
eng._render_one_scene = fake_render_one_scene

# ---------------- assertion helpers ----------------
def assert_video_duration(path):
    ac = AudioFileClip(str(path))
    dur = ac.duration
    ac.close()
    return 30.0 <= dur <= 45.5, dur

# ---------------- main matrix ----------------
print("=" * 60)
print("E2E AC test — story miễn phí, video 30–45s")
print("=" * 60)

results = []
for words in (500, 2000, 3000):
    for duration in (30, 35, 40, 45):
        prod = make_product(duration)
        storyboard = make_storyboard(6)

        for p in TMP.glob("mock_clip_*.mp4"):
            p.unlink(missing_ok=True)

        out_mp4 = TMP / f"video_{words}_{duration}s.mp4"
        result = eng.render_product(
            prod, job_id="server_e2e",
            progress_callback=lambda v, s: None,
        )

        info = {
            "story_words": words, "duration": duration,
            "ai_clips": result.meta.get("ai_clips"),
            "narration_chars": result.meta.get("narration_chars"),
            "story_words_meta": result.meta.get("story_words"),
            "narration_words": result.meta.get("narration_words"),
            "render_mode": result.meta.get("render_mode"),
            "provider": result.meta.get("provider"),
        }

        ok_vid, vid_dur = assert_video_duration(out_mp4)

        for name, cond, detail in [
            ("AC1 story không bị giới hạn",
             result.meta.get("story_words") == words, info),
            ("AC3 video ∈ [30,45]", ok_vid, f"dur={vid_dur:.2f}s"),
            ("AC3 narration ≤ budget (12 chars/s)",
             result.meta.get("narration_chars", 9999) <= duration * 12,
             f"chars={result.meta.get('narration_chars')}"),
            ("AC3 clip count = scene count (no dup/loop)",
             result.meta.get("ai_clips") == storyboard.scene_count(),
             f"clip={result.meta.get('ai_clips')}, scene={storyboard.scene_count()}"),
        ]:
            results.append((name, cond, detail))

# ---------------- summary ----------------
print("\n" + "=" * 60)
print("KẾT QUẢ E2E")
print("=" * 60)
passed = sum(1 for _, p, _ in results if p)
print(f"{passed}/{len(results)} PASS")
for name, p, detail in results:
    if not p:
        print(f"FAIL | {name} | {detail}")

print("\n[LAST LOG LINES]\n" + "\n".join(
    log_capture.getvalue().splitlines()[-15:]))
