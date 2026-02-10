"""
Entity Registry - Dynamic extraction of persons, places, keywords from Vietnamese history text.

Uses regex patterns and NLP heuristics to extract entities dynamically from text,
rather than relying on hardcoded static lists. Reference patterns derived from
storyteller.py but implemented as dynamic extraction functions.
"""
import re
from functools import lru_cache

# ========================
# REGEX PATTERNS (Dynamic)
# ========================

# Vietnamese person name pattern: 2-5 capitalized words
# Matches: "Nguyễn Huệ", "Trần Hưng Đạo", "Hồ Chí Minh"
PERSON_PATTERN = re.compile(
    r"\b("
    r"(?:[A-ZĐÂÊÔƯÀÁẢÃẠÈÉẺẼẸÌÍỈĨỊÒÓỎÕỌÙÚỦŨỤỲÝỶỸỴ]"
    r"[a-zà-ỹ]*\s+){1,4}"
    r"[A-ZĐÂÊÔƯÀÁẢÃẠÈÉẺẼẸÌÍỈĨỊÒÓỎÕỌÙÚỦŨỤỲÝỶỸỴ]"
    r"[a-zà-ỹ]*"
    r")\b"
)

# Geographic entity pattern: "tỉnh X", "thành phố X", "sông X", etc.
# Does NOT use IGNORECASE to avoid matching lowercase "thành" in middle of text
GEO_PREFIX_PATTERN = re.compile(
    r"(?:[Tt]ỉnh|[Tt]hành phố|[Hh]uyện|[Đđ]ảo|[Qq]uần đảo|[Ss]ông|[Nn]úi|"
    r"[Đđ]èo|[Cc]ửa|[Vv]ịnh|[Bb]iển|[Vv]ùng|[Kk]inh đô|[Pp]hủ|[Ll]àng|[Xx]ã|[Qq]uận)\s+"
    r"([A-ZĐÂÊÔƯÀÁẢÃẠÈÉẺẼẸÌÍỈĨỊÒÓỎÕỌÙÚỦŨỤỲÝỶỸỴ][a-zà-ỹ]+"
    r"(?:\s+[A-ZĐÂÊÔƯÀÁẢÃẠÈÉẺẼẸÌÍỈĨỊÒÓỎÕỌÙÚỦŨỤỲÝỶỸỴ][a-zà-ỹ]+){0,3})"
)

# Vietnamese conjunctions/prepositions that should stop place name capture
STOP_WORDS_FOR_NAMES = {"và", "của", "với", "trong", "từ", "tại", "đến", "hay", "hoặc", "cùng", "cho"}

# Year patterns
YEAR_WITH_CONTEXT = re.compile(r"(?:năm|Năm)\s+(\d{3,4})")
YEAR_STANDALONE = re.compile(r"(?<!\d)([1-9]\d{2,3})(?!\d)")
ANNIVERSARY_PATTERN = re.compile(
    r"(?:kỉ niệm|kỷ niệm)\s+(\d+)\s+năm", re.IGNORECASE
)

# Dynasty detection from text context
DYNASTY_PATTERNS = [
    (r"\bnhà?\s+Lý\b", "Lý"),
    (r"\bnhà?\s+Trần\b", "Trần"),
    (r"\bnhà?\s+Lê\b", "Lê"),
    (r"\bnhà?\s+Nguyễn\b", "Nguyễn"),
    (r"\bnhà?\s+Mạc\b", "Mạc"),
    (r"\bnhà?\s+Hồ\b", "Hồ"),
    (r"\bnhà?\s+Đinh\b", "Đinh"),
    (r"\bnhà?\s+Tiền Lê\b", "Tiền Lê"),
    (r"\bTây Sơn\b", "Tây Sơn"),
    (r"\bBắc thuộc\b", "Bắc thuộc"),
    (r"\bHùng Vương\b", "Hùng Vương"),
]

# ========================
# DENY LISTS (for filtering false positives)
# These are patterns, not static entity names
# ========================

