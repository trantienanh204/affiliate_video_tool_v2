"""Lightweight Hugging Face credential check before starting expensive work."""

from __future__ import annotations

import os

import httpx


def validate_hf_token() -> bool | None:
    """Return True/False for a supplied token; None when validation is inconclusive.

    This validates authentication only. Hugging Face does not expose a reliable
    public endpoint for checking remaining ZeroGPU quota across arbitrary Spaces.
    """
    token = os.getenv("HF_TOKEN", "").strip()
    if not token:
        return None  # Anonymous requests are permitted, with a smaller shared quota.

    try:
        response = httpx.get(
            "https://huggingface.co/api/whoami-v2",
            headers={"Authorization": f"Bearer {token}"},
            timeout=8.0,
            follow_redirects=True,
        )
    except httpx.HTTPError:
        return None

    if response.status_code in (401, 403):
        return False
    if response.is_success:
        return True
    return None
