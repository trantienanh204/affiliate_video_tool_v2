"""Generate long fictional narration using a local Ollama model."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable

from ai.llm.client import OllamaClient, get_ollama_client
from core.config import settings
from core.exceptions import LLMError, LLMUnavailableError
from core.logging import get_logger
from models.story import StoryInput, StoryPackage

logger = get_logger(__name__)

_SYSTEM = """Bạn là biên kịch truyện audio dài theo phong cách tiểu thuyết mạng hiện đại:
giọng kể gần gũi, cảm xúc rõ, tình tiết nối nhau bằng nguyên nhân và hệ quả. Viết như
một câu chuyện hoàn chỉnh để người nghe muốn nghe tiếp, không phải bản tóm tắt dàn ý.
Đây là tác phẩm hư cấu. Chỉ viết tiếng Việt tự nhiên. Không tự đổi ngôi kể, tên, giới tính,
quan hệ, bối cảnh hay thời gian đã thống nhất. Không lặp cảnh/lời thoại, không viết câu
đệm chung chung, không nhắc đến AI, prompt, yêu cầu, sửa văn bản hay quá trình tạo truyện."""

_OUTLINE_PROMPT = """Lập hồ sơ truyện và dàn ý cho một truyện audio hư cấu dài khoảng {duration_minutes} phút.

MÔ-TÍP: {trope}
Ý TƯỞNG GỐC (đây là trục chính bắt buộc của truyện): {premise}
QUY TẮC CANON CỤ THỂ:
{canon_rules}
KHUNG CỐT TRUYỆN:
{blueprint}
NHÂN VẬT CHÍNH: {protagonist}
TÔNG: {tone}
KIỂU KẾT: {ending}

Ý TƯỞNG GỐC là sự thật cố định, không được thay bằng truyện mẫu khác. Giữ đúng mọi
quan hệ, biến cố, mốc thời gian, địa điểm và chi tiết người dùng đã nêu. premise_anchor
phải diễn đạt lại chính xác ý tưởng đó. Nếu người dùng viết "tôi", kể ngôi thứ nhất
xuyên suốt. Nếu truyện đặt ở hiện đại thì tuyệt đối không đưa cung đình, cổ trang, lăng
viên, hoàng đế hay cách xưng hô cổ vào. Mô-típ chỉ là khung thể loại, không được lấn át
ý tưởng. Không bịa quan hệ huyết thống trái với ý tưởng.

Hãy coi nguyên văn ý tưởng gốc là "sổ canon" bất di bất dịch. Không tự đổi gia đình,
thứ tự anh chị em, quan hệ, tuổi, địa điểm, thời gian hoặc biến cố. Không dựng thành truyện
cổ trang nếu người dùng không yêu cầu. Mở truyện bằng biến cố trong ý tưởng gốc, không tự
tạo một sự kiện mở đầu khác.

Tạo đúng 8 chương nối tiếp nhau. Xây tiến trình như truyện audio cuốn hút: mở ngay bằng
một biến cố hoặc cảnh đối đầu; sau đó hé lộ từng phần, tăng xung đột, có lựa chọn khó,
đảo chiều hợp lý, cao trào và kết đúng kiểu đã chọn. Mỗi chương phải có mục tiêu nhân vật,
một sự kiện cụ thể, trở ngại, thay đổi cảm xúc/thông tin và hậu quả dẫn sang chương sau.
Mỗi chương phải tiến triển một bước mới, không kể lại cùng một bí mật hoặc cuộc tranh cãi.
Tạo hồ sơ nhân vật ngắn nhưng rõ: tuổi tương đối, quan hệ, điều họ muốn, điều họ che giấu.
Lập mốc thời gian và quan hệ gia đình nhất quán. Mỗi chương có 3 diễn biến cụ thể, không
viết beat chung chung kiểu "mọi người quyết định tìm hiểu sự thật".

Trả JSON:
{{
  "title": "tiêu đề gợi tò mò",
  "premise_anchor": "tóm tắt chính xác ý tưởng gốc trong một câu",
  "hook": "một câu mở đầu đúng ngôi kể và biến cố người dùng nhập",
  "narrative_pov": "ngôi kể đã chọn",
  "setting": "thời đại và địa điểm nhất quán",
  "characters": ["tên: tuổi tương đối, vai trò/quan hệ, mục tiêu, bí mật nếu có"],
  "chapters": [
    {{"title": "...", "beat": "3 diễn biến cụ thể có nguyên nhân và kết quả", "obstacle": "trở ngại riêng", "turn": "bước ngoặt cuối chương"}}
  ]
}}
"""

_CHAPTER_PROMPT = """Viết chương {chapter_number}/8 của truyện, khoảng {min_units}–{max_units}
tiếng Việt (đếm theo cụm cách nhau bằng dấu cách). Chương này là một phần của truyện
dài tối thiểu 15 phút; đừng rút thành tóm tắt.

