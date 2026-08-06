"""
ComfyUI HTTP + WebSocket client.

Assumes ComfyUI is running with API enabled (default :8188).
Does not require GPU at import time – only when submitting jobs.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Optional

import httpx

from core.config import settings
from core.exceptions import ComfyUIError
from core.logging import get_logger

logger = get_logger(__name__)


class ComfyUIClient:
    """Minimal ComfyUI API client for queue / history / upload / download."""

    def __init__(self, base_url: str | None = None, timeout: int | None = None):
        self.base_url = (base_url or settings.comfyui_url).rstrip("/")
        self.timeout = timeout or settings.comfyui_timeout
        self.client_id = uuid.uuid4().hex
        self._http = httpx.Client(base_url=self.base_url, timeout=30.0)

    def is_available(self) -> bool:
        try:
            r = self._http.get("/system_stats", timeout=5.0)
            return r.status_code == 200
        except Exception as e:
            logger.debug("ComfyUI health check failed: %s", e)
            return False

    def upload_image(self, image_path: Path, overwrite: bool = True) -> str:
        """Upload image to ComfyUI input folder. Returns server-side filename."""
        image_path = Path(image_path)
        if not image_path.is_file():
            raise ComfyUIError(f"Image not found: {image_path}")

        with open(image_path, "rb") as f:
            files = {
                "image": (image_path.name, f, "image/png"),
            }
            data = {"overwrite": "true" if overwrite else "false"}
            r = self._http.post("/upload/image", files=files, data=data, timeout=60.0)
        if r.status_code != 200:
            raise ComfyUIError(f"Upload failed: {r.status_code} {r.text[:200]}")
        info = r.json()
        name = info.get("name") or image_path.name
        logger.info("ComfyUI uploaded: %s", name)
        return name

    def queue_prompt(self, workflow: dict[str, Any]) -> str:
        """Submit workflow, return prompt_id."""
        payload = {"prompt": workflow, "client_id": self.client_id}
        r = self._http.post("/prompt", json=payload, timeout=30.0)
        if r.status_code != 200:
            raise ComfyUIError(f"Queue failed: {r.status_code} {r.text[:300]}")
        data = r.json()
        prompt_id = data.get("prompt_id")
        if not prompt_id:
            raise ComfyUIError(f"No prompt_id in response: {data}")
        logger.info("ComfyUI queued prompt_id=%s", prompt_id)
        return prompt_id

    def wait_for_completion(
        self,
        prompt_id: str,
        *,
        poll_interval: float = 2.0,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Poll /history until prompt finishes. Returns history entry outputs."""
        timeout = timeout or self.timeout
        deadline = time.time() + timeout

        while time.time() < deadline:
            try:
                r = self._http.get(f"/history/{prompt_id}", timeout=15.0)
                if r.status_code == 200:
                    hist = r.json()
                    if prompt_id in hist:
                        entry = hist[prompt_id]
                        status = entry.get("status", {})
                        if status.get("completed", False) or "outputs" in entry:
                            logger.info("ComfyUI done prompt_id=%s", prompt_id)
                            return entry
                        if status.get("status_str") == "error":
                            raise ComfyUIError(
                                f"ComfyUI job error: {status}",
                                details=json.dumps(status)[:500],
                            )
            except ComfyUIError:
                raise
            except Exception as e:
                logger.debug("Poll error: %s", e)
            time.sleep(poll_interval)

        raise ComfyUIError(f"Timeout waiting for prompt_id={prompt_id}")

    def download_output(
        self,
        filename: str,
        subfolder: str = "",
        folder_type: str = "output",
        dest: Optional[Path] = None,
    ) -> Path:
        """Download a file from ComfyUI output/input view endpoint."""
        params = {"filename": filename, "subfolder": subfolder, "type": folder_type}
        r = self._http.get("/view", params=params, timeout=120.0)
        if r.status_code != 200:
            raise ComfyUIError(f"Download failed: {r.status_code}")
        if dest is None:
            dest = Path(settings.project_root) / settings.cache_dir / "comfyui" / filename
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(r.content)
        logger.info("Downloaded %s → %s (%.1f KB)", filename, dest.name, len(r.content) / 1024)
        return dest

    def extract_video_outputs(self, history_entry: dict[str, Any]) -> list[dict[str, str]]:
        """
        Parse history outputs for video / gifs / images.

        Returns list of {filename, subfolder, type}.
        """
        results = []
        outputs = history_entry.get("outputs") or {}
        for node_id, node_out in outputs.items():
            for key in ("gifs", "videos", "images"):
                items = node_out.get(key) or []
                for item in items:
                    results.append({
                        "filename": item.get("filename", ""),
                        "subfolder": item.get("subfolder", ""),
                        "type": item.get("type", "output"),
                        "node_id": str(node_id),
                    })
        return results

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "ComfyUIClient":
        return self

    def __exit__(self, *args) -> None:
        self.close()


_client: Optional[ComfyUIClient] = None


def get_comfyui_client() -> ComfyUIClient:
    global _client
    if _client is None:
        _client = ComfyUIClient()
    return _client
