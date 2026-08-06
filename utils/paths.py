"""Path helpers relative to project root."""

from __future__ import annotations

from pathlib import Path

from core.config import settings


def project_root() -> Path:
    return settings.project_root


def outputs_dir() -> Path:
    d = settings.project_root / settings.outputs_dir
    d.mkdir(parents=True, exist_ok=True)
    return d


def cache_dir() -> Path:
    d = settings.project_root / settings.cache_dir
    d.mkdir(parents=True, exist_ok=True)
    return d


def assets_dir() -> Path:
    return settings.project_root / settings.assets_dir


def job_output_dir(job_id: str) -> Path:
    d = outputs_dir() / job_id
    d.mkdir(parents=True, exist_ok=True)
    return d