Ý TƯỞNG GỐC — phải được giữ xuyên suốt: {premise}
QUY TẮC CANON CỤ THỂ:
{canon_rules}
KHUNG CỐT TRUYỆN:
{blueprint}
Premise đã chốt trong dàn ý: {premise_anchor}
Mô-típ: {trope}
Nhân vật chính: {protagonist}
Tông kể: {tone}
Kiểu kết toàn truyện: {ending}
Tiêu đề truyện: {title}
Ngôi kể đã chọn: {narrative_pov}
Bối cảnh đã chốt: {setting}
Các nhân vật và quan hệ đã chốt:
{characters}

DÀN Ý 8 CHƯƠNG:
{outline}

ĐOẠN KẾT CỦA NHỮNG CHƯƠNG ĐÃ VIẾT (nếu là chương đầu thì ghi “chưa có”):
{previous}

CHƯƠNG CẦN VIẾT:
{chapter}

Quy tắc:
- Kể đúng ngôi đã chọn từ đầu đến cuối. Nhân vật xưng hô theo đúng tuổi và quan hệ; nếu
  chưa chắc cách gọi thì dùng tên, tuyệt đối không đảo anh/chị/em hay mẹ/con.
- Nếu ngôi kể là ngôi thứ nhất, câu đầu tiên phải bắt đầu bằng "Tôi" và không được mở bằng
  tên nhân vật ở ngôi thứ ba. Giữ ngôi kể ấy xuyên suốt, không chuyển qua lại giữa "tôi" và "cô".
- Bám từng diễn biến của beat; không đổi tên, giới tính, gia đình, động cơ, nghề nghiệp,
  thời đại hoặc địa điểm. Không đưa nhân vật mới vào nếu không cần cho beat.
- Viết 3 cảnh liền mạch: nhân vật muốn điều gì -> ai/cái gì cản trở -> họ làm gì -> việc đó
  gây hậu quả gì. Dùng hành động, đối thoại có dụng ý và chi tiết cụ thể thay vì kể cảm xúc
  bằng những câu lặp như "lòng đầy phức tạp", "mọi chuyện chỉ mới bắt đầu".
- Mở thẳng vào hành động tiếp theo sau chương trước; không tả thời tiết/đường đi cho dài,
  không nhắc lại phần trước, không hỏi lại câu đã được trả lời.
- Mỗi đoạn phải đưa thêm thông tin, hành động hoặc phản ứng mới. Không lặp nguyên câu,
  đoạn, cuộc đối thoại hay lời hứa. Không tự bịa thêm bí mật chỉ để kéo dài.
- Đối thoại phải tự nhiên, mỗi người nói có mục đích riêng; tránh độc thoại giải thích điều
  người nghe đã biết. Không biến anh/em thành chị/em hoặc đổi vai giữa câu.
- Kết bằng đúng bước chuyển đã định. Chỉ chương cuối mới giải quyết xung đột chính.
- Chương 8 phải khép lại theo kiểu kết đã chọn.
- Chỉ trả lời nội dung truyện bằng tiếng Việt. Không JSON, markdown, lời dẫn của người viết,
  lời xin lỗi, nhận xét, nhãn chương hoặc câu như "dưới đây là đoạn đã sửa".
"""

_CJK_RE = re.compile(r"[\u3400-\u9fff]")
_NUMBER_WORDS = {
    "1": "một",
    "2": "hai",
    "3": "ba",
    "4": "bốn",
    "5": "năm",
    "6": "sáu",
    "7": "bảy",
    "8": "tám",
    "9": "chín",
    "10": "mười",
    "11": "mười một",
    "12": "mười hai",
    "13": "mười ba",
    "14": "mười bốn",
    "15": "mười lăm",
    "16": "mười sáu",
    "17": "mười bảy",
    "18": "mười tám",
    "19": "mười chín",
    "20": "hai mươi",
}
def _remove_foreign_sentences(text: str) -> str:
    """Remove sentences containing CJK characters without inserting repetitive filler."""
    sentences = re.split(r"(?<=[.!?。！？])\s*", text)
    cleaned: list[str] = []
    removed = 0
    for sentence in sentences:
        if not sentence.strip():
            continue
        if _CJK_RE.search(sentence):
            removed += 1
        else:
            cleaned.append(sentence.strip())
    if removed:
        logger.warning("Removed %d story sentence(s) containing CJK text", removed)
    return " ".join(cleaned).strip()


_META_LINE_RE = re.compile(
    r"(?im)^\s*(?:đoạn văn đã được viết lại|dưới đây là đoạn|bản sửa|lời dẫn|ghi chú của người viết|"
    r"tôi đã (?:viết|sửa)|sau đây là|theo yêu cầu|chapter \d+|chương \d+)\b.*$"
)


def _clean_narration(text: str) -> str:
    """Remove model scaffolding and exact repeated sentences before saving a chapter."""
    fence = chr(96) * 3
    text = re.sub(rf"{re.escape(fence)}[^\n]*", "", text)
    text = _META_LINE_RE.sub("", text)
    text = re.sub(r"(?m)^\s*[-*_]{3,}\s*$", "", text)
    sentences = re.split(r"(?<=[.!?…])\s+|\n+", text.strip())
    seen: set[str] = set()
    cleaned: list[str] = []
    for sentence in sentences:
        sentence = sentence.strip().strip("*_ ")
        key = re.sub(r"[^\w\s]", "", sentence.casefold())
        key = re.sub(r"\s+", " ", key).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        cleaned.append(sentence)
    return " ".join(cleaned).strip()


def _is_identity_swap_story(story: StoryInput) -> bool:
    text = f"{story.trope} {story.premise}".casefold()
    return any(term in text for term in ("thiên kim", "thật giả", "tráo", "đánh tráo", "bế nhầm")) and (
        "giúp việc" in text or "người hầu" in text
    )


def _elapsed_years(story: StoryInput) -> str:
    match = re.search(r"(\d+)\s*năm", story.premise.casefold())
    if not match:
        return "nhiều"
    number = match.group(1)
    return _NUMBER_WORDS.get(number, number)


def _story_blueprint(story: StoryInput) -> str:
    if not _is_identity_swap_story(story):
        return "Mỗi chương phải có biến cố và quyết định mới, không lặp một cuộc tìm sự thật."
    return """Mô-típ thiên kim thật giả: đây là mạch truyện bắt buộc, không tự đổi thành bí ẩn chung chung.
