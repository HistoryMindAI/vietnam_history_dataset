import sys
sys.stdout.reconfigure(encoding="utf-8")

import json
import re
from pathlib import Path
from datasets import load_dataset
import random
from functools import lru_cache
from collections import defaultdict

DATASET_DIR = Path(
    "vietnam_history_dataset/default/0.0.0/3fdbbebc92e755190b4eaeb1522d97a753f0f18a"
)

ARROW_FILES = [
    str(DATASET_DIR / "vietnam-history-1_m-vi-train-00000-of-00002.arrow"),
    str(DATASET_DIR / "vietnam-history-1_m-vi-train-00001-of-00002.arrow"),
]

UNKNOWN_ENTITIES = set()

OUT_PATH = "data/history_timeline.json"

YEAR_ANY = re.compile(
    r"(?:^|\D)(?:năm|Năm)\s*"
    r"([1-9][0-9]{2,3})"
    r"(?![0-9])",
    re.UNICODE
)

DATE_WITH_YEAR = re.compile(
    r"\b([0-3]?\d/[01]?\d/([1-9][0-9]{2,3}))\b"
)

YEAR_INLINE = re.compile(
    r"(?:đầu|giữa|cuối|mùa\s+\w+)?\s*năm\s+([1-9][0-9]{2,3})",
    re.I
)

PERSON_PATTERN = re.compile(
    r"\b(?:Vua\s+)?"
    r"("
        # Nguyễn Huệ, Trần Hưng Đạo...
        r"(?:Nguyễn|Lê|Lý|Trần|Đinh|Hồ|Ngô|Phạm|Phan|Bùi|Đỗ|Vũ|Võ|Hoàng|Huỳnh|Đặng|Dương|Khúc|Mạc)"
        r"(?:\s+[A-ZĐÂÊÔƯ][a-zà-ỹ]+){1,3}"
    r"|"
        # Lý Thái Tổ, Trần Thánh Tông
        r"[A-ZĐÂÊÔƯ][a-zà-ỹ]+"
        r"\s+(?:Thái|Thánh|Nhân)\s+(?:Tổ|Tông)"
    r"|"
        # Miếu hiệu đơn
        r"(?:Quang\s+Trung|Gia\s+Long|Minh\s+Mạng|Tự\s+Đức|Hàm\s+Nghi)"
    r")\b"
)

ROYAL_TITLES = {
    "quang trung",
    "bắc bình vương",
    "gia long",
    "minh mạng",
    "tự đức",
    "thiệu trị",
    "hàm nghi",
}

CANONICAL_PERSON = {
    "quang trung": "Nguyễn Huệ",
    "bắc bình vương": "Nguyễn Huệ",
    "gia long": "Nguyễn Ánh",
    "minh mạng": "Minh Mạng",
    "tự đức": "Tự Đức",
    "thiệu trị": "Thiệu Trị",
    "hàm nghi": "Hàm Nghi",
    "lý công uẩn": "Lý Thái Tổ",
    "vua lý thái tổ": "Lý Thái Tổ",
    "nguyễn tất thành": "Nguyễn Tất Thành",
    "hồ chí minh": "Hồ Chí Minh",
    # Thêm các tên chuẩn để is_valid_person nhận diện
    "nguyễn huệ": "Nguyễn Huệ",
    "nguyễn ánh": "Nguyễn Ánh",
    "lý thái tổ": "Lý Thái Tổ",
}

def normalize_person(name: str) -> str:
    if not name:
        return name
    key = name.strip().lower()
    return CANONICAL_PERSON.get(key, name.strip())

JUNK_PATTERNS = [
    r"Để trả lời\.?",
    r"Nội dung\.?",
    r"Ý nghĩa lịch sử\.?",
    r"Ý nghĩa\.?",
    r"Về lâu dài,?",
    r"Đây là cột mốc quan trọng vì",
    r"Trình bày ngắn gọn, mạch lạc\.?",
    r"Vào\s*,?",
    r"\*\*",
]

BAD_PERSON_KEYWORDS = {
    "Việt Nam", "Đại Việt", "Đại La", "Thăng Long", "Hoa Lư",
    "Điện Biên Phủ", "Tháng Tám", "Bình Ngô", "Chiếu", "Hiệp"
}

def is_real_person(name: str) -> bool:
    if len(name.split()) < 2:
        return False
    for bad in BAD_PERSON_KEYWORDS:
        if bad in name:
            return False
    return True


ACTION_GROUPS = [
    ("đánh tan", "đẩy lui", "đánh bại", "tiêu diệt"),
    ("dựng chính quyền", "khôi phục quyền tự chủ", "giành quyền tự chủ"),
    ("lên ngôi", "xưng vương"),
    ("thống nhất", "dẹp loạn"),
]


INFORMATIVE_VERBS = [
    "đánh", "đánh bại", "đánh tan", "tiêu diệt",
    "dựng", "lập", "xưng", "lên ngôi", "đổi",
    "ký", "ban", "công bố",
    "tấn công", "phòng thủ", "chặn",
    "nhượng", "mất", "rơi vào",
    "thống nhất", "chia cắt",
    "khôi phục", "soán ngôi", "lật đổ", "thành lập",
    "phát động", "hạ", "chiếm", "giữ", "giải phóng",
    "ban bố", "hạ chiếu", "ký kết"
]