# Patterns that look like person names but are NOT persons
NOT_PERSON_PREFIXES = (
    "nhà ", "triều ", "quân ", "nghĩa quân ", "đội ",
    "đảng ", "mặt trận ", "công ty ", "tập đoàn ", "thời ",
)
NOT_PERSON_SUFFIXES = (" triều", " quân", " tộc")

NOT_PERSON_KEYWORDS = {
    "chiến dịch", "khởi nghĩa", "phong trào", "hiệp định",
    "tuyên ngôn", "trận", "đại phá", "bản đồ", "tác phẩm",
    "hiến pháp", "luật", "sắc lệnh", "bình ngô",
}

# Known collective/place terms that regex might catch as person names
COLLECTIVE_TERMS = {
    "nhân dân", "quân đội", "triều đình", "thực dân", "đế quốc",
    "phát xít", "nghĩa quân", "quân dân", "chính phủ", "quốc hội",
}

# Known place names that regex might catch as person names
# These are dynamically checked against text context
KNOWN_PLACE_PATTERNS = {
    "thăng long", "đại việt", "đại nam", "đại cồ việt",
    "bạch đằng", "chi lăng", "đống đa", "điện biên phủ",
    "ba đình", "tây sơn", "lam sơn", "đông đô",
    "hoa lư", "tháng tám", "bình ngô",
}

# ========================
# PERSON ALIAS MAPPING (common historical aliases)
# Used to normalize different names for same person
# ========================
PERSON_ALIASES = {
    "quang trung": "Nguyễn Huệ",
    "bắc bình vương": "Nguyễn Huệ",
    "gia long": "Nguyễn Ánh",
    "lý công uẩn": "Lý Thái Tổ",
    "nguyễn tất thành": "Hồ Chí Minh",
    "nguyễn ái quốc": "Hồ Chí Minh",
    "bác hồ": "Hồ Chí Minh",
}


# ========================
# DYNAMIC EXTRACTION FUNCTIONS
# ========================

@lru_cache(maxsize=4096)
def is_valid_person(name: str) -> bool:
    """Dynamically validate if a string is likely a Vietnamese person name."""
    if not name or len(name.strip()) < 4:
        return False

    name_low = name.strip().lower()

    # Reject collective/organizational terms
    if name_low in COLLECTIVE_TERMS:
        return False

    # Reject if it's a known place name
    if name_low in KNOWN_PLACE_PATTERNS:
        return False

    # Reject if starts/ends with non-person indicators
    if any(name_low.startswith(p) for p in NOT_PERSON_PREFIXES):
        return False
    if any(name_low.endswith(s) for s in NOT_PERSON_SUFFIXES):
        return False

    # Reject if contains event/artifact keywords
    if any(k in name_low for k in NOT_PERSON_KEYWORDS):
        return False

    # Vietnamese person names: 2-5 words, each capitalized
    words = name.strip().split()
    if len(words) < 2 or len(words) > 5:
        return False

    return True


def normalize_person(name: str) -> str:
    """Normalize person name using alias mapping."""
    if not name:
        return ""
    name_low = name.strip().lower()
    return PERSON_ALIASES.get(name_low, name.strip())


def extract_persons(text: str) -> list[str]:
    """
    Dynamically extract person names from Vietnamese text using regex.
    Uses capitalization patterns and context clues.
    """
    if not text:
        return []

    persons = set()

    for m in PERSON_PATTERN.finditer(text):
        raw = m.group(1).strip()

        # Skip if in non-person context
        prefix_start = max(0, m.start() - 20)
        prefix_context = text[prefix_start:m.start()].lower()
        if any(ex in prefix_context for ex in ("tỉnh", "thành phố", "huyện", "sông", "núi")):
            continue

        name = normalize_person(raw)
        if is_valid_person(name):
            persons.add(name)

    return sorted(persons)


def _trim_at_stopword(name: str) -> str:
    """Trim a captured name at the first Vietnamese conjunction/preposition."""
    words = name.split()
    result = []
    for w in words:
        if w.lower() in STOP_WORDS_FOR_NAMES:
            break
        result.append(w)
    return " ".join(result)


