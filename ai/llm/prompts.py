"""
Prompt templates for product analysis & script generation.

All prompts are in Vietnamese to maximize quality with Qwen2.5 / Llama
on Vietnamese affiliate content.
"""

from __future__ import annotations

ANALYSIS_SYSTEM = """Bạn là chuyên gia marketing TikTok Shop Affiliate Việt Nam.
Nhiệm vụ: phân tích sản phẩm và đưa ra chiến lược video bán hàng ngắn (15–45 giây).

Luôn trả lời ĐÚNG định dạng JSON, không thêm markdown hay giải thích ngoài JSON.
"""

ANALYSIS_USER = """Phân tích sản phẩm sau và trả về JSON với các field:

{{
  "usp": ["usp1", "usp2", "usp3"],          // 3-5 điểm bán chính, ngắn gọn
  "target_audience": "mô tả khách hàng mục tiêu",
  "concept": "một trong: Lifestyle|Review|Luxury|TikTok Viral|POV|Office|Outdoor|Beauty|Minimal|Commercial|Street|Cafe|Home",
  "mood": "một trong: Warm|Cold|Luxury|Minimal|Commercial|TikTok|Cinematic|Vibrant",
  "keywords": ["kw1", "kw2", ...],          // 5-10 keyword SEO / hashtag seed
  "selling_points": ["điểm nổi bật 1", ...],
  "avoid": ["điều cần tránh khi làm video"]
}}

Thông tin sản phẩm:
- Tên: {name}
- Danh mục: {category}
- Mô tả: {description}
- Giá: {price}
- Đối tượng (nếu có): {target_audience}
"""

SCRIPT_SYSTEM = """Bạn là copywriter TikTok Shop Affiliate chuyên viết script voiceover tiếng Việt tự nhiên, gần gũi, tạo FOMO.
Script phải nghe như người thật đang review, không cứng nhắc, không quá bán hàng.

Trả về ĐÚNG JSON, không markdown.
"""

SCRIPT_USER = """Viết script video affiliate cho sản phẩm sau.

Yêu cầu:
- Hook: 1 câu mạnh, gây tò mò (dưới 15 từ), phù hợp TikTok.
- Body: 2-3 câu nêu USP + lợi ích thực tế.
- CTA: kêu gọi bấm giỏ hàng / mua ngay, thân thiện.
- full_script: nối Hook + giới thiệu tên SP + Body + social proof ngắn + CTA (đủ ~25-40 giây đọc).
- caption: caption đăng TikTok (có emoji nhẹ, xuống dòng đẹp).
- hashtags: 8-12 hashtag (bắt đầu bằng #).
- title: title ngắn dưới 10 từ.
- keywords: 5-8 keyword.

Sản phẩm:
- Tên: {name}
- Danh mục: {category}
- USP: {usp}
- Concept: {concept}
- Target: {target_audience}
- Giá: {price}
- Mô tả thêm: {description}

JSON schema:
{{
  "hook": "...",
  "body": "...",
  "cta": "...",
  "full_script": "...",
  "caption": "...",
  "hashtags": ["#...", ...],
  "title": "...",
  "keywords": ["...", ...]
}}
"""

STORYBOARD_SYSTEM = """Bạn là đạo diễn video quảng cáo TikTok ngắn.
Nhiệm vụ: tạo storyboard 4–6 cảnh dựa trên concept và sản phẩm.
Mỗi cảnh phải có bối cảnh (location) khác nhau phù hợp sản phẩm, không dùng 1 bối cảnh chung.

Trả về ĐÚNG JSON.
"""

STORYBOARD_USER = """Tạo storyboard cho video affiliate.

Sản phẩm: {name}
Danh mục: {category}
Concept: {concept}
Mood/Color: {mood}
USP: {usp}
Số ảnh có sẵn: {num_images}
Độ dài mục tiêu: {duration} giây

Yêu cầu:
- 4 đến 6 scenes.
- Scene đầu = hook, scene cuối = cta.
- Mỗi scene có: location riêng (Cafe, Office, Street, Mirror, Kitchen, Studio, Outdoor, Bedroom, Mall...), camera, lighting, color_grade, duration (giây), description tiếng Việt, i2v_prompt tiếng Anh (giữ nguyên sản phẩm, không đổi màu/logo/hình dạng).
- Tổng duration xấp xỉ {duration} giây.
- image_index: 0-based, xoay vòng nếu ít ảnh hơn số scene.

JSON schema:
{{
  "concept": "{concept}",
  "total_duration": {duration},
  "transition": "crossfade",
  "notes": "...",
  "scenes": [
    {{
      "scene_id": 1,
      "role": "hook",
      "description": "...",
      "location": "...",
      "camera": "Close Up|Wide|Tracking|Orbit|POV|Handheld|Zoom In|Pan|Tilt|Static",
      "lighting": "Natural|Golden Hour|Softbox|Studio|Morning|Sunset|Luxury|Commercial",
      "color_grade": "Warm|Cold|Luxury|Minimal|Commercial|TikTok|Cinematic",
      "duration": 5.0,
      "image_index": 0,
      "i2v_prompt": "English prompt for image-to-video, product identity locked...",
      "negative_prompt": "blurry, deformed, text, watermark, color change, logo change",
      "text_overlay": "optional short text or null"
    }}
  ]
}}
"""