STATE_VERBS = [
    "suy yếu", "tan rã", "thất bại",
    "khủng hoảng", "ổn định",
    "phát triển", "rơi vào", "bước vào",
    "mở ra", "chấm dứt", "khẳng định"
]

STOPWORDS = {
    "diễn", "ra", "xảy", "xảy ra", "năm",
    "được", "bị", "là", "và", "ở",
    "sau", "khi", "trước", "trong",
    "tại", "với", "do", "để"
}

STOPWORDS |= {
    "đó", "này", "kia",
    "đã", "sẽ", "cũng",
    "những", "các"
}

VIETNAMESE_SURNAMES = {
    "nguyễn", "lê", "lý", "trần", "đinh", "phạm",
    "vũ", "võ", "hoàng", "huỳnh", "đặng",
    "bùi", "đỗ", "hồ", "ngô", "dương", "phan"
}

VIETNAMESE_SURNAMES |= {
    "khúc",
    "mạc",
    "đinh",
    "hồ",
}


NON_PERSON_PHRASES = {
    "lam sơn", "tây sơn",
    "đại việt", "đại nam", "đại cồ việt",
    "nhà lý", "nhà trần", "nhà lê", "nhà nguyễn",
    "quân thanh", "quân minh",
    "bạch đằng", "ngọc hồi", "đống đa",
    "khởi nghĩa", "kháng chiến", "chiến dịch",
}

NON_PERSON_TOKENS = {
    "sơn", "giang", "đô", "thành",
    "kháng", "trận", "quân",
    "triều", "nước",
    "tống", "minh", "thanh",
    "mông", "cổ"
}

ACTION_HINTS = {
    "đánh", "đánh bại", "đánh tan", "chỉ huy",
    "lãnh đạo", "tiến công", "phản công",
    "dựng", "xưng", "lên ngôi",
    "ban", "ký", "tôn", "chủ động"
}

ACTION_HINTS |= {
    "nhường ngôi",
    "soạn",
    "viết",
    "ban",
    "dựng",
    "lập",
    "chủ trì",
    "khởi xướng",
    "lãnh đạo",
    "ra đi",
}

HEROIC_YEARS = {
    938, 981, 1009, 1010,
    1075, 1077,
    1258, 1285, 1288,
    1418, 1427,
    1471,
    1789,
    1930, 1945,
    1960, 1968, 1972, 1975
}

TRAGIC_YEARS = {1858, 1884, 1955}


HEROIC_YEARS |= {1954}

ENTITY_REGISTRY = {
    "person": set([
        "Nguyễn Tất Thành",
        "Hồ Chí Minh",
        "Hồ Quý Ly",
        "Nguyễn Huệ",
        "Quang Trung",
        "Gia Long",
        "Nguyễn Ánh",
        "Lê Lợi",
        "Trần Hưng Đạo",
        "Ngô Quyền",
    ]),
    "place": set([
        "Thăng Long",
        "Bạch Đằng",
        "Ngọc Hồi",
        "Đống Đa",
        "Điện Biên Phủ",
        "Lam Sơn",
        # ...
    ]),
    "other": set([
        "Đại Việt",
        "Nhà Trần",
        "Quân Thanh",
        "Khởi nghĩa Lam Sơn",
        "Tây Sơn",
        "Đại Ngu"
    ])
}

ENTITY_LOOKUP: dict[str, str] = {}

for kind, names in ENTITY_REGISTRY.items():
    for n in names:
        ENTITY_LOOKUP[n] = kind


def classify_entity(name: str) -> str | None:
    return ENTITY_LOOKUP.get(name)



INVALID_PERSON_HINTS = {
    "quân", "nhà nước", "mặt trận", "đảng",
    "chiến dịch", "tết", "cách mạng",
    "hiệp định", "quốc hiệu",
    "thăng long", "đà nẵng", "sài gòn",
    "đại việt", "đại nam", "đại cồ việt"
}

INVALID_PERSON_PREFIX = {
    "thời", "triều", "nhà", "thời kỳ", "thời kì"
}


def is_valid_person(name: str) -> bool:
    if not name:
        return False

    name = name.strip()
    name_l = name.lower()
    parts = name_l.split()

    # 👑 miếu hiệu → luôn hợp lệ
    if re.search(r"(thái\s+(tổ|tông)|thánh\s+tông|nhân\s+tông)$", name_l):
        return True

    # alias vua hoặc miếu hiệu chuẩn
    if name_l in CANONICAL_PERSON or name_l in ROYAL_TITLES:
        return True

    # tối thiểu 2 token
    if len(parts) < 2:
        return False

    # ❌ prefix không phải người
    if parts[0] in INVALID_PERSON_PREFIX:
        return False

    # ❌ phrase phi nhân
    if name_l in NON_PERSON_PHRASES:
        return False

    # ❌ chứa token phi nhân
    for p in parts:
        if (
            p in NON_PERSON_TOKENS
            or p in INVALID_PERSON_HINTS
        ):
            return False

    # ❌ không có họ Việt → loại
    if parts[0] not in VIETNAMESE_SURNAMES:
        return False

    return True

