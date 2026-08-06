"""Job tracking models for queue + history."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from models.product import ProductAnalysis, ProductInput
from models.script import ScriptPackage
from models.storyboard import Storyboard


class Job(BaseModel):
    """One generation job."""

    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    status: str = Field(default="pending")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    product: ProductInput
    analysis: Optional[ProductAnalysis] = None
    script: Optional[ScriptPackage] = None
    storyboard: Optional[Storyboard] = None
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    stage: str = Field(default="pending")
    error: Optional[str] = None
    meta: dict[str, Any] = Field(default_factory=dict)

    def touch(self, status: str | None = None, progress: float | None = None, stage: str | None = None) -> None:
        self.updated_at = datetime.utcnow()
        if status is not None:
            self.status = status
        if progress is not None:
            self.progress = progress
        if stage is not None:
            self.stage = stage


class JobResult(BaseModel):
    """Final output of a successful job."""

    job_id: str
    video_path: Path
    caption: str
    script_text: str
    duration: float
    thumbnail_path: Optional[Path] = None
    meta: dict[str, Any] = Field(default_factory=dict)
