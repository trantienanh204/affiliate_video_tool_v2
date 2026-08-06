"""
Storyboard generator.

Produces 4–6 scenes with distinct locations, camera, lighting, color grade.
Uses Ollama when available; otherwise a category-aware fallback builder.
"""

from __future__ import annotations

import random
from typing import Optional

from core.config import settings
from core.exceptions import LLMError, LLMUnavailableError
from core.logging import get_logger
from models.product import ProductAnalysis, ProductInput
from models.script import ScriptPackage
from models.storyboard import Scene, Storyboard

from ai.llm.client import OllamaClient, get_ollama_client
from ai.llm.prompts import STORYBOARD_SYSTEM, STORYBOARD_USER

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Category → location pools (never reuse same location for every product)
# ---------------------------------------------------------------------------

_LOCATIONS: dict[str, list[str]] = {
    "Áo": ["Cafe", "Street", "Mirror", "Office", "Park", "Mall", "Bedroom"],
    "Quần": ["Street", "Office", "Cafe", "Outdoor", "Mirror", "Mall"],
    "Giày": ["Street", "Outdoor", "Gym", "Cafe", "Mirror", "Park"],
    "Đồ ăn": ["Kitchen", "Dining table", "Outdoor picnic", "Food stall", "Home living room"],
    "Phụ kiện": ["Cafe", "Street", "Mirror", "Office desk", "Minimal studio"],
    "Mỹ phẩm": ["Bathroom vanity", "Makeup studio", "Mirror close-up", "Bedroom soft light", "Beauty salon"],
    "Đồng hồ": ["Luxury hotel lobby", "Business meeting", "Car interior", "Office desk", "Minimal studio"],
    "Túi": ["Street", "Office", "Cafe", "Mall", "Airport lounge"],
    "Nhà cửa": ["Living room", "Kitchen", "Bedroom", "Balcony", "Home office"],
    "Khác": ["Minimal studio", "Lifestyle home", "Street", "Cafe", "Outdoor"],
}

_CAMERAS = [
    "Close Up", "Wide", "Tracking", "Orbit", "POV", "Handheld",
    "Zoom In", "Zoom Out", "Pan", "Tilt", "Static", "Slow Motion",
]

_LIGHTING = [
    "Natural", "Golden Hour", "Softbox", "Studio", "Morning",
    "Sunset", "Luxury", "Commercial", "Neon", "Moody",
]

_COLOR = [
    "Warm", "Cold", "Luxury", "Minimal", "Commercial",
    "TikTok", "Cinematic", "Vibrant",
]

# Role sequence templates by total scene count
_ROLE_SEQUENCES = {
    4: ["hook", "showcase", "detail", "cta"],
    5: ["hook", "showcase", "lifestyle", "detail", "cta"],
    6: ["hook", "closeup", "lifestyle", "detail", "social_proof", "cta"],
}