def extract_places(text: str) -> list[str]:
    """
    Dynamically extract place names from Vietnamese text.
    Uses geo-prefix patterns ("tỉnh X", "sông X") and known place context.
    """
    if not text:
        return []

    places = set()

    # Pattern 1: Explicit geo-prefix ("tỉnh Thanh Hóa", "sông Bạch Đằng")
    for m in GEO_PREFIX_PATTERN.finditer(text):
        raw_place = m.group(1).strip()
        place = _trim_at_stopword(raw_place)
        if len(place) > 2:
            places.add(place)

    # Pattern 2: Context-based ("trận X", "chiến thắng X")
    battle_pattern = re.compile(
        r"(?:trận|chiến thắng|chiến dịch|khởi nghĩa)\s+"
        r"([A-ZĐÂÊÔƯÀÁẢÃẠÈÉẺẼẸÌÍỈĨỊÒÓỎÕỌÙÚỦŨỤỲÝỶỸỴ][a-zà-ỹ]+"
        r"(?:\s+[A-ZĐÂÊÔƯÀÁẢÃẠÈÉẺẼẸÌÍỈĨỊÒÓỎÕỌÙÚỦŨỤỲÝỶỸỴ][a-zà-ỹ]+){0,3})"
    )
    for m in battle_pattern.finditer(text):
        raw = m.group(1).strip()
        candidate = _trim_at_stopword(raw)
        if len(candidate) > 2:
            places.add(candidate)

    # Pattern 3: Detect known places mentioned in text
    for place_low in KNOWN_PLACE_PATTERNS:
        # Search case-insensitively in text
        pattern = re.compile(re.escape(place_low), re.IGNORECASE)
        m = pattern.search(text)
        if m:
            # Use the actual casing from text
            places.add(m.group(0))

    return sorted(places)


def extract_year_smart(text: str) -> int:
    """
    Smart year extraction that handles edge cases:
    - "kỷ niệm 1000 năm Thăng Long" → find the actual year (2010), not 1000
    - "năm 1945" → 1945
    - Avoids capturing troop counts, quantities
    """
    if not text:
        return 0

    # Step 1: Remove anniversary patterns to avoid capturing
    # "kỷ niệm 1000 năm" → the "1000" is NOT the event year
    text_clean = ANNIVERSARY_PATTERN.sub("", text)

    # Step 2: Try explicit "năm XXXX" patterns first
    m = YEAR_WITH_CONTEXT.search(text_clean)
    if m:
        year = int(m.group(1))
        if 40 <= year <= 2025:
            return year

    # Step 3: Find standalone year numbers
    for m in YEAR_STANDALONE.finditer(text_clean):
        year = int(m.group(1))
        if 40 <= year <= 2025:
            # Verify it's not a quantity (check preceding context)
            pos = m.start()
            if pos > 0:
                prefix = text_clean[max(0, pos-15):pos].lower()
                if any(k in prefix for k in ("vạn", "nghìn", "binh", "chiến sĩ", "chiến thuyền", "quân")):
                    continue
            return year

    return 0


def extract_dynasty(text: str, year: int = 0) -> str:
    """Dynamically detect dynasty from text context or year."""
    if not text:
        return ""

    text_check = text.lower()

    # Pattern matching from text
    for pattern, dynasty in DYNASTY_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return dynasty

    # Fallback: infer from year using historical periods
    if year > 0:
        periods = [
            (None, 179, "Hùng Vương / An Dương Vương"),
            (179, 938, "Bắc thuộc"),
            (939, 967, "Ngô"),
            (968, 980, "Đinh"),
            (980, 1009, "Tiền Lê"),
            (1009, 1225, "Lý"),
            (1225, 1400, "Trần"),
            (1400, 1407, "Hồ"),
            (1407, 1427, "Minh thuộc"),
            (1428, 1527, "Lê sơ"),
            (1527, 1592, "Mạc"),
            (1533, 1789, "Lê trung hưng"),
            (1778, 1802, "Tây Sơn"),
            (1802, 1945, "Nguyễn"),
            (1945, 1976, "Việt Nam DCCH"),
            (1976, 2030, "CHXHCN Việt Nam"),
        ]
        for start, end, dynasty in periods:
            s = start if start is not None else -3000
            if s <= year <= end:
                return dynasty

    return ""


