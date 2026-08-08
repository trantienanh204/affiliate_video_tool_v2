"""
Application configuration via environment variables + optional YAML.

Priority: env > .env > config.yaml defaults.
Uses pydantic-settings for type-safe, validated config.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RenderMode(str, Enum):
    """Video render backend."""

    CPU = "cpu"  # Ken Burns multi-scene + MoviePy (no GPU)
    GPU = "gpu"  # ComfyUI Image-to-Video


class LLMProvider(str, Enum):
    OLLAMA = "ollama"
    FALLBACK = "fallback"  # template-based when Ollama unavailable


class Settings(BaseSettings):
    """Global application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="AVA_",  # Affiliate Video AI
        extra="ignore",
        case_sensitive=False,
    )

    # --- Paths ---
    project_root: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[1])
    outputs_dir: Path = Field(default=Path("outputs"))
    cache_dir: Path = Field(default=Path("cache"))
    assets_dir: Path = Field(default=Path("assets"))
    workflows_dir: Path = Field(default=Path("workflows"))

    # --- Render ---
    render_mode: RenderMode = RenderMode.CPU
    video_width: int = 1080
    video_height: int = 1920
    video_fps: int = 16  # CPU: 16fps nhanh hơn 24 rất nhiều, vẫn ổn TikTok
    video_bitrate: str = "2000k"
    default_duration: int = 30
    min_duration: int = 15
    max_duration: int = 60

    # --- LLM (Ollama) ---
    llm_provider: LLMProvider = LLMProvider.OLLAMA
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    ollama_timeout: int = 120  # seconds
    ollama_temperature: float = 0.7
    ollama_max_tokens: int = 2048

    # --- TTS ---
    tts_voice_default: str = "vi-VN-HoaiMyNeural"
    tts_rate: str = "+0%"
    tts_volume: str = "+0%"

    # --- ComfyUI (GPU mode) ---
    comfyui_url: str = "http://127.0.0.1:8188"
    comfyui_timeout: int = 600
    comfyui_enabled: bool = False

    # --- Subtitle ---
    # Default OFF on CPU: burn-in re-encodes toàn bộ video → +60–90s
    whisper_model: str = "base"
    whisper_device: Literal["cpu", "cuda"] = "cpu"
    burn_subtitles: bool = False

    # --- Music ---
    # Default OFF: không có file nhạc + tránh encode lần 2
    enable_bgm: bool = False
    bgm_volume: float = 0.18

    # --- Gradio ---
    gradio_server_name: str = "0.0.0.0"
    gradio_server_port: int = 7860
    gradio_share: bool = False
    gradio_queue: bool = True
    max_queue_size: int = 20

    # --- Batch ---
    max_batch_size: int = 100
    parallel_workers: int = 2  # CPU workers for batch

    # --- Logging ---
    log_level: str = "INFO"
    log_file: str | None = "logs/app.log"

    # --- History ---
    history_db: Path = Field(default=Path("cache/history.db"))

    @field_validator("outputs_dir", "cache_dir", "assets_dir", "workflows_dir", mode="before")
    @classmethod
    def _resolve_path(cls, v: str | Path, info) -> Path:
        p = Path(v)
        if not p.is_absolute():
            # relative to project root (computed later if needed)
            return p
        return p

    def ensure_dirs(self) -> None:
        """Create required directories if missing."""
        root = self.project_root
        for d in (
            root / self.outputs_dir,
            root / self.cache_dir,
            root / self.assets_dir / "music",
            root / self.assets_dir / "fonts",
            root / self.assets_dir / "templates",
            root / self.workflows_dir,
            root / "logs",
        ):
            d.mkdir(parents=True, exist_ok=True)

    @property
    def is_gpu_mode(self) -> bool:
        return self.render_mode == RenderMode.GPU and self.comfyui_enabled


# Singleton
settings = Settings()
settings.ensure_dirs()