1) Mở ngay ở hiện tại khi manh mối về vụ tráo đổi sau {years} năm xuất hiện; người kể sống trong
   gia đình của bà giúp việc, không phải đã lớn lên trong biệt thự của gia tộc giàu có.
2) Người của gia tộc Bắc Kinh tìm đến; nhân vật chính yêu cầu bằng chứng độc lập (xét nghiệm,
   hồ sơ sinh hoặc đối chiếu nhiều nguồn), không tin một cuốn nhật ký đơn lẻ.
3) Kết quả xác nhận nhân vật chính là con ruột gia tộc; con gái bà giúp việc mới là người
   được nuôi trong nhà giàu. Cho hai cô gái phản ứng có mục tiêu riêng, không mặc định ai ác.
4) Nhân vật chính bước vào gia đình mới, vấp xung đột cụ thể với một người thân và người
   đang giữ vị trí con gái trong nhà; kết quả kiểm chứng thứ hai mở ra manh mối vụ tráo.
5) Người mẹ nuôi/bà giúp việc kể phần sự thật của mình, có lý do và bằng chứng; phân biệt
   rõ mẹ nuôi với mẹ ruột, không đổi vai giữa truyện.
6) Người có động cơ che giấu tìm cách bác bỏ bằng chứng; nhân vật chính chủ động tìm nguồn
   độc lập và phát hiện một chi tiết khiến giả thuyết cũ phải thay đổi.
7) Đối chất công khai hoặc trong gia đình, sự thật được xác nhận bằng các bằng chứng đã gieo,
   không có nhân vật mới xuất hiện để giải thích mọi thứ.
8) Giải quyết hậu quả theo kiểu kết người dùng chọn. Không xóa sạch tổn thương bằng một câu
   xin lỗi; mỗi quan hệ cần một hành động cụ thể để bắt đầu hàn gắn.
