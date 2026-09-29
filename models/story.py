"""Fictional short-form story input and generated package."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class StoryInput(BaseModel):
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
    title: str
    hook: str
    full_script: str
    caption: str
    hashtags: list[str] = Field(default_factory=list)
    generation_mode: str = "template"
    spoken_units: int = 0
