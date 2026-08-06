"""
Product analysis + script generation.

Uses Ollama when available; otherwise falls back to smart templates
(improved version of the original tool).
"""

from __future__ import annotations

import random
from typing import Optional

from core.config import settings
from core.exceptions import LLMError, LLMUnavailableError
from core.logging import get_logger
from models.product import ProductAnalysis, ProductInput
from models.script import ScriptPackage

from ai.llm.client import OllamaClient, get_ollama_client
from ai.llm.prompts import ANALYSIS_SYSTEM, ANALYSIS_USER, SCRIPT_SYSTEM, SCRIPT_USER

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Fallback templates (used when Ollama is offline)
# ---------------------------------------------------------------------------

_FALLBACK_USP = {
    "Áo": ["Form chuẩn, tôn dáng", "Chất vải mềm thoáng", "Giá hạt dẻ, dễ phối"],
    "Quần": ["Phom tôn chân", "Co giãn, không nhăn", "Nhiều size"],
    "Giày": ["Êm chân cả ngày", "Đế chống trượt", "Thiết kế trendy"],
    "Đồ ăn": ["Nguyên liệu tươi", "Vị đậm đà", "Giao nhanh còn nóng"],
    "Phụ kiện": ["Nâng tầm outfit", "Bền, không dị ứng", "Giá siêu mềm"],
    "Mỹ phẩm": ["Lành tính", "Hiệu quả rõ", "Phù hợp da Việt"],
    "Đồng hồ": ["Sang trọng", "Pin lâu", "Chống nước"],
    "Túi": ["Sức chứa lớn", "Chất liệu bền", "Thiết kế thời trang"],
    "Nhà cửa": ["Tiện lợi", "Bền đẹp", "Giá hợp lý"],
    "Khác": ["Chất lượng tốt", "Giá hợp lý", "Nhiều người review 5 sao"],
}

_FALLBACK_HOOKS = {
    "Áo": ["Áo này mặc lên form chuẩn luôn á!", "Săn được chiếc áo xịn giá hạt dẻ!", "Mặc cái này đi chơi là nổi bần bật!"],
    "Quần": ["Quần này ống rộng hay suông đều đẹp!", "Tìm quần đi học/đi làm mà vẫn xinh thì đây!", "Quần lưng cao che bụng siêu đỉnh!"],
    "Giày": ["Đôi giày này đi êm chân kinh khủng!", "Giày đẹp giá rẻ, đi mưa không sợ!", "Săn được đôi giày hot trend giá cực tốt!"],
    "Đồ ăn": ["Món này ngon xuất sắc, ăn một lần là ghiền!", "Ship tận nơi, còn nóng hổi!", "Ăn thử đi rồi biết, ngon hơn mình nghĩ!"],
    "Phụ kiện": ["Phụ kiện này làm nổi bật outfit luôn!", "Rẻ mà chất, đeo lên là xinh!", "Item nhỏ nhưng nâng tầm cả set đồ!"],
    "Mỹ phẩm": ["Dùng cái này da mình căng bóng hẳn!", "Review thật, không quảng cáo ảo!", "Sản phẩm đang hot, nên thử ngay!"],
    "Đồng hồ": ["Đeo lên tay là sang hẳn!", "Đồng hồ đẹp giá tốt thế này hiếm lắm!", "Phối đồ công sở hay dạo phố đều ổn!"],
    "Túi": ["Túi này đựng đồ vừa đủ mà vẫn xinh!", "Mang đi làm hay đi chơi đều hợp!", "Chất da/xịn, cầm rất chắc tay!"],
    "Nhà cửa": ["Đồ nhà cửa xinh mà tiện thế này cơ à!", "Mua một lần dùng lâu, đáng tiền!", "Không gian nhà mình lên level luôn!"],
    "Khác": ["Sản phẩm này đáng tiền thật sự!", "Dùng một lần là thích luôn!", "Hot item đang bán chạy, nhanh tay nha!"],
}

_FALLBACK_CTA = [
    "Bấm giỏ hàng góc trái để xem giá và mua ngay nha!",
    "Muốn sở hữu thì bấm giỏ hàng liền tay nha!",
    "Đói bụng / cần gấp thì bấm giỏ hàng đặt ngay nha!",
    "Bấm giỏ hàng để check size và đặt hàng nha!",
]

_CONCEPT_BY_CATEGORY = {
    "Áo": ["Lifestyle", "Street", "Cafe", "Office"],
    "Quần": ["Street", "Office", "Lifestyle", "Outdoor"],
    "Giày": ["Street", "Outdoor", "Lifestyle", "POV"],
    "Đồ ăn": ["Home", "Lifestyle", "Review", "POV"],
    "Phụ kiện": ["Lifestyle", "Minimal", "Street", "Cafe"],
    "Mỹ phẩm": ["Beauty", "Minimal", "Lifestyle", "POV"],
    "Đồng hồ": ["Luxury", "Office", "Commercial", "Minimal"],
    "Túi": ["Lifestyle", "Street", "Office", "Luxury"],
    "Nhà cửa": ["Home", "Lifestyle", "Minimal", "Commercial"],
    "Khác": ["Lifestyle", "Review", "TikTok Viral", "Commercial"],
}