Mỗi chương tiến thêm một nấc; không lặp cảnh tra hỏi, lời hứa "tìm hiểu thêm" hoặc kết luận
   "giữ bí mật" sau khi nhân vật đã quyết tâm phơi bày sự thật.""".format(years=_elapsed_years(story))


def _identity_swap_chapters(story: StoryInput) -> list[dict[str, str]]:
    years = _elapsed_years(story)
    beats = [
        ("Dấu vết năm thứ {years}", "Tôi lớn lên trong nhà của mẹ nuôi là bà giúp việc. Một giấy tờ sinh cũ khiến bà hoảng hốt; trên đó có mã bệnh viện và ngày sinh trùng với hồ sơ của gia tộc giàu nhất Bắc Kinh. Tôi quyết định tự kiểm chứng.", "Mẹ nuôi muốn giấu tờ giấy vì sợ mất tôi.", "Một người của gia tộc tìm đến và nói họ cũng đang tìm đứa con thất lạc."),
        ("Hai mẫu xét nghiệm", "Tôi đồng ý xét nghiệm quan hệ huyết thống với gia đình kia nhưng yêu cầu lấy mẫu độc lập và có người làm chứng. Kết quả xác nhận tôi là con ruột của họ.", "Gia đình giàu có sợ kết quả giả; mẹ nuôi không muốn tôi rời đi.", "Họ đề nghị tôi gặp cô gái đang được nuôi như con trong nhà họ."),
        ("Cô gái ở vị trí của tôi", "Tôi gặp cô con gái của bà giúp việc đã lớn lên trong gia tộc. Cô ấy phủ nhận, còn cha mẹ ruột tôi lúng túng giữa hai cô con gái.", "Giấy xét nghiệm xác nhận huyết thống nhưng chưa giải thích ai đã tráo hai đứa trẻ.", "Một chi tiết trên vòng sơ sinh không khớp với bệnh viện ghi trong giấy tờ."),
        ("Không ai nhường chỗ", "Tôi đặt ranh giới với gia đình mới và tự tìm hiểu hồ sơ. Cô gái kia có lý do riêng để sợ mất vị trí; một người thân giúp tôi tra lại bệnh viện.", "Hồ sơ chính thức đã bị sửa, khiến hai gia đình nghi ngờ lẫn nhau.", "Tên người ký vào sổ trực năm đó dẫn đến một nhân chứng còn sống."),
        ("Nhân chứng năm ấy", "Tôi gặp người từng trực ca sinh và đối chiếu lời kể với sổ gốc, vòng sơ sinh cùng kết quả xét nghiệm.", "Nhân chứng chỉ nhớ một phần và sợ bị liên lụy.", "Bằng chứng cho thấy vụ tráo đổi không phải nhầm lẫn ngẫu nhiên."),
        ("Lý do bị che giấu", "Tôi lần theo người hưởng lợi từ việc đổi chỗ hai đứa trẻ. Mẹ nuôi kể điều bà biết nhưng phân biệt rõ điều tận mắt chứng kiến với điều chỉ nghe kể.", "Người bị nghi ngờ phủ nhận và đưa ra một bằng chứng phản bác.", "Tôi phát hiện bằng chứng ấy bị làm sai lệch từ một chi tiết đã xuất hiện ở chương trước."),
        ("Đối chất", "Tôi tập hợp hồ sơ bệnh viện, nhân chứng và xét nghiệm độc lập để đối chất với người đứng sau. Cô gái lớn lên trong gia tộc phải tự quyết định sẽ đứng về phía nào.", "Sự thật có thể phá vỡ cả hai gia đình và không ai được miễn trách nhiệm.", "Người gây ra vụ tráo đổi phải công khai chịu hậu quả."),
        ("Sau khi biết sự thật", "Tôi quyết định cách xây dựng quan hệ với cha mẹ ruột, mẹ nuôi và cô gái kia theo kiểu kết đã chọn. Mỗi người thể hiện lựa chọn bằng hành động cụ thể, không thể xóa tổn thương chỉ bằng lời xin lỗi.", "Những năm tháng đã mất không thể lấy lại.", f"Khép lại theo kiểu kết: {story.ending}.") ,
    ]
    return [
        {
            "title": title.format(years=years),
            "beat": beat,
            "obstacle": obstacle,
            "turn": turn,
        }
        for title, beat, obstacle, turn in beats
    ]


def _apply_identity_swap_canon(story: StoryInput, outline: dict) -> dict:
    """Replace model-invented identity facts with the user's fixed family relationships."""
    years = _elapsed_years(story)
    title = str(outline.get("title") or "").strip()
    if not title or any(term in title.casefold() for term in ("hoàng gia", "cổ trang", "lăng viên")):
        outline["title"] = "Thiên Kim Thật Giả"
    outline["premise_anchor"] = (
        f"{story.protagonist} là con ruột gia tộc giàu nhất Bắc Kinh, bị tráo lúc mới sinh với con ruột của bà giúp việc; "
        f"sau {years} năm, hai gia đình mới phát hiện sự thật."
    )
    outline["narrative_pov"] = "ngôi thứ nhất (tôi)"
    outline["setting"] = "Bắc Kinh hiện đại và nơi gia đình bà giúp việc sinh sống"
    outline["characters"] = [
        f"{story.protagonist}: con ruột gia tộc giàu nhất Bắc Kinh, bị tráo lúc mới sinh và lớn lên cùng bà giúp việc.",
        "Con gái ruột của bà giúp việc: bị tráo cùng ngày, lớn lên trong gia tộc giàu có; có mục tiêu và cảm xúc riêng, không mặc định là phản diện.",
        "Bà giúp việc: mẹ nuôi của nhân vật chính, biết một phần sự việc và có lý do riêng để im lặng.",
        "Cha mẹ ruột của nhân vật chính: gia đình giàu có ở Bắc Kinh, cần bằng chứng độc lập trước khi đón nhận sự thật.",
    ]
    outline["chapters"] = _identity_swap_chapters(story)
    outline["hook"] = (
        f"Tôi lớn lên bên người mẹ làm giúp việc; {years} năm sau, xét nghiệm xác nhận tôi mới là con ruột của gia tộc giàu nhất Bắc Kinh. "
        "Cô gái được nuôi thay vị trí tôi lại là con ruột của bà ấy."
    )
    return outline


