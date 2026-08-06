"""
Ollama LLM client with retry + graceful fallback detection.

Uses the official `ollama` Python package when available,
otherwise falls back to raw httpx calls against the Ollama HTTP API.
"""

from __future__ import annotations

import json
from typing import Any, Optional

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from core.config import settings
from core.exceptions import LLMError, LLMUnavailableError
from core.logging import get_logger

logger = get_logger(__name__)


class OllamaClient:
    """Thin async-compatible wrapper around Ollama generate / chat."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
    ):
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.ollama_model
        self.timeout = timeout or settings.ollama_timeout
        self._client = httpx.Client(base_url=self.base_url, timeout=self.timeout)

    def is_available(self) -> bool:
        """Quick health check – does not raise."""
        try:
            r = self._client.get("/api/tags", timeout=5.0)
            return r.status_code == 200
        except Exception as e:
            logger.debug("Ollama health check failed: %s", e)
            return False

    def list_models(self) -> list[str]:
        try:
            r = self._client.get("/api/tags")
            r.raise_for_status()
            data = r.json()
            return [m["name"] for m in data.get("models", [])]
        except Exception as e:
            raise LLMUnavailableError("Cannot list Ollama models", details=str(e)) from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
        reraise=True,
    )
    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        format_json: bool = False,
    ) -> str:
        """
        Chat completion. Returns assistant message content as string.

        Raises LLMUnavailableError if server is down.
        Raises LLMError on other failures.
        """
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature if temperature is not None else settings.ollama_temperature,
                "num_predict": max_tokens or settings.ollama_max_tokens,
            },
        }
        if format_json:
            payload["format"] = "json"

        try:
            r = self._client.post("/api/chat", json=payload)
            if r.status_code == 404:
                raise LLMUnavailableError(
                    f"Model '{self.model}' not found. Pull it with: ollama pull {self.model}"
                )
            r.raise_for_status()
            data = r.json()
            content = data.get("message", {}).get("content", "")
            if not content:
                raise LLMError("Empty response from Ollama")
            return content.strip()
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            raise LLMUnavailableError(
                "Ollama server unreachable",
                details=str(e),
            ) from e
        except LLMUnavailableError:
            raise
        except Exception as e:
            raise LLMError(f"Ollama chat failed: {e}", details=str(e)) from e

    def generate_json(
        self,
        system: str,
        user: str,
        *,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        """Convenience: force JSON response and parse it."""
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        raw = self.chat(messages, temperature=temperature, format_json=True)
        # Strip markdown fences if model still wraps them
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.warning("JSON parse failed, raw=%s", raw[:300])
            raise LLMError("Model returned invalid JSON", details=str(e)) from e

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "OllamaClient":
        return self

    def __exit__(self, *args) -> None:
        self.close()


# Module-level singleton (lazy)
_client: Optional[OllamaClient] = None


def get_ollama_client() -> OllamaClient:
    global _client
    if _client is None:
        _client = OllamaClient()
    return _client
