"""Ultra-fast, cohesive 1-shot fictional story generator (text-only, no TTS)."""

from __future__ import annotations

import json
import re
from typing import Callable, Optional

from ai.llm.client import OllamaClient
from core.config import settings
from core.logging import get_logger
from models.story import FastStoryInput, FastStoryResult, StoryLength

logger = get_logger(__name__)

ProgressCb = Optional[Callable[[float, str], None]]

_FAST_STORY_SYSTEM = """Bạn là một nhà văn / biên kịch truyện hư cấu xuất sắc.
Nhiệm vụ của bạn là viết một câu chuyện hoàn chỉnh, liền mạch, cuốn hút bằng tiếng Việt tự nhiên.
Quy tắc bất di bất dịch:
1. Liền mạch tuyệt đối: Tình tiết nối nhau bằng quan hệ nguyên nhân - kết quả chặt chẽ. Nhân vật hành động có động cơ rõ ràng.
2. Không mâu thuẫn: Giữ đúng tên, vai vế, tính cách và hoàn cảnh đã đặt ra từ đầu đến cuối.
3. Không ngắt quãng: Kể một mạch trọn vẹn, không viết tóm tắt dàn ý, không tự ý chèn lời chào, câu bình luận của AI hay ghi chú ngoài truyện.
4. Trả về đúng định dạng JSON yêu cầu.
"""

_LENGTH_GUIDELINES = {
    StoryLength.SHORT: ("khoảng 350 - 500 từ", 500),
    StoryLength.MEDIUM: ("khoảng 800 - 1200 từ", 1200),
    StoryLength.LONG: ("khoảng 1500 - 2200 từ", 2200),
}


def _clean_json_str(raw: str) -> str:
    cleaned = raw.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()