def _canon_rules(story: StoryInput) -> str:
    """Turn explicit premise constraints into short, deterministic instructions."""
    premise = story.premise.casefold()
    rules = [f"Giữ nguyên ý tưởng gốc: {story.premise.strip() or story.trope}"]
    if "con gái út" in premise or "con út" in premise:
        rules.append("Nhân vật chính là con út; không viết em gái của cô ấy lớn tuổi hơn.")
    if any(term in premise for term in ("tráo", "đánh tráo", "bế nhầm")):
        rules.append("Không đổi ai bị tráo với ai; hai đứa trẻ bị tráo cùng thời điểm phải cùng lứa tuổi.")
    if "giúp việc" in premise:
        rules.append("Giữ đúng mối liên hệ giữa gia đình chính và con của bà giúp việc.")
    if _is_identity_swap_story(story):
        rules.extend([
            "Nhân vật chính là con ruột của gia tộc giàu nhất Bắc Kinh; lúc mới sinh bị tráo với con ruột bà giúp việc.",
            "Nhân vật chính lớn lên trong gia đình người giúp việc; cô gái được nuôi trong gia tộc giàu là con ruột bà giúp việc.",
            "Hai cô gái cùng tuổi; bà giúp việc là mẹ nuôi của nhân vật chính, không phải mẹ ruột.",
            "Đây là gia tộc giàu có hiện đại, không phải hoàng gia/cung đình/cổ trang.",
            "Sự thật cần được chứng minh bằng nhiều manh mối nhất quán; không dùng một cuốn nhật ký làm bằng chứng duy nhất.",
        ])
    if "tôi" in premise:
        rules.append("Kể ngôi thứ nhất; người kể là nhân vật chính, không gọi cô ấy là 'cô' trong lời kể.")
    for number in re.findall(r"\d+", story.premise):
        rules.append(f"Không bỏ hoặc đổi mốc số {number} đã nêu.")
    return "\n".join(f"- {rule}" for rule in rules)


def _read_checkpoint(path: Path | None, story: StoryInput) -> tuple[dict | None, list[str], list[str]]:
    if not path or not path.is_file():
        return None, [], []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("input") != story.model_dump(mode="json") or payload.get("complete"):
            return None, [], []
        outline = payload.get("outline")
        chapters = payload.get("chapters")
        recaps = payload.get("recaps")
        if isinstance(outline, dict) and isinstance(chapters, list) and isinstance(recaps, list):
            logger.info("Resuming story draft from chapter %d", len(chapters) + 1)
            return outline, [str(item) for item in chapters], [str(item) for item in recaps]
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        logger.warning("Ignoring unreadable story checkpoint: %s", exc)
    return None, [], []


def _write_checkpoint(
    path: Path | None,
    story: StoryInput,
    outline: dict,
    chapters: list[str],
    recaps: list[str],
    *,
    complete: bool = False,
) -> None:
    if not path:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    payload = {
        "input": story.model_dump(mode="json"),
        "outline": outline,
        "chapters": chapters,
        "recaps": recaps,
        "complete": complete,
    }
    temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def _ensure_ollama_model(client: OllamaClient) -> None:
    if settings.llm_provider.value == "fallback" or not client.is_available():
        raise LLMUnavailableError(
            "Truyện dài 15–20 phút cần Ollama chạy trong Docker và model qwen2.5:7b. "
            "Cài model bằng: docker compose exec ollama ollama pull qwen2.5:7b"
        )
    try:
        models = client.list_models()
    except LLMUnavailableError as exc:
        raise LLMUnavailableError(
            "Không kiểm tra được model Ollama. Hãy chạy: docker compose exec ollama ollama pull qwen2.5:7b"
        ) from exc
    if client.model not in models:
        raise LLMUnavailableError(
            f"Ollama chưa có model {client.model}. Cài bằng: docker compose exec ollama ollama pull {client.model}"
        )


