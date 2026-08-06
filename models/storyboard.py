"""Storyboard and scene models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Scene(BaseModel):
    """One scene in the video storyboard."""

    scene_id: int = Field(..., ge=1)
    role: str = Field(..., description="hook | showcase | detail | lifestyle | cta | ...")
    description: str = Field(..., description="Mô tả cảnh bằng tiếng Việt (cho người)")
    location: str = Field(default="", description="Bối cảnh: Cafe, Office, Street, ...")
    camera: str = Field(default="Close Up", description="Camera movement / shot type")
    lighting: str = Field(default="Natural")
    color_grade: str = Field(default="Warm")
    duration: float = Field(default=5.0, ge=1.0, le=20.0, description="Giây")
    image_index: int = Field(default=0, ge=0, description="Index ảnh sản phẩm dùng cho scene")
    i2v_prompt: str = Field(default="", description="Prompt Image-to-Video (English)")
    negative_prompt: str = Field(
        default="blurry, deformed, text, watermark, logo change, color shift",
        description="Negative prompt cho I2V",
    )
    text_overlay: str | None = Field(default=None, description="Text hiện trên scene (nếu có)")


class Storyboard(BaseModel):
    """Complete storyboard for one video."""

    concept: str = Field(default="Lifestyle")
    total_duration: float = Field(default=35.0)
    scenes: list[Scene] = Field(default_factory=list)
    transition: str = Field(default="crossfade", description="crossfade | cut | slide")
    notes: str = Field(default="")

    def scene_count(self) -> int:
        return len(self.scenes)

    def validate_durations(self) -> float:
        """Return sum of scene durations."""
        return sum(s.duration for s in self.scenes)