def get_instant_template_story(inp: FastStoryInput) -> FastStoryResult:
    """Generate high-quality, instant story without waiting for an LLM."""
    name = inp.protagonist
    premise_txt = inp.premise.strip() or "Một bí mật bị chôn giấu suốt nhiều năm bất ngờ phát lộ."

    if "thiên kim" in inp.trope.lower() or "thân phận" in inp.trope.lower():
        title = f"Ván Cờ Thân Phận Của {name}"
        hook = f"Ngày nhận lại gia đình tài phiệt, {name} mới phát hiện vị trí của mình đã có một người khác thay thế."
        p1 = (
            f"Cơn mưa rào đầu hạ phủ kín bậc thềm biệt thự họ Lâm. {name} đứng đó, bộ quần áo giản dị ướt đẫm, "
            f"trong tay chỉ vỏn vẹn một tờ giấy xét nghiệm ADN đã nhàu nát. Hai mươi năm sống tại vùng quê nghèo, "
            f"{name} chưa từng nghĩ mình lại là đại tiểu thư thất lạc của tập đoàn danh tiếng bậc nhất kinh đô.\n\n"
            f"Nhưng cánh cửa gỗ lim mở ra không mang lại hơi ấm đoàn viên. Người bước ra đầu tiên không phải bố mẹ ruột, "
            f"mà là Diễm My – cô con gái nuôi được gia đình cưng chiều như ngọc quý. Diễm My khẽ cười khẩy, "
            f"ánh mắt sắc lạnh như muốn nói rằng nơi này không có chỗ cho kẻ thứ hai."
        )
        p2 = (
            f"Những ngày sau đó trong căn biệt thự xa hoa trở thành một chiến trường không khói súng. "
            f"Mỗi cử chỉ, lời ăn tiếng nói của {name} đều bị đem ra soi xét và chê bai. Người mẹ ruột ái ngại nhìn cô, "
            f"trong khi người cha bận rộn chỉ căn dặn: 'Đừng làm ảnh hưởng đến danh dự gia đình'. Nhưng họ không hề biết, "
            f"hai mươi năm lăn lộn ngoài đời đã tôi luyện cho {name} một trực giác nhạy bén và ý chí kiên cường.\n\n"
            f"{name} âm thầm kiểm tra sổ sách công ty gia đình và phát hiện Diễm My cùng người bác ruột đang biển thủ "
            f"hàng trăm tỷ đồng, chuẩn bị đẩy họ Lâm vào bờ vực phá sản. {premise_txt}"
        )
        p3 = (
            f"Đêm tiệc kỷ niệm ba mươi năm thành lập tập đoàn, Diễm My bước lên sân khấu chuẩn bị đón nhận quyết định bổ nhiệm. "
            f"Đúng lúc ấy, màn hình lớn phía sau bất ngờ chuyển sang tập hồ sơ kiểm toán mật do chính {name} thu thập. "
            f"Từng chứng cứ chuyển tiền, từng đoạn ghi âm âm mưu chiếm đoạt tài sản vang lên rõ mồn một trước hàng trăm quan khách.\n\n"
            f"Diễm My tái mặt ngã quỵ, còn cha mẹ {name} bàng hoàng nhìn đứa con gái mà họ từng xem nhẹ. "
            f"{name} bước lên sân khấu, nụ cười bình thản nhưng kiên định. Cô không cần một vị trí danh nghĩa được ban phát, "
            f"bởi bằng chính bản lĩnh của mình, cô đã trở thành người làm chủ cuộc chơi."
        )
    elif "phản bội" in inp.trope.lower() or "tái sinh" in inp.trope.lower():
        title = f"Ngọn Lửa Tái Sinh Của {name}"
        hook = f"Khoảnh khắc mất đi tất cả cũng là lúc {name} nhận ra mình đã trao lòng tin nhầm chỗ."
        p1 = (
            f"Gió lạnh thấu xương lùa qua căn phòng trọ nhỏ hẹp. {name} nhìn chăm chú vào bản hợp đồng bị xé vụn trên bàn. "
            f"Người bạn thân nhất và đối tác tin cậy nhất đã cấu kết cướp đi toàn bộ công sức gây dựng suốt năm năm qua của cô. "
            f"Mọi người đều nghĩ {name} sẽ gục ngã, nhưng trong đôi mắt cô lúc này chỉ có sự tĩnh lặng đến lạnh người."
        )
        p2 = (
            f"Không một lời oán trách, không một giọt nước mắt thừa thãi. {name} bắt đầu lại từ con số không tròn trĩnh. "
            f"Cô tận dụng từng mối quan hệ cũ còn sót lại, làm việc mười sáu tiếng mỗi ngày để hoàn thiện một dự án hoàn toàn mới. "
            f"{premise_txt}\n\n"
            f"Trong khi kẻ phản bội mải mê tự mãn với chiến lợi phẩm cướp được, {name} âm thầm nắm bắt bước chuyển mình của thị trường, "
            f"tạo ra sản phẩm vượt trội gấp nhiều lần."
        )
        p3 = (
            f"Sáu tháng sau, tại buổi đấu thầu lớn nhất năm, kẻ phản bội tự tin bước vào với tư thế người chiến thắng. "
            f"Nhưng hội đồng giám khảo đồng loạt đứng dậy chào đón nhà đầu tư chiến lược vừa thâu tóm toàn bộ cổ phần chi phối. "
            f"Người bước vào trong bộ vest thanh lịch, ánh mắt sáng rực tự tin chính là {name}. "
            f"Sự trả thù ngọt ngào nhất không phải là đánh bại kẻ thù bằng thủ đoạn, mà là vươn lên tầm cao mà họ mãi mãi không thể với tới."
        )
    else:
        title = f"Bước Ngoặt Định Mệnh Của {name}"
        hook = f"{name} chưa từng nghĩ một quyết định bất ngờ lại thay đổi hoàn toàn quỹ đạo cuộc đời mình."
        p1 = (
            f"Thành phố lúc hai giờ sáng vẫn sáng rực ánh đèn đường nhưng chìm trong tĩnh mịch. "
            f"{name} ngồi lại bên bàn làm việc, ánh mắt dừng lại ở bức thư gửi từ một địa chỉ vô danh. "
            f"{premise_txt}"
        )
        p2 = (
            f"Từng manh mối dần hé lộ đưa {name} bước vào một hành trình đầy thử thách. "
            f"Những người ngỡ như xa lạ lại có sợi dây liên kết kỳ lạ với quá khứ của cô. "
            f"Dù bao lần đối mặt với nguy hiểm và toan tính, {name} vẫn giữ vững sự tỉnh táo và trái tim ấm áp."
        )
        p3 = (
            f"Khi bức màn bí mật cuối cùng được kéo lên, sự thật không chỉ minh oan cho những hiểu lầm trong quá khứ "
            f"mà còn mở ra cho {name} một con đường hoàn toàn mới. "
            f"Cô mỉm cười đón nhận ánh nắng ban mai, sẵn sàng cho những chương mới rực rỡ phía trước."
        )

    p2_extra = (
        f"Trong bóng tối của những âm mưu toan tính, {name} từng bước gỡ bỏ từng cạm bẫy đối phương giăng ra. "
        f"Mỗi người tưởng chừng thân cận đều lần lượt lộ rõ tâm cơ thực sự. "
        f"Nhưng thay vì hoang mang, {name} biến từng trở ngại thành đòn bẩy chiến lược để xoay chuyển cục diện."
    )

    if inp.length == StoryLength.SHORT:
        content = f"{p1}\n\n{p3}"
    elif inp.length == StoryLength.LONG:
        content = f"{p1}\n\n{p2}\n\n{p2_extra}\n\n{p3}"
    else:
        content = f"{p1}\n\n{p2}\n\n{p3}"

    words = len(re.findall(r"\w+", content))
    return FastStoryResult(
        title=title,
        hook=hook,
        content=content,
        caption=f"🔥 {title}\n\n{hook}\n\nTheo dõi để đọc tiếp những câu chuyện kịch tính tiếp theo!",
        hashtags=["#truyenngan", "#tieuthuyet", "#drama", f"#{re.sub(r'[^a-zA-Z0-9]', '', name).lower()}"],
        word_count=words,
        estimated_read_time_minutes=round(words / 200, 1),
        mode="template",
    )