def _story_outline(client: OllamaClient, story: StoryInput) -> dict:
    premise = story.premise.strip() or (
        f"Hãy tự sáng tác một cốt truyện mới theo mô-típ {story.trope}, "
        f"với nhân vật chính {story.protagonist}."
    )
    prompt = _OUTLINE_PROMPT.format(
        duration_minutes=story.duration_seconds // 60,
        trope=story.trope,
        premise=premise,
        canon_rules=_canon_rules(story),
        blueprint=_story_blueprint(story),
        protagonist=story.protagonist,
        tone=story.tone,
        ending=story.ending,
    )
    outline = client.generate_json(_SYSTEM, prompt, temperature=0.45)
    chapters = outline.get("chapters")
    if not outline.get("title") or not outline.get("premise_anchor") or not isinstance(chapters, list) or len(chapters) != 8:
        raise LLMError("AI chưa lập được dàn ý 8 chương đầy đủ; hãy tạo lại.")
    if not isinstance(outline.get("characters"), list) or not outline["characters"]:
        raise LLMError("Dàn ý thiếu hồ sơ nhân vật; hãy tạo lại để tránh nhầm quan hệ.")
    for index, chapter in enumerate(chapters, start=1):
        if not isinstance(chapter, dict) or not chapter.get("beat") or not chapter.get("turn"):
            raise LLMError(f"Dàn ý chương {index} thiếu diễn biến hoặc bước ngoặt; hãy tạo lại.")
        chapter.setdefault("obstacle", "")
    outline.setdefault("narrative_pov", "ngôi thứ nhất" if "tôi" in story.premise.casefold() else "ngôi thứ ba giới hạn")
    outline.setdefault("setting", "bối cảnh theo ý tưởng gốc")
    if "tôi" in story.premise.casefold():
        outline["narrative_pov"] = "ngôi thứ nhất (tôi)"
        hook = str(outline.get("hook") or "").strip()
        if not _is_identity_swap_story(story) and not hook.casefold().startswith("tôi "):
            outline["hook"] = ""
    if _is_identity_swap_story(story):
        outline = _apply_identity_swap_canon(story, outline)

    # Reject an outline that ignores the user's central idea.
    premise_words = {
        word.lower()
        for word in re.findall(r"[A-Za-zÀ-ỹ0-9]+", story.premise)
        if len(word) >= 4
    }
    anchor_words = {
        word.lower()
        for word in re.findall(r"[A-Za-zÀ-ỹ0-9]+", str(outline["premise_anchor"]))
        if len(word) >= 4
    }
    meaningful = premise_words - {"được", "trong", "người", "mình", "của", "những", "đang"}
    overlap = len(meaningful & anchor_words)
    required_overlap = 2 if len(meaningful) >= 5 else 1
    if meaningful and overlap < required_overlap:
        raise LLMError("Dàn ý chưa bám vào ý tưởng bạn nhập. Hãy nhấn tạo lại.")
    plan_text = json.dumps(outline, ensure_ascii=False).casefold()
    premise_lower = story.premise.casefold()
    missing_facts: list[str] = []
    if "bắc kinh" in premise_lower and "bắc kinh" not in plan_text:
        missing_facts.append("địa điểm Bắc Kinh")
    if "giúp việc" in premise_lower and not any(term in plan_text for term in ("giúp việc", "người hầu", "nữ hầu")):
        missing_facts.append("người mẹ/con của bà giúp việc")
    if any(term in premise_lower for term in ("tráo", "đánh tráo", "bế nhầm")) and not any(
        term in plan_text for term in ("tráo", "đánh tráo", "bế nhầm", "đổi thân phận")
    ):
        missing_facts.append("biến cố tráo đổi thân phận")
    for number in re.findall(r"\d+", story.premise):
        if number not in plan_text and _NUMBER_WORDS.get(number, "") not in plan_text:
            missing_facts.append(f"mốc {number} năm")
    if missing_facts:
        raise LLMError("Dàn ý làm rơi chi tiết bắt buộc: " + ", ".join(missing_facts) + ". Hãy tạo lại.")
    if "bắc kinh" in premise_lower and not _is_identity_swap_story(story) and any(
        term in plan_text for term in ("hoàng đế", "cung đình", "triều đại", "nhà thanh", "lăng viên")
    ):
        raise LLMError("Dàn ý tự chuyển sang cổ trang, trái với ý tưởng về gia tộc ở Bắc Kinh hiện đại. Hãy tạo lại.")
    return outline


def _opening_alignment_issues(story: StoryInput, text: str) -> list[str]:
    """Catch premise drift in chapter one before spending time on the other chapters."""
    opening = text[:4500].casefold()
    premise = story.premise.casefold()
    issues: list[str] = []
    narration_start = re.sub(r"[\"“].*?[\"”]", "", opening[:700], flags=re.S).lstrip()
    if "tôi" in premise and not re.match(r"tôi\b", narration_start):
        issues.append("câu mở đầu chưa bắt đầu bằng ngôi thứ nhất 'Tôi'")
    if "bắc kinh" in premise and "bắc kinh" not in opening:
        issues.append("bỏ mất địa điểm Bắc Kinh")
    if "giúp việc" in premise and not any(term in opening for term in ("giúp việc", "người hầu", "nữ hầu")):
        issues.append("chưa đưa người mẹ/con bà giúp việc vào truyện")
    if any(term in premise for term in ("tráo", "đánh tráo", "bế nhầm")) and not any(
        term in opening for term in ("tráo", "đánh tráo", "bế nhầm", "đổi thân phận")
    ):
        issues.append("chưa bám biến cố tráo đổi thân phận")
    for number in re.findall(r"\d+", premise):
        if number not in opening and _NUMBER_WORDS.get(number, "") not in opening:
            issues.append(f"bỏ mốc {number} năm")
    if re.search(r"con gái út|con út", premise) and re.search(
        r"em gái.{0,35}(?:lớn hơn|lớn tuổi hơn|chị cả)|(?:lớn hơn|lớn tuổi hơn).{0,35}em gái", opening
    ):
        issues.append("mâu thuẫn thứ tự chị em: nhân vật út nhưng lại có em gái lớn tuổi hơn")
    if _is_identity_swap_story(story):
        if "hoàng gia" in opening:
            issues.append("nhầm gia tộc giàu có thành hoàng gia")
        if re.search(r"(?:tôi|mình).{0,90}(?:lớn lên|được nuôi|sống).{0,70}(?:biệt thự|phủ gia tộc)", opening):
            issues.append("nhân vật chính bị viết thành đã lớn lên trong biệt thự gia tộc giàu")
        if re.search(r"(?:tôi|mình).{0,50}(?:con gái|con ruột|mẹ ruột).{0,50}(?:bà|mẹ).{0,20}giúp việc", opening):
            issues.append("đảo ngược mẹ ruột và mẹ nuôi")
    return issues


