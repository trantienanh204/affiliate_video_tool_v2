"""Domain-specific exceptions for clean error handling."""

from __future__ import annotations


class AVAError(Exception):
    """Base exception for Affiliate Video AI."""

    def __init__(self, message: str, *, details: str | None = None):
        super().__init__(message)
        self.message = message
        self.details = details


class ConfigError(AVAError):
    """Invalid or missing configuration."""


class LLMError(AVAError):
    """Ollama / LLM related failure."""


class LLMUnavailableError(LLMError):
    """Ollama server not reachable → should fall back to templates."""


class TTSError(AVAError):
    """Text-to-speech generation failed."""


class VideoRenderError(AVAError):
    """MoviePy / ComfyUI render failure."""


class ComfyUIError(AVAError):
    """ComfyUI API or workflow error."""


class ProductValidationError(AVAError):
    """Invalid product input (name, images, etc.)."""


class BatchError(AVAError):
    """Batch / Excel processing error."""


class SubtitleError(AVAError):
    """Whisper / subtitle burn-in failure."""