def generate_fast_story(
    inp: FastStoryInput,
    client: OllamaClient | None = None,
    progress_callback: ProgressCb = None,
) -> FastStoryResult:
    """
    Generate story via fast 1-shot LLM with immediate template fallback.
    Guarantees fast response and zero audio/TTS overhead.
    """
    if progress_callback:
        progress_callback(0.15, "Đang khởi tạo cốt truyện liền mạch...")

    if client is None:
        try:
            client = OllamaClient(timeout=min(settings.ollama_timeout, 90))
        except Exception:
            client = None

    if client is None or not client.is_available():
        logger.info("Ollama client unavailable; generating via Instant Template Generator")
        if progress_callback:
            progress_callback(0.85, "Đang hoàn thiện truyện bằng Instant Template...")
        res = get_instant_template_story(inp)
        if progress_callback:
            progress_callback(1.0, f"Đã viết xong truyện ({res.word_count} từ)")
        return res

    length_text, max_tokens = _LENGTH_GUIDELINES.get(inp.length, _LENGTH_GUIDELINES[StoryLength.MEDIUM])

    user_prompt = f"""Hãy viết một câu chuyện hoàn chỉnh với các thông tin sau:
- Thể loại / Mô-típ: {inp.trope}
- Ý tưởng cốt lõi: {inp.premise or "Tự do sáng tạo phù hợp mô-típ"}
- Nhân vật chính: {inp.protagonist}
- Tông giọng: {inp.tone}
- Kiểu kết: {inp.ending}
- Độ dài mục tiêu: {length_text}

Yêu cầu xuất ra định dạng JSON:
{{
  "title": "Tiêu đề truyện ấn tượng",
  "hook": "Câu mở đầu gây tò mò, kịch tính",
  "content": "Toàn bộ nội dung truyện chia các đoạn văn mạch lạc bằng 2 dấu xuống dòng",
  "caption": "Mô tả ngắn gọn thu hút đăng mạng xã hội",
  "hashtags": ["#tag1", "#tag2", "#tag3"]
}}
"""
    if progress_callback:
        progress_callback(0.35, "AI đang viết toàn bộ câu chuyện 1-shot...")

    try:
        raw_resp = client.chat(
            messages=[
                {"role": "system", "content": _FAST_STORY_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens + 500,
            temperature=0.75,
            format_json=True,
        )

        cleaned = _clean_json_str(raw_resp)
        data = json.loads(cleaned)

        title = str(data.get("title", f"Câu chuyện của {inp.protagonist}")).strip()
        hook = str(data.get("hook", "")).strip()
        content = str(data.get("content", "")).strip()
        caption = str(data.get("caption", "")).strip()
        hashtags = [str(t).strip() for t in data.get("hashtags", []) if str(t).strip()]

        if not content:
            logger.warning("LLM returned empty content, falling back to template")
            return get_instant_template_story(inp)

        words = len(re.findall(r"\w+", content))
        if progress_callback:
            progress_callback(1.0, f"Đã viết xong truyện ({words} từ)")

        return FastStoryResult(
            title=title,
            hook=hook,
            content=content,
            caption=caption or f"🔥 {title}\n\n{hook}",
            hashtags=hashtags or ["#truyenngan", "#tieuthuyet"],
            word_count=words,
            estimated_read_time_minutes=round(words / 200, 1),
            mode="ollama",
        )
    except Exception as exc:
        logger.warning("Fast story generation with LLM failed (%s), falling back to template", exc)
        if progress_callback:
            progress_callback(0.8, "Chuyển sang bộ mẫu sáng tạo tức thì...")
        res = get_instant_template_story(inp)
        if progress_callback:
            progress_callback(1.0, f"Đã viết xong truyện ({res.word_count} từ)")
        return res