def _fallback_analysis(product: ProductInput) -> ProductAnalysis:
    cat = product.category if product.category in _FALLBACK_USP else "Khác"
    usp = list(_FALLBACK_USP[cat])
    if product.description:
        usp.insert(0, product.description.strip()[:80])
    concept = random.choice(_CONCEPT_BY_CATEGORY.get(cat, _CONCEPT_BY_CATEGORY["Khác"]))
    target = product.target_audience or "Người dùng TikTok quan tâm mua sắm online"
    return ProductAnalysis(
        usp=usp[:5],
        target_audience=target,
        concept=concept,
        mood="Warm" if concept not in ("Luxury", "Minimal") else "Luxury",
        keywords=[product.name, cat, "TikTokShop", "Affiliate", "Review"],
        selling_points=usp[:3],
        avoid=["spam quá nhiều", "text quá dài che sản phẩm"],
        confidence=0.55,
    )


def _fallback_script(product: ProductInput, analysis: ProductAnalysis) -> ScriptPackage:
    cat = product.category if product.category in _FALLBACK_HOOKS else "Khác"
    hook = random.choice(_FALLBACK_HOOKS[cat])
    body = product.description.strip() or random.choice(analysis.usp)
    extra = analysis.usp[1] if len(analysis.usp) > 1 else analysis.usp[0]
    cta = random.choice(_FALLBACK_CTA)
    full = (
        f"{hook} "
        f"Đây là {product.name}. "
        f"{body} "
        f"{extra} "
        f"Nhiều bạn feedback rất tốt, chất lượng ổn trong tầm giá. "
        f"{cta}"
    )
    hashtags = [
        "#TikTokShop",
        "#Affiliate",
        "#Review",
        "#MuaSamOnline",
        f"#{cat.replace(' ', '')}",
        "#HangTotGiaRe",
        "#ReviewThat",
        f"#{product.name.replace(' ', '')[:20]}",
    ]
    caption = (
        f"{hook}\n"
        f"{product.name}\n"
        f"{body}\n\n"
        f"{cta}\n\n"
        + " ".join(hashtags)
    )
    return ScriptPackage(
        hook=hook,
        body=body,
        cta=cta,
        full_script=full,
        caption=caption,
        hashtags=hashtags,
        title=f"Review {product.name}",
        keywords=analysis.keywords,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def analyze_product(
    product: ProductInput,
    client: Optional[OllamaClient] = None,
) -> ProductAnalysis:
    """
    Analyze product → USP, target, concept, mood, keywords.

    Falls back to templates if Ollama is unavailable.
    """
    use_client = client or get_ollama_client()

    if settings.llm_provider.value == "fallback" or not use_client.is_available():
        logger.warning("Ollama unavailable → using fallback analysis")
        return _fallback_analysis(product)

    user_prompt = ANALYSIS_USER.format(
        name=product.name,
        category=product.category,
        description=product.description or "(không có)",
        price=product.price or "(chưa rõ)",
        target_audience=product.target_audience or "(tự suy luận)",
    )

    try:
        data = use_client.generate_json(ANALYSIS_SYSTEM, user_prompt)
        return ProductAnalysis(
            usp=data.get("usp") or [],
            target_audience=data.get("target_audience") or "",
            concept=data.get("concept") or "Lifestyle",
            mood=data.get("mood") or "Warm",
            keywords=data.get("keywords") or [],
            selling_points=data.get("selling_points") or [],
            avoid=data.get("avoid") or [],
            confidence=0.9,
        )
    except (LLMUnavailableError, LLMError) as e:
        logger.warning("LLM analysis failed (%s) → fallback", e.message)
        return _fallback_analysis(product)


def generate_script(
    product: ProductInput,
    analysis: ProductAnalysis,
    client: Optional[OllamaClient] = None,
) -> ScriptPackage:
    """
    Generate full script package (hook, body, cta, caption, hashtags).
    """
    use_client = client or get_ollama_client()

    if settings.llm_provider.value == "fallback" or not use_client.is_available():
        logger.warning("Ollama unavailable → using fallback script")
        return _fallback_script(product, analysis)

    user_prompt = SCRIPT_USER.format(
        name=product.name,
        category=product.category,
        usp=", ".join(analysis.usp) or product.description,
        concept=analysis.concept,
        target_audience=analysis.target_audience,
        price=product.price or "",
        description=product.description or "",
    )

    try:
        data = use_client.generate_json(SCRIPT_SYSTEM, user_prompt)
        hashtags = data.get("hashtags") or []
        # ensure # prefix
        hashtags = [h if h.startswith("#") else f"#{h}" for h in hashtags]
        return ScriptPackage(
            hook=data.get("hook") or "",
            body=data.get("body") or "",
            cta=data.get("cta") or "",
            full_script=data.get("full_script") or "",
            caption=data.get("caption") or "",
            hashtags=hashtags,
            title=data.get("title") or f"Review {product.name}",
            keywords=data.get("keywords") or analysis.keywords,
        )
    except (LLMUnavailableError, LLMError) as e:
        logger.warning("LLM script failed (%s) → fallback", e.message)
        return _fallback_script(product, analysis)


def analyze_and_script(
    product: ProductInput,
    client: Optional[OllamaClient] = None,
) -> tuple[ProductAnalysis, ScriptPackage]:
    """One-shot: analysis + script."""
    analysis = analyze_product(product, client=client)
    script = generate_script(product, analysis, client=client)
    return analysis, script
