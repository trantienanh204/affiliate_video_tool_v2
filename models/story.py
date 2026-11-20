"""Fictional short-form story input and generated package."""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field, field_validator


class StoryLength(str, Enum):
    SHORT = "short"      # ~300 - 500 từ (TikTok/Reels đọc nhanh)
    MEDIUM = "medium"    # ~800 - 1200 từ (Truyện vừa, cao trào đầy đủ)
    LONG = "long"        # ~1500 - 2500 từ (Truyện dài kịch tính)


class StoryInput(BaseModel):
    """Legacy StoryInput kept for compatibility."""
    trope: str = Field(min_length=1, max_length=120)
    premise: str = Field(default="", max_length=1200)
    protagonist: str = Field(default="An Nhiên", max_length=80)
    duration_seconds: int = Field(default=960, ge=900, le=2400)
    ending: str = Field(default="Cliffhanger tập sau", max_length=80)
    tone: str = Field(default="Kịch tính, cảm xúc", max_length=80)

    @field_validator("protagonist")
    @classmethod
    def normalize_protagonist(cls, value: str) -> str:
        return value.strip() or "An Nhiên"


class StoryPackage(BaseModel):
    """Legacy StoryPackage kept for compatibility."""
    title: str
    hook: str
    full_script: str
    caption: str
    hashtags: list[str] = Field(default_factory=list)
    generation_mode: str = "template"
    spoken_units: int = 0


class FastStoryInput(BaseModel):
    """Input for ultra-fast cohesive story writing (text-only, no TTS)."""
    trope: str = Field(default="Chủ đề tự nhập", max_length=150)
    premise: str = Field(default="", max_length=2000)
    protagonist: str = Field(default="An Nhiên", max_length=80)
    length: StoryLength = Field(default=StoryLength.MEDIUM)
    tone: str = Field(default="Kịch tính, cảm xúc", max_length=80)
    ending: str = Field(default="Twist bất ngờ", max_length=80)

    @field_validator("protagonist")
    @classmethod
    def normalize_protagonist(cls, value: str) -> str:
        return value.strip() or "An Nhiên"


class FastStoryResult(BaseModel):
    """Output for ultra-fast cohesive story writing."""
    title: str
    hook: str
    content: str
    caption: str
    hashtags: list[str] = Field(default_factory=list)
    word_count: int = 0
    estimated_read_time_minutes: float = 0.0
    mode: str = "ollama"  # "ollama" | "template"
