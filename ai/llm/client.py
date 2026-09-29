"""
Ollama LLM client with retry + graceful fallback detection.

Uses the official `ollama` Python package when available,
otherwise falls back to raw httpx calls against the Ollama HTTP API.
"""

from __future__ import annotations

import json
import base64
from pathlib import Path
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

    def describe_product_images(self, image_paths: list[Path], *, product_name: str = "", category: str = "") -> str:
        """Use an Ollama vision model to describe visible product attributes."""
        encoded_images = []
        for path in image_paths[:4]:
            try:
                data = base64.b64encode(Path(path).read_bytes()).decode("ascii")
                encoded_images.append(data)
            except OSError as e:
                logger.warning("Cannot read product image %s: %s", path, e)
        if not encoded_images:
            return ""

        prompt = (
            "Mô tả ngắn gọn những gì NHÌN THẤY trực tiếp trong ảnh sản phẩm để viết video giới thiệu. "
            "Ưu tiên loại sản phẩm, màu sắc, họa tiết, phom dáng, chi tiết thiết kế và cách phối/mặc nếu thấy. "
            "Không suy đoán chất liệu, giá, độ bền, công dụng, thương hiệu hay đánh giá nếu ảnh không chứng minh. "
            "Nếu không nhận diện rõ, hãy nói chưa xác định được. Trả lời tiếng Việt trong 2-4 câu. "
            f"Tên người dùng nhập: {product_name}. Danh mục: {category}."
        )
        try:
            r = self._client.post("/api/chat", json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt, "images": encoded_images}],
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 220},
            })
            r.raise_for_status()
            description = (r.json().get("message", {}).get("content") or "").strip()
            return description[:1000]
        except Exception as e:
            logger.warning("Ollama vision analysis unavailable: %s", e)
            return ""

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
