"""
Batch import from Excel / CSV and sequential render.

Excel columns (header row required):
  name* | category | description | price | target_audience | image_path | duration | voice

* = required
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Callable, Optional

import pandas as pd

from core.config import settings
from core.exceptions import BatchError, ProductValidationError
from core.logging import get_logger
from models.job import JobResult
from models.product import ProductInput
from services.history import save_failure, save_result
from tts.edge import resolve_voice
from video.engine import render_product

logger = get_logger(__name__)

REQUIRED_COLUMNS = {"name"}
OPTIONAL_COLUMNS = {
    "category",
    "description",
    "price",
    "target_audience",
    "image_path",
    "duration",
    "voice",
}

ProgressCb = Optional[Callable[[float, str], None]]


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    # aliases
    rename = {
        "ten": "name",
        "ten_san_pham": "name",
        "product_name": "name",
        "danh_muc": "category",
        "mo_ta": "description",
        "gia": "price",
        "doi_tuong": "target_audience",
        "anh": "image_path",
        "image": "image_path",
        "images": "image_path",
        "do_dai": "duration",
        "giong": "voice",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    return df


def load_batch_file(path: Path | str) -> list[ProductInput]:
    """
    Load products from .xlsx / .xls / .csv.

    Returns list of ProductInput (image_path may be relative or absolute).
    """
    path = Path(path)
    if not path.is_file():
        raise BatchError(f"File không tồn tại: {path}")

    suffix = path.suffix.lower()
    try:
        if suffix in (".xlsx", ".xls"):
            df = pd.read_excel(path)
        elif suffix == ".csv":
            df = pd.read_csv(path)
        else:
            raise BatchError(f"Định dạng không hỗ trợ: {suffix} (dùng .xlsx hoặc .csv)")
    except BatchError:
        raise
    except Exception as e:
        raise BatchError(f"Không đọc được file: {e}") from e

    if df.empty:
        raise BatchError("File rỗng")

    df = _normalize_columns(df)

    if "name" not in df.columns:
        raise BatchError(
            "Thiếu cột bắt buộc 'name' (hoặc 'ten' / 'product_name'). "
            f"Các cột hiện có: {list(df.columns)}"
        )

    products: list[ProductInput] = []
    base_dir = path.parent

    for idx, row in df.iterrows():
        name = str(row.get("name") or "").strip()
        if not name or name.lower() == "nan":
            logger.warning("Skip row %s: empty name", idx)
            continue

        image_paths: list[Path] = []
        raw_img = row.get("image_path")
        if raw_img is not None and str(raw_img).strip() and str(raw_img).lower() != "nan":
            for part in str(raw_img).split(";"):
                part = part.strip()
                if not part:
                    continue
                p = Path(part)
                if not p.is_absolute():
                    p = base_dir / p
                if p.is_file():
                    image_paths.append(p)
                else:
                    logger.warning("Image not found: %s", p)

        duration = row.get("duration")
        try:
            duration = int(float(duration)) if duration == duration else settings.default_duration
        except (TypeError, ValueError):
            duration = settings.default_duration

        voice_raw = str(row.get("voice") or settings.tts_voice_default)
        if voice_raw.lower() == "nan":
            voice_raw = settings.tts_voice_default

        try:
            products.append(
                ProductInput(
                    name=name,
                    category=str(row.get("category") or "Khác").strip() or "Khác",
                    description=str(row.get("description") or "").replace("nan", "").strip(),
                    price=(str(row.get("price") or "").replace("nan", "").strip() or None),
                    target_audience=(
                        str(row.get("target_audience") or "").replace("nan", "").strip() or None
                    ),
                    image_paths=image_paths,
                    duration=duration,
                    voice=resolve_voice(voice_raw),
                )
            )
        except Exception as e:
            logger.warning("Skip row %s (%s): %s", idx, name, e)

    if not products:
        raise BatchError("Không có sản phẩm hợp lệ nào trong file")

    if len(products) > settings.max_batch_size:
        raise BatchError(
            f"Batch quá lớn ({len(products)} > max {settings.max_batch_size}). "
            "Tách file hoặc tăng AVA_MAX_BATCH_SIZE."
        )

    logger.info("Loaded %d products from %s", len(products), path.name)
    return products


def run_batch(
    products: list[ProductInput],
    *,
    progress_callback: ProgressCb = None,
) -> list[JobResult]:
    """
    Render products sequentially (stable on CPU).

    Saves each result to history. Continues on individual failures.
    """
    total = len(products)
    results: list[JobResult] = []

    for i, product in enumerate(products):
        job_id = uuid.uuid4().hex[:10]
        stage_base = i / total
        stage_span = 1.0 / total

        def _cb(v: float, s: str, _base=stage_base, _span=stage_span) -> None:
            if progress_callback:
                progress_callback(_base + v * _span, f"[{i+1}/{total}] {s}")

        if progress_callback:
            progress_callback(stage_base, f"[{i+1}/{total}] {product.name}")

        try:
            result = render_product(product, job_id=job_id, progress_callback=_cb)
            # enrich meta for history
            result.meta = {
                **(result.meta or {}),
                "product_name": product.name,
                "category": product.category,
            }
            save_result(result, status="done")
            results.append(result)
            logger.info("Batch item OK | %s | %s", product.name, result.video_path.name)
        except Exception as e:
            logger.exception("Batch item failed | %s", product.name)
            save_failure(job_id, product.name, str(e), category=product.category)
            if progress_callback:
                progress_callback(stage_base + stage_span, f"[{i+1}/{total}] Lỗi: {product.name}")

    if progress_callback:
        progress_callback(1.0, f"Batch xong: {len(results)}/{total} thành công")

    return results


def create_sample_excel(path: Path | str) -> Path:
    """Write a sample template Excel for users."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(
        [
            {
                "name": "Áo thun form rộng cotton",
                "category": "Áo",
                "description": "Cotton 100%, form rộng, giá 99k",
                "price": "99.000đ",
                "target_audience": "Nam nữ 18-28",
                "image_path": "",
                "duration": 30,
                "voice": "Nữ dễ thương (Hoài My)",
            },
            {
                "name": "Giày sneaker trắng basic",
                "category": "Giày",
                "description": "Đế cao su, đi êm, size 36-43",
                "price": "199k",
                "target_audience": "Học sinh sinh viên",
                "image_path": "",
                "duration": 30,
                "voice": "Nam miền Bắc (Nam Minh)",
            },
        ]
    )
    df.to_excel(path, index=False)
    return path
