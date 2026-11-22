"""
QA e2e-lvl test harness for video/engine.py changes (logic level).
Runs with python3.12 (project interpreter) in the project dir.
"""
import sys, os, tempfile, wave
from pathlib import Path

sys.path.insert(0, r"D:\Projects\tool_ai_video\affiliate-video-ai-V2")

import numpy as np
from moviepy import AudioFileClip, concatenate_audioclips, ImageClip, VideoFileClip

from models.product import ProductInput
from models.script import ScriptPackage
from models.storyboard import Storyboard, Scene
from models.job import JobResult
from core.config import settings
from video.engine import (_target_scene_count, _condense_script, _normalize_audio_duration, render_product, _render_provider_scenes)
from video.compositor import compose_video
from video.subtitle import generate_subtitles

ROOT = Path(r"D:\Projects\tool_ai_video\affiliate-video-ai-V2")
tmp = Path(tempfile.mkdtemp(prefix="qa_e2e_01"))
results = []

def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(("PASS" if cond else "FAIL"), "|", name, "|", detail)

# ---------- Test A: _target_scene_count ----------
print("=== Test A: _target_scene_count ===")
for n in [0, 3, 4, 5, 6]:
    s = Storyboard(scenes=[Scene(scene_id=i+1, role="shot", description=f"Cảnh {i+1}", image_index=0) for i in range(n)], total_duration=35.0)
    got = _target_scene_count(s)
    check(f"scenes={n}", got in (0,1,2,3,4,5,6), f"-> {got}")