def normalize_persons(persons: list[str]) -> list[str]:
    result = set()

    for p in persons:
        p2 = canonical_person(p)
        if not is_valid_person(p2):
            continue

        kind = classify_entity(p2)
        if kind and kind != "person":
            continue

        result.add(p2)

    return sorted(result)


def strip_evaluation(text: str) -> str:
    return re.sub(
        r",?\s*(mở ra|khẳng định|đánh dấu|thể hiện)[^,.]*",
        "",
        text,
        flags=re.I
    ).strip(" ,.")

def canonical_person(name: str) -> str:
    if not name:
        return name

    key = name.strip().lower()
    return CANONICAL_PERSON.get(key, name.strip())

def extract_parenthetical_persons(text: str):
    persons = []

    def repl(m):
        content = m.group(1).strip()
        if is_valid_person(content):
            persons.append(canonical_person(content))
            return content  # ⬅️ GIỮ LẠI
        return ""

    clean_text = re.sub(r"\(([^()]{2,50})\)", repl, text)
    return clean_text.strip(), persons

def is_person_actor(text: str, person: str) -> bool:
    """
    PERSON là actor nếu:
    - PERSON đứng gần động từ hành động (trước hoặc sau)
    - hoặc PERSON là alias của nhân vật thực hiện hành động
    """
    t = text.lower()
    p = person.lower()

    # tập alias: Quang Trung ↔ Nguyễn Huệ
    aliases = {p}
    for k, v in CANONICAL_PERSON.items():
        if v.lower() == p.lower():
            aliases.add(k)

    ACTIONS = [
        "đánh", "đánh bại", "đánh tan", "tiến công",
        "chủ động", "dùng", "nhử",
        "lên ngôi", "xưng vương",
        "dựng", "lập", "ban",
        "soạn", "viết",
        "ra đi", "khởi xướng",
        "lãnh đạo", "chỉ huy",
        "soán ngôi", "lật đổ", "thành lập",
        "phát động", "hạ", "chiếm", "giữ"
    ]

    for name in aliases:
        for act in ACTIONS:
            # PERSON trước hoặc sau verb (±40 ký tự)
            if re.search(rf"{name}.{{0,40}}{act}", t):
                return True
            if re.search(rf"{act}.{{0,40}}{name}", t):
                return True

    return False

def is_political_actor(text: str, person: str) -> bool:
    t = text.lower()
    p = person.lower()

    for k in [
        "lên ngôi",
        "nhường ngôi",
        "ban chiếu",
        "xưng vương",
        "trị vì",
        "đổi quốc hiệu",
        "lập nhà",
        "dựng chính quyền",
        "ra đi",
        "soán ngôi",
        "lật đổ",
        "thành lập",
        "hạ chiếu",
        "ban bố",
    ]:
        if re.search(rf"{p}.{{0,40}}{k}|{k}.{{0,40}}{p}", t):
            return True

    return False

def extract_persons_from_body(text: str) -> set[str]:
    all_persons = set(cached_extract_all_persons(text))
    subjects = set()

    # 👑 vua → luôn là subject
    kings = {
        p for p in all_persons
        if re.search(r"(thái\s+(tổ|tông)|thánh\s+tông|nhân\s+tông)$", p.lower())
    }
    if kings:
        return {canonical_person(k) for k in kings}

    for p in all_persons:
        if is_person_actor(text, p) or is_political_actor(text, p):
            subjects.add(canonical_person(p))

    return subjects

def clean_text(text):
    if not text:
        return None

    for p in JUNK_PATTERNS:
        text = re.sub(p, "", text, flags=re.I)

    text = re.sub(
        r"^(Năm\s+[0-9]{3,4}[,:]?\s*)([^.]{0,80}?)(?:diễn ra|xảy ra)\s+",
        r"\1\2",
        text,
        flags=re.I
    )

    text = re.sub(r"2/9/?\s*1945", "ngày 2 tháng 9 năm 1945", text)
    text = re.sub(r"[;:]", ".", text)
    text = re.sub(r"\s+", " ", text)

    sentences = re.split(r"(?<=\.)\s+", text)

    if len(sentences) >= 2 and len(sentences[0]) < 40:
        sentences[0] = sentences[0].rstrip(". ,") + ", " + sentences[1]
        sentences = [sentences[0]] + sentences[2:]

    text = " ".join(sentences[:2])
    text = re.sub(r"đổi\s*mới", "Đổi mới", text, flags=re.I)

    return text.strip(" ,.-") if len(text) >= 50 else None

CORE_ACTIONS = [
    "lên ngôi", "tôn lập", "xưng vương",
    "ban chiếu", "ký hiệp định",
    "đánh bại", "đánh tan", "giành thắng lợi",
    "khởi nghĩa", "kháng chiến",
    "thành lập", "đổi quốc hiệu",
    "giải phóng", "thống nhất"
]

