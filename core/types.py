"""
Shared type aliases and constants used across modules.
Prefer Pydantic models in `models/` for domain objects.
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict

# ---------------------------------------------------------------------------
# Literal unions
# ---------------------------------------------------------------------------

Category = Literal[
    "Áo",
    "Quần",
    "Giày",
    "Đồ ăn",
    "Phụ kiện",
    "Mỹ phẩm",
    "Đồng hồ",
    "Túi",
    "Nhà cửa",
    "Khác",
]

Concept = Literal[
    "Lifestyle",
    "Review",
    "Luxury",
    "TikTok Viral",
    "POV",
    "Office",
    "Outdoor",
    "Beauty",
    "Minimal",
    "Commercial",
    "Street",
    "Cafe",
    "Home",
]

CameraMove = Literal[
    "Close Up",
    "Wide",
    "Tracking",
    "Orbit",
    "POV",
    "Handheld",
    "Drone",
    "Zoom In",
    "Zoom Out",
    "Slow Motion",
    "Pan",
    "Tilt",
    "Static",
]

Lighting = Literal[
    "Natural",
    "Golden Hour",
    "Softbox",
    "Studio",
    "Morning",
    "Sunset",
    "Luxury",
    "Commercial",
    "Neon",
    "Moody",
]

ColorGrade = Literal[
    "Warm",
    "Cold",
    "Luxury",
    "Minimal",
    "Commercial",
    "TikTok",
    "Cinematic",
    "Vibrant",
]

JobStatus = Literal[
    "pending",
    "analyzing",
    "scripting",
    "storyboarding",
    "rendering",
    "tts",
    "subtitling",
    "compositing",
    "done",
    "failed",
    "cancelled",
]

# ---------------------------------------------------------------------------
# Lightweight TypedDicts (for internal transfer)
# ---------------------------------------------------------------------------


class ProgressUpdate(TypedDict, total=False):
    progress: float  # 0.0 – 1.0
    stage: str
    message: str


class ScenePrompt(TypedDict, total=False):
    scene_id: int
    description: str
    camera: str
    lighting: str
    color: str
    duration: float
    i2v_prompt: str
    negative_prompt: str


# Re-export common Any for convenience
JSONDict = dict[str, Any]