def _pick_locations(category: str, n: int) -> list[str]:
    pool = list(_LOCATIONS.get(category, _LOCATIONS["Khác"]))
    random.shuffle(pool)
    if len(pool) >= n:
        return pool[:n]
    # repeat if not enough unique
    return (pool * ((n // len(pool)) + 1))[:n]


def _i2v_prompt(
    product_name: str,
    location: str,
    camera: str,
    lighting: str,
    color: str,
    role: str,
) -> str:
    """English prompt that locks product identity for Image-to-Video models."""
    return (
        f"Keep the exact same product appearance, color, shape and logo. "
        f"Cinematic {camera.lower()} shot of the product in a {location.lower()} setting, "
        f"{lighting.lower()} lighting, {color.lower()} color grade, "
        f"{role} style for TikTok commercial, smooth subtle motion, high detail, 9:16 vertical"
    )


def _fallback_storyboard(
    product: ProductInput,
    analysis: ProductAnalysis,
    script: ScriptPackage,
) -> Storyboard:
    """Rule-based multi-scene storyboard (no LLM)."""
    target = float(product.duration or settings.default_duration)
    num_images = max(1, len(product.image_paths))

    # Decide scene count by duration
    if target <= 25:
        n = 4
    elif target <= 40:
        n = 5
    else:
        n = 6

    roles = _ROLE_SEQUENCES[n]
    locations = _pick_locations(product.category, n)

    # Duration distribution: hook shorter, cta medium, middle flexible
    weights = {
        "hook": 0.18,
        "closeup": 0.15,
        "showcase": 0.22,
        "lifestyle": 0.20,
        "detail": 0.15,
        "social_proof": 0.12,
        "cta": 0.18,
    }
    raw = [weights.get(r, 0.16) for r in roles]
    total_w = sum(raw)
    durations = [round(target * w / total_w, 1) for w in raw]
    # fix rounding drift
    durations[-1] = round(target - sum(durations[:-1]), 1)

    # Text overlays from script
    overlay_map = {
        "hook": script.hook,
        "cta": script.cta,
        "showcase": script.body[:60] if script.body else None,
        "detail": analysis.usp[0] if analysis.usp else None,
    }

    scenes: list[Scene] = []
    for i, role in enumerate(roles):
        camera = (
            "Close Up" if role in ("hook", "detail", "closeup")
            else "Wide" if role == "lifestyle"
            else "Zoom In" if role == "cta"
            else random.choice(["Tracking", "Orbit", "Handheld", "Static"])
        )
        lighting = (
            "Golden Hour" if analysis.mood in ("Warm", "Cinematic")
            else "Studio" if analysis.concept == "Commercial"
            else "Luxury" if analysis.concept == "Luxury"
            else random.choice(["Natural", "Softbox", "Morning"])
        )
        color = analysis.mood if analysis.mood in _COLOR else "Warm"
        loc = locations[i]
        img_idx = i % num_images

        scenes.append(
            Scene(
                scene_id=i + 1,
                role=role,
                description=f"{role.capitalize()} – {product.name} tại {loc}",
                location=loc,
                camera=camera,
                lighting=lighting,
                color_grade=color,
                duration=max(2.0, durations[i]),
                image_index=img_idx,
                i2v_prompt=_i2v_prompt(
                    product.name, loc, camera, lighting, color, role
                ),
                negative_prompt=(
                    "blurry, deformed, text, watermark, logo change, "
                    "color shift, extra limbs, low quality"
                ),
                text_overlay=overlay_map.get(role),
            )
        )

    return Storyboard(
        concept=analysis.concept,
        total_duration=sum(s.duration for s in scenes),
        scenes=scenes,
        transition="crossfade",
        notes=f"Fallback storyboard | category={product.category} | images={num_images}",
    )


def _parse_llm_storyboard(data: dict, product: ProductInput) -> Storyboard:
    """Convert raw LLM JSON into Storyboard model with safety defaults."""
    raw_scenes = data.get("scenes") or []
    scenes: list[Scene] = []
    num_images = max(1, len(product.image_paths))

    for i, s in enumerate(raw_scenes):
        scenes.append(
            Scene(
                scene_id=int(s.get("scene_id") or i + 1),
                role=str(s.get("role") or "showcase"),
                description=str(s.get("description") or ""),
                location=str(s.get("location") or "Studio"),
                camera=str(s.get("camera") or "Close Up"),
                lighting=str(s.get("lighting") or "Natural"),
                color_grade=str(s.get("color_grade") or "Warm"),
                duration=float(s.get("duration") or 5.0),
                image_index=int(s.get("image_index") or 0) % num_images,
                i2v_prompt=str(s.get("i2v_prompt") or ""),
                negative_prompt=str(
                    s.get("negative_prompt")
                    or "blurry, deformed, text, watermark, color change"
                ),
                text_overlay=s.get("text_overlay"),
            )
        )

    if not scenes:
        raise LLMError("LLM returned empty scenes list")

    return Storyboard(
        concept=str(data.get("concept") or "Lifestyle"),
        total_duration=float(data.get("total_duration") or sum(sc.duration for sc in scenes)),
        scenes=scenes,
        transition=str(data.get("transition") or "crossfade"),
        notes=str(data.get("notes") or ""),
    )


def generate_storyboard(
    product: ProductInput,
    analysis: ProductAnalysis,
    script: ScriptPackage,
    client: Optional[OllamaClient] = None,
) -> Storyboard:
    """
    Generate multi-scene storyboard.

    Prefers LLM; falls back to rule-based builder.
    """
    use_client = client or get_ollama_client()

    if settings.llm_provider.value == "fallback" or not use_client.is_available():
        logger.warning("Ollama unavailable → fallback storyboard")
        return _fallback_storyboard(product, analysis, script)

    user_prompt = STORYBOARD_USER.format(
        name=product.name,
        category=product.category,
        concept=analysis.concept,
        mood=analysis.mood,
        usp=", ".join(analysis.usp),
        num_images=max(1, len(product.image_paths)),
        duration=product.duration or settings.default_duration,
    )

    try:
        data = use_client.generate_json(STORYBOARD_SYSTEM, user_prompt, temperature=0.65)
        sb = _parse_llm_storyboard(data, product)
        logger.info(
            "LLM storyboard: %d scenes, total=%.1fs, concept=%s",
            sb.scene_count(),
            sb.total_duration,
            sb.concept,
        )
        return sb
    except (LLMUnavailableError, LLMError) as e:
        logger.warning("LLM storyboard failed (%s) → fallback", e.message)
        return _fallback_storyboard(product, analysis, script)