def choose_representative_event(events: list[str]) -> str:
    def score(e: str):
        s = 0
        if any(k in e.lower() for k in ["mở ra", "chấm dứt", "khẳng định"]):
            s += 2
        if any(k in e.lower() for k in CORE_ACTIONS):
            s += 2
        s += len(e) / 100
        return s

    return max(events, key=score)

def extract_all_persons(text: str) -> set[str]:
    persons: set[str] = set()

    if not text:
        return persons

    for m in PERSON_PATTERN.finditer(text):
        raw = m.group(1).strip()
        p = canonical_person(raw)

        # validate hình thức người
        if not is_valid_person(p):
            continue

        # loại nếu entity registry nói KHÔNG phải người
        kind = classify_entity(p)
        if kind and kind != "person":
            continue

        persons.add(p)

    return persons

def resolve_entity(name: str):
    kind = classify_entity(name)
    if kind:
        return kind

    UNKNOWN_ENTITIES.add(name)
    return None


def pick_tone(tones):
    """
    Chọn tone đại diện để kể chuyện.
    Ưu tiên: heroic > tragic > neutral
    """
    if not tones:
        return "neutral"

    if isinstance(tones, (list, set)):
        if "heroic" in tones:
            return "heroic"
        if "tragic" in tones:
            return "tragic"
        return next(iter(tones))

    return tones


def ask_by_person(timeline, name: str):
    name = canonical_person(name)
    results = []

    for year, block in timeline.items():
        for e in block["events"]:
            if any(name.lower() == p.lower() for p in e.get("persons_all", [])):
                subject = infer_subject(
                    e["event"],
                    set(e.get("persons", [])),
                    e["nature"]
                )
                results.append(
                    storyteller(
                        int(year),
                        pick_tone(e["tone"]),
                        e["event"],
                        subject
                    )
                )

    return results or None

def remove_non_informative_clauses(text):
    clauses = [c.strip() for c in text.split(",") if c.strip()]
    kept = []

    for c in clauses:
        # ✅ có PERSON → giữ
        if cached_extract_all_persons(c):
            kept.append(c)
            continue


        lc = c.lower()

        if any(v in lc for v in INFORMATIVE_VERBS + STATE_VERBS):
            kept.append(c)
            continue

        if re.search(
            r"(quân|đô|kinh|sông|thành|hiệp định|quốc hiệu|bài|tác phẩm|cải cách)",
            lc
        ):
            kept.append(c)

    return ", ".join(kept)

def remove_year_phrases(text, year):
    text = re.sub(
        rf"(diễn ra|xảy ra)(?:\s+(?:vào|trong))?\s+năm\s+{year}",
        "",
        text,
        flags=re.I
    )
    return re.sub(r"\s+,", ",", text).strip(" ,.")

def force_person_from_text(event_text: str) -> list[str]:
    forced = []

    FORCE_MAP = {
        "Nguyễn Tất Thành": "Nguyễn Tất Thành",
        "Hồ Chí Minh": "Hồ Chí Minh",
        "Quang Trung": "Nguyễn Huệ",
        "Nguyễn Huệ": "Nguyễn Huệ",
        "Gia Long": "Nguyễn Ánh",
    }

    for k, v in FORCE_MAP.items():
        if k in event_text:
            forced.append(v)

    return forced


def merge_events_by_year(events: list[dict]) -> list[dict]:
    """
    Merge các sự kiện TRÙNG NỘI DUNG trong cùng một năm
    """
    if not events:
        return []

    buckets: dict[str, list[dict]] = defaultdict(list)

    # 1️⃣ Bucket theo chữ ký nội dung
    for e in events:
        sig = event_signature(e["event"])
        buckets[sig].append(e)

    merged_events: list[dict] = []

    # 2️⃣ Merge từng bucket
    for bucket in buckets.values():
        base = {
            "year": bucket[0]["year"],
            "event": choose_representative_event(
                [b["event"] for b in bucket]
            ),
            "persons": sorted(
                set(p for b in bucket for p in b.get("persons", []))
            ),
            "persons_all": sorted(
                set(p for b in bucket for p in b.get("persons_all", []))
            ),
            "nature": sorted(
                set(n for b in bucket for n in b.get("nature", []))
            ),
            "tone": sorted(
                set(t for b in bucket for t in b.get("tone", []))
            ),
            "keywords": sorted(
                set(k for b in bucket for k in b.get("keywords", []))
            ),
        }

        merged_events.append(base)

    return merged_events

def build_year_summary(events):
    tones = set(t for e in events for t in e["tone"])
    natures = set(n for e in events for n in e["nature"])

    if "heroic" in tones and "tragic" in tones:
        return "Một năm mang tính bước ngoặt, vừa ghi dấu thắng lợi lớn vừa để lại hệ quả lịch sử sâu sắc."

    if "heroic" in tones:
        if "military" in natures:
            return "Một năm ghi dấu thắng lợi quân sự quan trọng của dân tộc."
        return "Một năm đánh dấu bước tiến lớn trong tiến trình lịch sử dân tộc."


    if "tragic" in tones:
        return "Một năm đầy biến cố, để lại những tổn thất và chia cắt lịch sử."

    return "Một năm có những chuyển biến quan trọng trong tiến trình lịch sử."