# ---------- Test B: _condense_script ----------
print("\n=== Test B: _condense_script ===")
def make_script(words=250):
    body = "Đây là thân thể của script. " * max(1, words // 20)
    return ScriptPackage(hook="Mở đầu hook", body=body, cta="Kết thúc CTA", caption="", full_script="Mở đầu hook" + body + "Kết thúc CTA.")

s_short = make_script(50)
c = _condense_script(s_short, 300)
check("short unchanged", c == s_short.full_script)
s_long = make_script(2500)
c = _condense_script(s_long, 300)
check("long condensed", len(c) <= 300, f"len={len(c)}")
check("arc hook preserved", "Mở đầu hook" in c)
check("arc body partially preserved", "Đây là thân thể của script" in c)
check("long story never exceeds budget (no crash)", len(c) <= 300)
s2 = ScriptPackage(hook="Hook", body="B".join(["X"]*6000), cta="", caption="", full_script="Hook" + "B".join(["X"]*6000))
c = _condense_script(s2, 120)
check("no cta within budget", len(c) <= 120, f"len={len(c)}")

# ---------- Test C: _normalize_audio_duration ----------
print("\n=== Test C: _normalize_audio_duration ===")
def make_wav(path, dur_sec, rate=16000):
    t = np.linspace(0, dur_sec, int(rate*dur_sec), endpoint=False)
    snd = (0.3 * np.sin(2*np.pi*440*t)).astype(np.float32)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes((snd*32767).astype(np.int16).tobytes())

src = tmp / "in_12s.wav"
make_wav(src, 12.0)

def norm(target):
    out = tmp / f"out_{target}s.wav"
    _normalize_audio_duration(src, target, out)
    ac = AudioFileClip(str(out))
    dur = ac.duration
    ac.close()
    return dur

d30 = norm(30.0); d45 = norm(45.0)
check("normalize to 30s exact", abs(d30 - 30.0) < 0.05, f"got {d30:.3f}")
check("normalize to 45s exact", abs(d45 - 45.0) < 0.05, f"got {d45:.3f}")

# ---------- Test D: compose_video Ken Burns preview ----------
print("\n=== Test D: compose_video (Ken Burns preview) ===")
# synthetic still frames (solid color cards) + narration
img_tmp = tmp / "img"
img_tmp.mkdir()
def solid_frame(path, w=1080, h=1920, color=(30,41,59), text=""):
    img = np.full((h, w, 3), color, dtype=np.uint8)
    # draw a simple centered bar using PIL
    from PIL import Image, ImageDraw, ImageFont
    img_p = Image.fromarray(img)
    d = ImageDraw.Draw(img_p)
    try:
        fnt = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 24)
    except Exception:
        fnt = ImageFont.load_default()
    if text:
        d.text((w//2, h//2), text, fill=(255,255,255), font=fnt, anchor="mm")
    img_p.save(path)
    return path

frames = []
for i in range(4):
    p = img_tmp / f"f{i}.png"
    solid_frame(p, color=(30,41,59) if i % 2 == 0 else (13,27,42), text=f"Cảnh {i+1}")
    duration = 8.0 if i % 2 == 0 else 12.0
    clip = ImageClip(str(p)).with_duration(duration)
    frames.append(clip)

script = ScriptPackage(hook="Mở đầu", body="Đây là body của video. " * 50, cta="Kết thúc", full_script="Mở đầu" + "Đây là body của video. " * 50 + "Kết thúc")
audio_text = script.full_script  # normal-ish narration
# generate a real-ish audio with edge_tts? offline -> use synthetic wav
def wav_from_text(text, path, dur=None):
    import wave
    if dur is None:
        dur = max(30.0, len(text.split()) / 12.0 * 1.0)
    t = np.linspace(0, dur, int(16000*dur), endpoint=False)
    snd = (0.4*np.sin(2*np.pi*400*t)).astype(np.float32)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes((snd*32767).astype(np.int16).tobytes())
    return path

audio_path = wav_from_text(script.full_script, tmp/"audio_synth.wav")
out_video = tmp / "kenburns_test.mp4"
comp = compose_video(
    storyboard=storyboard_v, image_paths=[str(img_tmp / f"f{i}.png") for i in range(4)],
    audio_path=audio_path, output_path=out_video,
    job_id="test", target_duration=30.0, product_name="A", category="B",
)
check("compose_video doesn't crash", out_video.exists() and out_video.stat().st_size > 5000, f"size={out_video.stat().st_size if out_video.exists() else 0}")

# ---------- Test E: full render_product with mocked AI provider ----------
print("\n=== Test E: render_product with mocked AI (logic e2e) ===")
# Build a valid product with a LONG story (2000 words) -> narration condensed
long_body = "Câu chuyện sự kiện mỗi ngày băng qua nhiều địa danh. " * 800
script = ScriptPackage(
    hook="Hành động chỉ xảy ra một lần, ở khu vực giang hồ.",
    body=long_body,
    cta="Gọi anh ấy. Nét mặt bị che chẩn là vẻ đẹp truyền cảm hứng.",
    full_script="Hành động chỉ xảy ra một lần, ở khu vực giang hồ. " + long_body + " Gọi anh ấy. Nét mặt bị che chẩn là vẻ đẹp truyền cảm hứng.",
)
prod = ProductInput(
    name="Áo thun form rộng",
    category="Áo",
    description="Cotton 100%",
    duration=45,
    voice="vi-VN-HoaiMyNeural",
    image_paths=[],  # no real images -> Ken Burns path (no AI backend in sandbox)
)

# Need a real storyboard + image_paths for render_product. Generate a synthetic storyboard manually
storyboard = Storyboard(
    concept="Lifestyle",
    total_duration=45.0,
    scenes=[
        Scene(scene_id=1, role="hook", description="Cảnh mở", duration=8.0, image_index=0),
        Scene(scene_id=2, role="showcase", description="Cảnh chi tiết", duration=10.0, image_index=1),
        Scene(scene_id=3, role="detail", description="Cảnh chi tiết", duration=10.0, image_index=0),
        Scene(scene_id=4, role="cta", description="Cảnh CTA", duration=7.0, image_index=1),
        Scene(scene_id=5, role="closing", description="Cảnh kết", duration=10.0, image_index=0),
    ],
)
# ProductInput.image_paths is already empty => engine will treat as no images -> Ken Burns? 
# Actually render_product requires image_paths for AI path; empty -> CPU Ken Burns fallback.
# We mock _generate_video_with_fallbacks to return N clips by monkeypatching engine function
import video.engine as eng
_orig_gen = eng._generate_video_with_fallbacks
def fake_gen(storyboard, image_paths, job_id, progress_callback, product, *a, **k):
    return None, "", []  # no AI -> falls back to Ken Burns (since require_ai_video_active False in sandbox)
eng._generate_video_with_fallbacks = fake_gen

# Also monkeypatch analyze_and_script to return our script
from ai.llm.analyzer import analyze_and_script as _orig_analyz
def fake_analyz(product):
    class A:
        concept = "Lifestyle"; mood = "Warm"
    return A(), script
eng.analyze_and_script = fake_analyz

# Mock storyboard generation
from ai.storyboard.generator import generate_storyboard as _orig_sb
def fake_sb(product, analysis, script):
    return storyboard
eng.generate_storyboard = fake_sb

out = tmp / "final_e2e.mp4"
try:
    res = render_product(prod, job_id="e2e_test", progress_callback=lambda v,s: None)
    check("render_product completes", True)
    check("ai_clips == 0 (no AI backend)", res.meta.get("ai_clips") == 0, f"got {res.meta.get('ai_clips')}")
    check("narration condensed", res.meta.get("narration_chars", 9999) <= 45*12, f"narration_chars={res.meta.get('narration_chars')}")
    check("story_words preserved", res.meta.get("story_words", 9999) > 1000, f"story_words={res.meta.get('story_words')}")
    # Subtitle using condensed narration should be generated
    import os
    aud_path = tmp / "audio_e2e_test.mp3"
    check("audio file exists", aud_path.exists(), f"size={aud_path.stat().st_size if aud_path.exists() else 'missing'}")
    if aud_path.exists():
        ac = AudioFileClip(str(aud_path))
        check("audio duration in [30,45]", 30.0 <= ac.duration <= 45.5, f"dur={ac.duration:.2f}")
        ac.close()
    # subtitle segments
    narration = _condense_script(script, 45 * 12)
    segs = generate_subtitles(aud_path, script_text=narration, duration=45.0)
    check("subtitle from condensed narration", isinstance(segs, list) and len(segs) > 0, f"{len(segs) if segs else 0} segments")
finally:
    eng._generate_video_with_fallbacks = _orig_gen
    eng.analyze_and_script = _orig_analyz
    eng.generate_storyboard = _orig_sb

# ---------- Summary ----------
print("\n================ SUMMARY ================")
passed = sum(1 for _, p, _ in results if p)
print(f"{passed}/{len(results)} tests passed")
for name, p, detail in results:
    if not p:
        print("FAIL:", name, "|", detail)