def _insert_missing_time_anchor(story: StoryInput, text: str, issues: list[str]) -> str:
    """Preserve a user-specified elapsed-years fact when the model omitted it."""
    time_issues = [re.search(r"bỏ mốc (\d+) năm", issue) for issue in issues]
    numbers = [match.group(1) for match in time_issues if match]
    if not numbers or any(not re.search(rf"\b{number}\s+năm\b", story.premise.casefold()) for number in numbers):
        return text
    anchors = []
    for number in numbers:
        years = _NUMBER_WORDS.get(number, number)
        anchors.append(f"{years.capitalize()} năm sau, gia đình mới phát hiện sự thật về thân phận của tôi.")
    logger.info("Inserted user-provided elapsed-time fact into story opening: %s years", ", ".join(numbers))
    return " ".join(anchors) + "\n\n" + text


def _narration_only(client: OllamaClient, prompt: str) -> str:
    """Generate/repair prose without JSON, which small models often corrupt."""
    messages = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": prompt + "\n\nChỉ viết tiếng Việt. Không JSON, không markdown, không tiêu đề chương."},
    ]
    text = client.chat(messages, temperature=0.78, max_tokens=2048).strip()
    fence = chr(96) * 3
    if text.startswith(fence):
        text = "\n".join(line for line in text.splitlines() if not line.strip().startswith(fence)).strip()
    if _CJK_RE.search(text):
        repair_messages = [
            {"role": "system", "content": _SYSTEM},
            {
                "role": "user",
                "content": (
                    "Viết lại đoạn dưới thành lời kể tự nhiên hoàn toàn bằng tiếng Việt. "
                    "Dịch hoặc thay mọi ký tự/từ tiếng Trung và ngoại ngữ; giữ nguyên cốt truyện, "
                    "không thêm tình tiết mới. Chỉ trả đoạn văn đã sửa:\n\n" + text
                ),
            },
        ]
        text = client.chat(repair_messages, temperature=0.45, max_tokens=2048).strip()
    if _CJK_RE.search(text):
        text = _remove_foreign_sentences(text)
    text = _clean_narration(text)
    if not text:
        raise LLMError("Model không trả nội dung truyện.")
    return text


def _write_chapter(
    client: OllamaClient,
    story: StoryInput,
    outline: dict,
    chapter_number: int,
    previous: list[str],
    min_units: int,
    max_units: int,
) -> tuple[str, str]:
    prompt = _CHAPTER_PROMPT.format(
        chapter_number=chapter_number,
        min_units=min_units,
        max_units=max_units,
        premise=story.premise.strip() or outline["premise_anchor"],
        canon_rules=_canon_rules(story),
        blueprint=_story_blueprint(story),
        premise_anchor=outline["premise_anchor"],
        trope=story.trope,
        protagonist=story.protagonist,
        tone=story.tone,
        ending=story.ending,
        title=outline["title"],
        narrative_pov=outline.get("narrative_pov", "ngôi thứ nhất"),
        setting=outline.get("setting", "bối cảnh theo ý tưởng gốc"),
        characters="\n".join(f"- {item}" for item in outline.get("characters", [])),
        outline="\n".join(
            f"{index}. {item.get('title', '')}: {item.get('beat', '')} "
            f"(trở ngại: {item.get('obstacle', '')}; chuyển: {item.get('turn', '')})"
            for index, item in enumerate(outline["chapters"], start=1)
        ),
        previous="\n".join(previous[-4:]) or "chưa có",
        chapter=json.dumps(outline["chapters"][chapter_number - 1], ensure_ascii=False),
    )
    text = _narration_only(client, prompt)
    if chapter_number == 1:
        issues = _opening_alignment_issues(story, text)
        if issues and all(re.fullmatch(r"bỏ mốc \d+ năm", issue) for issue in issues):
            text = _insert_missing_time_anchor(story, text, issues)
            issues = _opening_alignment_issues(story, text)
        if issues:
            correction_prompt = f"""BẢN VỪA VIẾT KHÔNG ĐẠT vì: {'; '.join(issues)}.
Viết lại hoàn toàn chương 1, không tiếp tục hay biên tập bản cũ. Sổ canon bắt buộc:
{story.premise}
Nhân vật chính: {story.protagonist}. Ngôi kể bắt buộc: {outline.get('narrative_pov')}.
Quy tắc canon:
{_canon_rules(story)}
Bối cảnh và hồ sơ nhân vật:
{outline.get('setting')}\n{chr(10).join(f'- {item}' for item in outline.get('characters', []))}
Mở đầu phải chứa đúng chi tiết người dùng đã đưa; không tự thay gia đình, quan hệ, địa điểm,
tuổi hay biến cố. Viết thành truyện kể có hành động cụ thể, không tóm tắt.
Chỉ trả chương truyện bằng tiếng Việt, không lời dẫn hoặc nhận xét.
"""
            text = _narration_only(client, correction_prompt)
            issues = _opening_alignment_issues(story, text)
            if issues:
                raise LLMError(
                    "Model vẫn không giữ đúng ý tưởng ở đoạn mở đầu ("
                    + "; ".join(issues)
                    + "). App đã dừng sớm để không bắt bạn chờ viết cả truyện sai hướng."
                )
    recap = text[-500:]

    # Smaller local models often stop a chapter early despite the requested
    # length. Continue from the final beat instead of discarding/restarting it.
    for attempt in range(3):
        current_units = len(text.split())
        if current_units >= min_units:
            return text, recap or text[-500:]
        deficit = min_units - current_units
        continuation_prompt = f"""Tiếp tục chương {chapter_number} của truyện dưới đây.

Ý tưởng gốc: {story.premise.strip() or outline['premise_anchor']}
Mô-típ: {story.trope}
Nhân vật chính: {story.protagonist}
Dàn ý chương: {json.dumps(outline['chapters'][chapter_number - 1], ensure_ascii=False)}
Ngôi kể: {outline.get('narrative_pov', 'ngôi thứ nhất')}. Bối cảnh: {outline.get('setting', '')}.
Nhân vật và quan hệ cố định:
{chr(10).join(f'- {item}' for item in outline.get('characters', []))}
Đoạn cuối hiện tại:
{text[-1800:]}

Chương hiện có {current_units} tiếng; cần bổ sung khoảng {deficit + 25} tiếng để đạt tối thiểu {min_units}.
Viết tiếp liền sau câu cuối, thêm diễn biến/hội thoại/phản ứng nhân vật, không nhắc lại đoạn cũ,
không giải quyết tình tiết ngoài dàn ý. Giữ đúng ngôi kể, thời đại và quan hệ nhân vật.
Mỗi câu mới phải có thông tin/hành động/phản ứng mới; không kéo dài bằng câu đệm hoặc lặp ý.
Chỉ trả phần truyện tiếp nối bằng tiếng Việt, không JSON, không markdown, không nhãn chương.
"""
        addition = _narration_only(client, continuation_prompt)
        added_units = len(addition.split())
        if added_units:
            text = f"{text}\n\n{addition}"
        else:
            logger.warning("Story chapter %d continuation attempt %d returned no text", chapter_number, attempt + 1)

    current_units = len(text.split())
    if current_units < min_units:
        raise LLMError(
            f"Chương {chapter_number} hiện có {current_units} tiếng, chưa đạt mốc {min_units} sau khi thử viết tiếp."
        )
    return text, recap or text[-500:]