def extract_year(text: str):
    if m := DATE_WITH_YEAR.search(text):
        return m.group(2)

    if m := YEAR_ANY.search(text):
        return m.group(1)

    return None

def purge(text):
    text = re.sub(r"\s+\.", ".", text)
    text = re.sub(r"\.+", ".", text)
    return text.strip(" .,-")

def classify_tone(text: str, year: str | None = None) -> set[str]:
    t = text.lower()
    tones = set()

    heroic = [
        "đánh bại", "đánh tan", "đẩy lui",
        "toàn thắng", "giải phóng",
        "thống nhất", "giành độc lập",
        "tự chủ", "chấm dứt ách",
        "buộc quân", "buộc phải"
    ]
    if any(k in t for k in heroic):
        tones.add("heroic")

    tragic = [
        "bị xâm lược", "mất nước",
        "bắc thuộc", "minh thuộc",
        "chia cắt", "áp đặt",
        "mở đầu cuộc chiến"
    ]

    if any(k in t for k in tragic):
        tones.add("tragic")

    if year:
        y = int(year)
        if y in HEROIC_YEARS:
            tones.add("heroic")
        if y in TRAGIC_YEARS:
            tones.add("tragic")

    return tones or {"neutral"}

def classify_nature(text: str) -> list[str]:
    t = text.lower()
    labels = []

    if any(k in t for k in [
        "khởi nghĩa", "kháng chiến",
        "chiến dịch", "tiến công",
        "phản công", "tấn công",
        "xâm lược", "đánh bại",
        "đánh tan", "đánh lui",
        "chiến thắng", "buộc quân rút"
    ]):
        labels.append("military")

    if any(k in t for k in [
        "lên ngôi", "tôn lập",
        "xưng vương", "dựng chính quyền",
        "thành lập"
    ]):
        labels.append("political")

    if any(k in t for k in [
        "hiệp định", "ký kết",
        "đàm phán"
    ]):
        labels.append("diplomacy")

    if any(k in t for k in [
        "đổi quốc hiệu", "ban chiếu",
        "cải cách"
    ]):
        labels.append("institutional")

    return sorted(set(labels)) if labels else ["general"]

HEROIC_ENDINGS = [
    "Sự kiện này mở ra một chương sử hào hùng của dân tộc.",
    "Chiến công ấy khẳng định ý chí tự chủ và sức sống bền bỉ của người Việt.",
    "Đây là dấu mốc thể hiện bản lĩnh và khát vọng làm chủ vận mệnh dân tộc.",
]

TRAGIC_ENDINGS = [
    "Đó là giai đoạn bi thương, khi đất nước rơi vào thử thách khắc nghiệt.",
    "Biến cố này để lại những mất mát sâu sắc cho vận mệnh dân tộc.",
    "Thời kỳ ấy ghi dấu nỗi đau và những tổn thất nặng nề của đất nước.",
]





def storyteller(year, kind, content, subject=None):
    content = content.rstrip(".")

    if subject:
        content = subject + " " + content[0].lower() + content[1:]

    if kind == "heroic":
        return (
            f"Năm {year}, {content}. "
            f"{random.choice(HEROIC_ENDINGS)}"
        )

    if kind == "tragic":
        return (
            f"Năm {year}, {content}. "
            f"{random.choice(TRAGIC_ENDINGS)}"
        )

    return f"Năm {year}, {content}."


def collapse_year_events(events: list[dict]) -> list[dict]:
    groups = {}

    for e in events:
        sig = event_signature(e["event"])
        groups.setdefault(sig, []).append(e)

    collapsed = []

    for sig, group in groups.items():
        best = max(
            group,
            key=lambda x: (
                len(x["event"]),
                "rời bến" in x["event"],
                "ban" in x["event"],
                "ký" in x["event"],
                "tuyên" in x["event"]
            )
        )
        all_nature = sorted(set(n for g in group for n in g["nature"]))
        all_tone = sorted(set(t for g in group for t in g["tone"]))

        collapsed.append({
            "year": best["year"],
            "event": best["event"],
            "nature": all_nature,
            "tone": all_tone
        })


    return collapsed


def deduplicate_phrases(text):
    parts = re.split(r"[.]", text)
    seen = set()
    result = []

    for p in parts:
        key = re.sub(r"\W+", "", p.lower())
        if key and key not in seen:
            seen.add(key)
            result.append(p.strip())

    return ". ".join(result).strip()

def extract_core_tokens(text: str) -> set:
    cores = set()
    for a in CORE_ACTIONS:
        if a in text.lower():
            cores.add(a)

    names = re.findall(
        r"[a-zà-ỹ]+(?:\s+[a-zà-ỹ]+){1,3}", text.lower()
    )
    cores.update(names[:2])
    return cores

