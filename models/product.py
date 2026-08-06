"""Product input and AI analysis models."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class ProductInput(BaseModel):
    """Raw user input for one product."""

    name: str = Field(..., min_length=1, max_length=200, description="Tên sản phẩm")
    description: str = Field(default="", max_length=2000, description="Mô tả / USP thô")
    category: str = Field(default="Khác", description="Danh mục")
    price: Optional[str] = Field(default=None, description="Giá hiển thị (vd: 99k, 250.000đ)")
    target_audience: Optional[str] = Field(
        default=None,
        description="Đối tượng khách hàng (vd: nữ 18-25, dân văn phòng)",
    )
    image_paths: list[Path] = Field(default_factory=list, description="Đường dẫn ảnh sản phẩm")
    duration: int = Field(default=35, ge=15, le=90, description="Độ dài video mục tiêu (giây)")
    voice: str = Field(default="vi-VN-HoaiMyNeural", description="Voice ID edge-tts")
    render_mode: str = Field(default="cpu", description="cpu | gpu")

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Tên sản phẩm không được để trống")
        return v

    @field_validator("image_paths", mode="before")
    @classmethod
    def coerce_paths(cls, v):
        if v is None:
            return []
        if isinstance(v, (str, Path)):
            return [Path(v)]
        return [Path(p) for p in v]


class ProductAnalysis(BaseModel):
    """Result of AI product analysis (LLM)."""

    usp: list[str] = Field(default_factory=list, description="3–5 USP chính")
    target_audience: str = Field(default="", description="Khách hàng mục tiêu đã suy luận")
    concept: str = Field(default="Lifestyle", description="Concept video được chọn")
    mood: str = Field(default="Warm", description="Mood / color grade")
    keywords: list[str] = Field(default_factory=list, description="Keyword SEO / hashtag seed")
    selling_points: list[str] = Field(default_factory=list, description="Điểm bán nổi bật")
    avoid: list[str] = Field(default_factory=list, description="Điều cần tránh khi gen video")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