def generate_story(
    story: StoryInput,
    client: OllamaClient | None = None,
    progress_callback: Callable[[float, str], None] | None = None,
    checkpoint_path: Path | None = None,
) -> StoryPackage:
    """Plan then write a long story in sequential chapters for continuity."""
    use_client = client or get_ollama_client()
    if progress_callback:
        progress_callback(0.03, "Kiểm tra model viết truyện...")
    _ensure_ollama_model(use_client)
    outline, chapters, recaps = _read_checkpoint(checkpoint_path, story)
    if not outline:
        if progress_callback:
            progress_callback(0.08, "Lập dàn ý bám theo ý tưởng...")
        outline = _story_outline(use_client, story)
        _write_checkpoint(checkpoint_path, story, outline, chapters, recaps)

    # Aim for a realistic narration word count, while keeping each chapter readable.
    target_units = round(story.duration_seconds / 60 * 165)
    min_units = max(240, round(target_units / 8 * 0.99))
    max_units = round(target_units / 8 * 1.15)
    for chapter_number in range(len(chapters) + 1, 9):
        if progress_callback:
            progress_callback(
                0.1 + 0.78 * (chapter_number - 1) / 8,
                f"Đang viết chương {chapter_number}/8...",
            )
        chapter_text, recap = _write_chapter(
            use_client,
            story,
            outline,
            chapter_number,
            recaps,
            min_units,
            max_units,
        )
        chapters.append(chapter_text)
        recaps.append(recap)
        _write_checkpoint(checkpoint_path, story, outline, chapters, recaps)
        if progress_callback:
            progress_callback(
                0.1 + 0.78 * chapter_number / 8,
                f"Đã viết xong chương {chapter_number}/8...",
            )

    full_script = "\n\n".join(chapters)
    hook = str(outline.get("hook") or "").strip()
    if hook and hook.casefold() not in full_script[:500].casefold():
        full_script = f"{hook}\n\n{full_script}"
    full_script = _clean_narration(full_script)
    spoken_units = len(full_script.split())
    if spoken_units < target_units * 0.95:
        raise LLMError(
            f"Truyện chỉ đạt khoảng {spoken_units} tiếng, thấp hơn độ dài yêu cầu. Hãy tạo lại để đạt tối thiểu 15 phút."
        )

    _write_checkpoint(checkpoint_path, story, outline, chapters, recaps, complete=True)
    if progress_callback:
        progress_callback(0.9, "Hoàn tất truyện; chuẩn bị tạo giọng đọc...")
    caption = f"{outline['title']} — một bí mật sẽ thay đổi tất cả."
    return StoryPackage(
        title=str(outline["title"]).strip(),
        hook=hook,
        full_script=full_script,
        caption=caption,
        hashtags=["#TruyenDai", "#TruyenHuCau", "#KeChuyen", "#TikTokStory", "#YouTubeStory"],
        generation_mode="ollama",
        spoken_units=spoken_units,
    )