def collapse_fragments(text):
    return re.sub(r"\.\s+([a-zà-ỹ])", r", \1", text, flags=re.I)

def remove_repeated_subject(text):
    parts = re.split(r"\.\s+", text)
    if len(parts) < 2:
        return text

    first = parts[0]
    names = re.findall(
        r"[A-ZĐÂÊÔƯ][a-zà-ỹ]+(?:\s+[A-ZĐÂÊÔƯ][a-zà-ỹ]+)+", first
    )

    for i in range(1, len(parts)):
        for name in names:
            parts[i] = re.sub(rf"^{name}\s*", "", parts[i])

    return ". ".join(parts).strip()

def remove_redundant_actions(text):
    clauses = [c.strip() for c in re.split(r",", text)]
    kept = []
    used_groups = set()

    for clause in clauses:
        lowered = clause.lower()
        matched_group = None

        for i, group in enumerate(ACTION_GROUPS):
            if any(k in lowered for k in group):
                matched_group = i
                break

        if matched_group is not None:
            if matched_group in used_groups:
                continue
            used_groups.add(matched_group)

        kept.append(clause)

    return ", ".join(kept)

def normalize_event_text(text: str) -> set:
    text = text.lower()

    text = re.sub(r"\b(1[0-9]{3})\b", "", text)
    text = re.sub(
        r"(diễn ra|xảy ra|năm|sau khi|được|vào|đã|các)",
        "",
        text
    )
    text = re.sub(r"[^\w\s]", " ", text)

    words = [
        w for w in text.split()
        if w not in STOPWORDS and len(w) > 3
    ]

    return set(words)

def normalize_temporal_clause(text: str) -> str:
    return re.sub(
        r",?\s*Sau khi [^,]+?(?=,|$)",
        "",
        text,
        flags=re.I
    )




def is_same_event(e1: str, e2: str, threshold=0.3) -> bool:
    # 1. So core (chủ thể + hành động)
    c1 = extract_core_tokens(e1)
    c2 = extract_core_tokens(e2)

    if c1 and c2 and len(c1 & c2) >= 2:
        return True


    # 2. Fallback bag-of-words
    s1 = normalize_event_text(e1)
    s2 = normalize_event_text(e2)

    if not s1 or not s2:
        return False

    overlap = len(s1 & s2)
    score = overlap / min(len(s1), len(s2))

    return score >= threshold


def lowercase_after_comma(text):
    return re.sub(
        r",\s+(?![A-ZĐÂÊÔƯ][a-zà-ỹ]+\s+[A-ZĐÂÊÔƯ])([A-ZĐÂÊÔƯ])",
        lambda m: ", " + m.group(1).lower(),
        text
    )


def remove_repeated_subject_inline(text):
    names = re.findall(
        r"[A-ZĐÂÊÔƯ][a-zà-ỹ]+(?:\s+[A-ZĐÂÊÔƯ][a-zà-ỹ]+)+",
        text
    )
    if len(names) < 2:
        return text

    main = names[0]

    text = re.sub(
        rf",\s*{re.escape(main)}\b",
        ",",
        text
    )

    text = re.sub(
        rf",\s*{re.escape(main)}\s+",
        ", ",
        text
    )

    return re.sub(r"\s+,", ",", text)

def normalize_titles(text):
    return re.sub(
        r",\s*(Văn kiện|Tác phẩm|Sự kiện)\s+",
        ", ",
        text,
        flags=re.I
    )

