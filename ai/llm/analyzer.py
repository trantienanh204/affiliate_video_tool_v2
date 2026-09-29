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
    "Áo": ["Thiết kế dễ phối đồ"], "Quần": ["Kiểu dáng dễ phối đồ"],
    "Giày": ["Thiết kế phù hợp nhiều phong cách"], "Đồ ăn": ["Sản phẩm tiện chọn mua"],
    "Phụ kiện": ["Thiết kế tạo điểm nhấn"], "Mỹ phẩm": ["Bao bì và sản phẩm như hình"],
    "Đồng hồ": ["Thiết kế phù hợp nhiều phong cách"], "Túi": ["Kiểu dáng tiện phối đồ"],
    "Nhà cửa": ["Thiết kế hướng đến sự tiện dụng"], "Khác": ["Cùng xem chi tiết sản phẩm"],
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

# CTA theo category — không dùng chung (tránh "đói bụng" cho áo)
_FALLBACK_CTA: dict[str, list[str]] = {
    "Áo": [
        "Bấm giỏ hàng góc trái để xem giá và mua ngay nha!",
        "Muốn mặc đẹp thì bấm giỏ hàng liền tay nha!",
        "Check size và đặt hàng ở giỏ góc trái nha!",
    ],
    "Quần": [
        "Bấm giỏ hàng để chọn size và mua ngay nha!",
        "Muốn sở hữu thì bấm giỏ hàng liền tay nha!",
    ],
    "Giày": [
        "Bấm giỏ hàng góc trái để check size và đặt hàng nha!",
        "Muốn đi êm thì bấm giỏ hàng đặt ngay nha!",
    ],
    "Đồ ăn": [
        "Đói bụng thì bấm giỏ hàng đặt ngay nha!",
        "Ship tận nơi — bấm giỏ hàng góc trái nha!",
    ],
    "Phụ kiện": [
        "Bấm giỏ hàng để sở hữu ngay nha!",
        "Rẻ mà xinh — bấm giỏ hàng liền tay nha!",
    ],
    "Mỹ phẩm": [
        "Bấm giỏ hàng để trải nghiệm ngay nha!",
        "Muốn da đẹp thì đặt ở giỏ hàng góc trái nha!",
    ],
    "Đồng hồ": [
        "Bấm giỏ hàng để sở hữu ngay nha!",
        "Sang mà giá tốt — đặt ở giỏ hàng liền nha!",
    ],
    "Túi": [
        "Bấm giỏ hàng góc trái để mua ngay nha!",
        "Muốn xách đẹp thì đặt hàng liền tay nha!",
    ],
    "Nhà cửa": [
        "Bấm giỏ hàng để order về nhà ngay nha!",
        "Tiện mà xinh — đặt ở giỏ hàng góc trái nha!",
    ],
    "Khác": [
        "Bấm giỏ hàng góc trái để xem giá và mua ngay nha!",
        "Muốn sở hữu thì bấm giỏ hàng liền tay nha!",
    ],
}

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
    elif product.image_description:
        usp.insert(0, product.image_description.strip()[:100])
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
    # Conversational openings, without unverified superlatives or fake claims.
    hook_pool = {
        "Áo": [
            "Một chiếc áo basic, nhưng nhìn kỹ có vài điểm khá hay.",
            "Nếu bạn thích mặc đơn giản, thử ngó qua mẫu áo này nhé.",
            "Đang tìm một chiếc áo dễ mặc mỗi ngày? Xem mẫu này nha.",
            "Mẫu áo này hợp với những hôm muốn chọn đồ thật nhanh.",
        ],
        "Quần": [
            "Thử xem chiếc quần này có hợp với tủ đồ của bạn không nhé.",
            "Một mẫu quần nhìn gọn gàng, mình cùng xem chi tiết nha.",
            "Nếu đang tìm quần mới, bạn có thể tham khảo mẫu này.",
        ],
        "Giày": [
            "Mình cùng xem kỹ đôi giày này trước khi chọn nhé.",
            "Đang tìm một đôi giày mới? Đây là mẫu bạn có thể tham khảo.",
        ],
        "Khác": [
            "Mình vừa thấy món này, cùng xem thử có gì đáng chú ý nhé.",
            "Nếu bạn đang cân nhắc món này, xem nhanh vài thông tin nha.",
        ],
    }
    hook = random.choice(hook_pool.get(cat, hook_pool["Khác"]))
    # Treat free-form description/target as fallible. Without an LLM there is
    # no safe way to reconcile contradictions, so only use concise visual facts.
    visual = (product.image_description or "").strip()
    safe_visual = visual[:180].rstrip(" .")
    if safe_visual:
        body = f"Trong ảnh, mình thấy {safe_visual[0].lower() + safe_visual[1:]}."
    elif cat in ("Áo", "Quần", "Giày", "Túi", "Phụ kiện"):
        body = "Nếu đang cân nhắc mẫu này, mình có thể xem kỹ kiểu dáng, chi tiết và thông tin size trước khi chọn."
    else:
        body = "Mình cùng xem qua sản phẩm và những thông tin cần thiết trước khi chọn nhé."
    price = ""
    if product.price:
        raw_price = product.price.strip()
        digits = "".join(ch for ch in raw_price if ch.isdigit())
        if digits and len(digits) >= 4 and not any(ch in raw_price.lower() for ch in "kđđồng"):
            try:
                raw_price = f"{int(digits):,}".replace(",", ".") + " đồng"
            except ValueError:
                pass
        price = f"Mức giá tham khảo là {raw_price}. "
    cta_pool = _FALLBACK_CTA.get(cat) or _FALLBACK_CTA["Khác"]
    cta = (
        "Bạn xem bảng size và thông tin sản phẩm ở giỏ hàng trước khi chọn nha!"
        if cat in ("Áo", "Quần", "Giày")
        else random.choice(cta_pool)
    )
    full = f"{hook} Đây là {product.name}. {body} {price}{cta}"
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

    if product.image_paths and not product.image_description:
        product.image_description = use_client.describe_product_images(
            product.image_paths, product_name=product.name, category=product.category
        )

    user_prompt = ANALYSIS_USER.format(
        name=product.name,
        category=product.category,
        description="\n".join(filter(None, [
            product.description or "",
            "Đặc điểm nhìn thấy trong ảnh: " + product.image_description if product.image_description else "",
        ])) or "(không có)",
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
        usp=", ".join(analysis.usp) or product.description or product.image_description,
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