def extract_keywords_smart(text: str, persons: list[str] = None, places: list[str] = None) -> list[str]:
    """
    Extract meaningful keywords from Vietnamese history text.
    Combines NLP-style extraction with domain-specific patterns.
    """
    if not text:
        return []

    keywords = set()
    text_low = text.lower()

    # 1. Domain-specific keyword patterns (dynamic detection from text)
    domain_patterns = {
        # Military
        "chiến thắng": "chiến_thắng",
        "chiến dịch": "chiến_dịch",
        "khởi nghĩa": "khởi_nghĩa",
        "kháng chiến": "kháng_chiến",
        "giải phóng": "giải_phóng",
        "đại phá": "đại_phá",
        "xâm lược": "xâm_lược",
        "phản công": "phản_công",
        "thắng lợi": "thắng_lợi",
        "tiêu diệt": "tiêu_diệt",
        # Political
        "độc lập": "độc_lập",
        "thống nhất": "thống_nhất",
        "cách mạng": "cách_mạng",
        "thành lập": "thành_lập",
        "lên ngôi": "lên_ngôi",
        "dời đô": "dời_đô",
        "đổi quốc hiệu": "đổi_quốc_hiệu",
        # Documents
        "tuyên ngôn": "tuyên_ngôn",
        "hiệp định": "hiệp_định",
        "hiến pháp": "hiến_pháp",
        "hòa ước": "hòa_ước",
        # Culture
        "văn miếu": "văn_miếu",
        "giáo dục": "giáo_dục",
    }

    for phrase, keyword in domain_patterns.items():
        if phrase in text_low:
            keywords.add(keyword)

    # 2. Add persons and places as keywords
    if persons:
        for p in persons[:3]:
            keywords.add(p.lower().replace(" ", "_"))
    if places:
        for p in places[:3]:
            keywords.add(p.lower().replace(" ", "_"))

    # 3. Extract dynasty mentions as keywords
    for pattern, dynasty in DYNASTY_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            keywords.add(f"nhà_{dynasty.lower()}")

    return sorted(keywords)[:10]


def classify_tone(text: str) -> str:
    """Dynamically classify emotional tone of historical text."""
    if not text:
        return "neutral"

    t = text.lower()

    heroic_patterns = [
        "chiến thắng", "lừng lẫy", "đánh bại", "đánh tan",
        "toàn thắng", "giải phóng", "thống nhất", "giành độc lập",
        "tự chủ", "chấm dứt ách", "oanh liệt", "đại phá",
        "vang dội", "hào khí", "thắng lợi",
    ]

    tragic_patterns = [
        "tàn phá", "tổn thất", "mất nước", "bắc thuộc",
        "chia cắt", "áp đặt", "hy sinh", "thất bại",
        "chiếm đóng", "xâm lược", "đau thương", "đô hộ",
    ]

    has_heroic = any(k in t for k in heroic_patterns)
    has_tragic = any(k in t for k in tragic_patterns)

    if has_heroic and has_tragic:
        return "mixed"
    if has_heroic:
        return "heroic"
    if has_tragic:
        return "somber"
    return "neutral"


def classify_nature(text: str) -> list[str]:
    """Dynamically classify the nature/category of a historical event."""
    if not text:
        return ["general"]

    t = text.lower()
    labels = set()

    # Dynamic classification using keyword detection
    category_patterns = {
        "military": [
            "đánh bại", "đại phá", "chiến thắng", "chiến dịch",
            "giải phóng", "xâm lược", "kháng chiến", "trận",
        ],
        "political": [
            "lên ngôi", "xưng vương", "thành lập", "ban hành",
            "hiệp định", "tuyên ngôn", "dời đô", "giành chính quyền",
        ],
        "cultural": [
            "văn miếu", "giáo dục", "văn hóa", "nghệ thuật",
            "xây dựng", "phật giáo", "nho giáo",
        ],
        "economic": [
            "thương cảng", "giao thương", "kinh tế", "thuế",
            "mở cửa", "đổi mới",
        ],
    }

    for category, patterns in category_patterns.items():
        if any(k in t for k in patterns):
            labels.add(category)

    return sorted(labels) if labels else ["general"]