def event_signature(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\b1[0-9]{3}\b", "", text)
    text = re.sub(
        r"(diễn ra|xảy ra|năm|sau khi|được|vua|triều)",
        "",
        text
    )
    text = re.sub(r"[^\w\s]", " ", text)

    tokens = [
        w for w in text.split()
        if w not in STOPWORDS and len(w) > 3
    ]

    return " ".join(tokens[:8])   # ⬅ tăng từ 6 → 8

def extract_keywords(text: str) -> list[str]:
    keywords = set()

    persons = re.findall(
        r"[A-ZĐÂÊÔƯ][a-zà-ỹ]+(?:\s+[A-ZĐÂÊÔƯ][a-zà-ỹ]+){1,3}",
        text
    )

    for p in persons:
        if is_valid_person(p):
            keywords.add(p)
            break

    actions = re.findall(
        r"(đánh bại|đánh tan|lên ngôi|xưng vương|"
        r"khởi nghĩa|kháng chiến|"
        r"ban chiếu|ký hiệp định|"
        r"thành lập|giải phóng|thống nhất)",
        text.lower()
    )

    keywords.update(actions)
    return sorted(keywords)

def merge_events(events: list[str]) -> str:
    clauses = []

    for e in events:
        e = re.sub(r"(diễn ra|xảy ra)", "", e)
        clauses.append(e.strip(" ,."))

    base = max(clauses, key=len)

    for c in clauses:
        if "mở ra" in c or "chấm dứt" in c or "khẳng định" in c:
            if c not in base:
                base += ", " + c

    return purge(base)

def prune_event_sentence(text: str) -> str:
    clauses = [c.strip() for c in text.split(",") if c.strip()]
    if len(clauses) <= 1:
        return text

    kept = []

    # 1️⃣ clause có PERSON
    for c in clauses:
        if cached_extract_all_persons(c):
            kept.append(c)


    # 2️⃣ nếu chưa có → clause có action
    if not kept:
        for c in clauses:
            if any(v in c.lower() for v in INFORMATIVE_VERBS + STATE_VERBS):
                kept.append(c)

    # 3️⃣ giữ hệ quả lịch sử
    for c in clauses:
        if any(k in c.lower() for k in ["mở ra", "chấm dứt", "khẳng định"]):
            if c not in kept:
                kept.append(c)

    return ", ".join(kept or [clauses[0]])


def ask_by_event(timeline, query: str):
    query = query.lower()
    matches = []

    for year, block in timeline.items():
        for e in block["events"]:
            if query in e["event"].lower():
                matches.append((year, e))

    if not matches:
        return None

    year, event = max(matches, key=lambda x: len(x[1]["event"]))
    tone = pick_tone(event.get("tone", []))

    return storyteller(int(year), tone, event["event"])

def scan_by_entity(timeline, entity: str):
    entity = entity.lower()
    results = []

    for year, block in timeline.items():
        for e in block["events"]:
            persons = [p.lower() for p in e.get("persons", [])]
            if any(entity in p for p in persons):
                results.append({
                    "year": int(year),
                    "event": e["event"],
                    "tone": e["tone"],
                    "nature": e["nature"]
                })

    return sorted(results, key=lambda x: x["year"])


def ask_by_year(timeline, year: int):
    block = timeline.get(str(year))
    if not block:
        return f"Không tìm thấy sự kiện nào trong năm {year}."

    results = []
    for e in block["events"]:
        subject = infer_subject(
            e["event"],
            set(e.get("persons", [])),
            e["nature"]
        )
        results.append(
            storyteller(
                year,
                pick_tone(e["tone"]),
                e["event"],
                subject
            )
        )

    return results

def ask(timeline, question: str):
    q = question.strip().lower()

    # 1️⃣ hỏi theo năm
    m = re.search(r"năm\s+([1-9][0-9]{2,3})", q)
    if m:
        return ask_by_year(timeline, int(m.group(1)))

    # 2️⃣ hỏi theo nhân vật
    person = extract_person_query(q)
    person_answer = ask_by_person(timeline, person)
    if person_answer:
        return person_answer

    # 3️⃣ fallback hỏi theo sự kiện
    return ask_by_event(timeline, q)


def load_timeline(path=OUT_PATH):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def narrate_year(timeline, year):
    block = timeline.get(str(year))
    if not block:
        return None

    events = block["events"]

    merged = merge_events([e["event"] for e in events])
    tones = sorted(set(t for e in events for t in e["tone"]))

    return {
        "year": int(year),
        "event": merged,
        "tone": tones
    }

def remove_duplicate_subjects_global(text):
    clauses = [c.strip() for c in text.split(",")]
    if len(clauses) < 2:
        return text

    m = re.match(
        r"^([A-ZĐÂÊÔƯ][a-zà-ỹ]+(?:\s+[A-ZĐÂÊÔƯ][a-zà-ỹ]+)+)\b",
        clauses[0]
    )
    if not m:
        return text

    subject = m.group(1)

    cleaned = [clauses[0]]
    for c in clauses[1:]:
        c = re.sub(rf"^{subject}\s*", "", c)
        cleaned.append(c)

    return ", ".join(cleaned)

def infer_subject(body: str, persons: set, nature: list[str]) -> str | None:
    if persons:
        return next(iter(persons))

    t = body.lower()

    if "military" in nature:
        if "quân dân" in t:
            return "Quân dân Việt Nam"
        if "nghĩa quân" in t:
            return "Nghĩa quân"
        return "Lực lượng đương thời"

    if any(n in nature for n in ["political", "institutional", "diplomacy"]):
        return "Chính quyền đương thời"

    if re.search(r"(chiếu|hiệp định|tuyên ngôn|sắc lệnh)", t):
        return "Văn kiện lịch sử"

    return None

def render_event_with_subject(year, body, subject=None):
    if subject:
        return f"Năm {year}, {subject} {body[0].lower() + body[1:]}."
    return f"Năm {year}, {body}."


def extract_person_query(q: str) -> str | None:
    q = q.lower().strip()

    matches = re.findall(
        r"[a-zà-ỹ]+(?:\s+[a-zà-ỹ]+){1,3}",
        q
    )

    for m in sorted(matches, key=len, reverse=True):
        if m in NON_PERSON_PHRASES:
            continue

        p = canonical_person(m)
        if is_valid_person(p):
            return p

    return None

def fix_common_noun_phrases(text):
    return re.sub(
        r",\s*(Quân|Nghĩa quân|Triều|Chính quyền)\b",
        lambda m: ", " + m.group(1).lower(),
        text
    )

def smooth_actions(text):
    text = re.sub(
        r"(đánh (?:tan|bại|lui)[^,]+),\s*(lãnh đạo[^,]+)",
        r"\2 \1",
        text,
        flags=re.I
    )

    text = re.sub(
        r"(dựng[^,]+),\s*(nắm quyền[^,]+)",
        r"\1, sau đó \2",
        text,
        flags=re.I
    )

    text = re.sub(
        r"(dùng[^,]+),\s*(đánh (?:bại|tan|lui)[^,]+)",
        r"\1 và \2",
        text,
        flags=re.I
    )

    return text

def is_collective_event(nature: list[str], body: str) -> bool:
    # ⛔ nếu text có PERSON → KHÔNG BAO GIỜ collective
    if extract_all_persons(body):
        return False

    t = body.lower()

    if "military" in nature and any(k in t for k in [
        "cách mạng",
        "tổng tiến công",
        "kháng chiến",
        "chiến dịch",
        "toàn thắng",
        "quân dân"
    ]):
        return True

    return False

def extract_implicit_ruler(text: str) -> set[str]:
    persons = set()

    patterns = [
        r"(?:Vua\s+)?([A-ZĐÂÊÔƯ][a-zà-ỹ]+\s+(?:Thái|Thánh|Nhân)\s+(?:Tổ|Tông))",
        r"(?:thời|dưới thời|triều)\s+([A-ZĐÂÊÔƯ][a-zà-ỹ]+\s+(?:Thái|Thánh|Nhân)\s+(?:Tổ|Tông))",
    ]

    for p in patterns:
        for m in re.findall(p, text):
            persons.add(canonical_person(m))

    return persons


@lru_cache(maxsize=100_000)
def cached_extract_all_persons(text: str) -> tuple[str, ...]:
    """
    Cache kết quả extract person theo text
    """
    return tuple(extract_all_persons(text))

def normalize(text: str):

    if not text:
        return None

    if len(text) < 50:
        return None

    # bỏ câu hỏi / chat
    if "?" in text:
        return None

    raw = clean_text(text)
    if not raw:
        return None

    year = extract_year(raw)
    if not year:
        return None

    body_raw = re.sub(
        rf"^Năm\s+{year}[,:.\s-]*",
        "",
        raw,
        flags=re.I
    )

    # ===== PERSON TRƯỚC KHI CẮT =====
    persons_subject = extract_persons_from_body(body_raw)
    persons_all = extract_all_persons(body_raw)


    # sau khi có persons_subject, persons_all
    forced = force_person_from_text(body_raw)
    persons_subject |= set(forced)
    persons_all |= set(forced)


    # 👑 vua ngầm
    implicit = extract_implicit_ruler(body_raw)
    persons_subject |= implicit
    persons_all |= implicit

    # PERSON trong ngoặc
    body, parenthetical_persons = extract_parenthetical_persons(body_raw)
    persons_all |= set(parenthetical_persons)

    # ===== TEXT PIPELINE =====
    body = purge(body)
    body = remove_year_phrases(body, year)
    body = normalize_titles(body)
    body = prune_event_sentence(body)
    body = deduplicate_phrases(body)
    body = normalize_temporal_clause(body)
    body = remove_duplicate_subjects_global(body)
    body = lowercase_after_comma(body)
    body = fix_common_noun_phrases(body)
    body = remove_redundant_actions(body)
    body = remove_non_informative_clauses(body)
    body = collapse_fragments(body)
    body = remove_repeated_subject_inline(body)
    body = remove_repeated_subject(body)

    if len(body) < 30:
        return None

    nature = classify_nature(body)
    tone = classify_tone(body, year)

    body = body[0].upper() + body[1:]

    return year, body, nature, tone, persons_subject, persons_all


def iter_raw(ds):
    for row in ds:
        for m in row.get("messages", []):
            if m.get("role") == "assistant":
                yield m.get("content", "")


def main():
    print("[INFO] Loading dataset...")
    ds = load_dataset("arrow", data_files=ARROW_FILES, split="train")

    timeline: dict[str, list[dict]] = {}

    total_raw = 0
    total_kept = 0

    for line in iter_raw(ds):
        total_raw += 1

        res = normalize(line)
        if not res:
            continue

        year, body, nature, tone, persons_subject, persons_all = res

        timeline.setdefault(year, []).append({
            "year": int(year),
            "event": body,
            "persons": sorted(persons_subject),
            "persons_all": sorted(persons_all),
            "nature": set(nature),
            "tone": tone,
            "keywords": set(extract_keywords(body))
        })

        total_kept += 1

    final_timeline = {}

    for year, events in timeline.items():
        final_timeline[year] = {
            "summary": build_year_summary(events),
            "events": merge_events_by_year(events)
        }

    timeline = final_timeline

    Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(timeline, f, ensure_ascii=False, indent=2)

    print(
        f"[DONE] Raw: {total_raw} | "
        f"Giữ lại: {total_kept} | "
        f"Năm có sự kiện: {len(timeline)}"
    )

if __name__ == "__main__":
    main()

