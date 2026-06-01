from app.services.search_service import (
    semantic_search, scan_by_year, scan_by_year_range,
    detect_dynasty_from_query, detect_place_from_query,
    resolve_query_entities, scan_by_entities,
    scan_by_dynasty_timeline, scan_national_resistance,
    scan_territorial_conflicts, scan_civil_wars, scan_broad_history,
    DYNASTY_ORDER,
)
from app.services.event_aggregator import aggregate_events, normalize_for_dedup
from app.services.answer_postprocessor import deduplicate_answer, canonicalize_year_format, _dedup_intra_line, _is_fuzzy_dup
from app.services.formatters.timeline_formatter import extract_year, format_timeline_entry, enforce_timeline_format
from app.services.query_understanding import (
    rewrite_query, extract_question_intent,
    generate_search_variations,
)
from app.services.cross_encoder_service import (
    filter_and_rank_events,
    validate_answer_relevance,
)
from app.services.nli_validator_service import validate_events_nli
from app.services.intent_classifier import (
    classify_intent, QueryAnalysis, detect_duration_guard,
)
from app.services.answer_synthesis import synthesize_answer
from app.services.semantic_intent import classify_semantic_intent
from app.services.implicit_context import (
    expand_query_with_implicit_context,
    filter_discriminating_keywords,
    is_vietnam_scope_query,
    is_broad_vietnam_query,
    has_resistance_terms,
    NON_DISCRIMINATING_KEYWORDS,
)
# --- Phase 1 / Giai đoạn 11: Protection Layers ---
from app.services.constraint_extractor import ConstraintExtractor
from app.services.answer_validator import AnswerValidator
from app.services.conflict_detector import ConflictDetector
from app.services.guardrails import OutputVerifier
from app.services import confidence_scorer
from app.services import answer_builder
from app.services import answer_formatter
from app.services.rewrite_engine import RewriteEngine
from app.core.config import (
    CONFIDENCE_THRESHOLD, RERANK_WEIGHT, ENTAILMENT_WEIGHT, USE_LLM_REWRITE,
)
from app.core.utils.date_utils import safe_year
from app.services.entity_normalizer import normalize_entity_names
import app.core.startup as startup
import re

# ===================================================================
# HELPER FUNCTIONS FOR ENTITY DETECTION
# ===================================================================

def _looks_like_entity_query(query: str) -> bool:
    """
    Detect if query looks like it's asking about a specific entity
    (person, dynasty, event) even if entity resolution failed.

    Used to prevent hallucination from weak semantic matches.
    """
    q_lower = query.lower()

    # Patterns indicating entity-specific query
    entity_patterns = [
        r"(ai là|là ai|who is|who was)",
        r"(là gì|what is|what was)",
        r"(nào là|which is)",
        r"(vua|vị vua|vị tướng|hoàng đế|anh hùng)",
        r"(bà|ông|chúa|tướng|thái úy)",
        r"(nhà .{1,20})",  # "nhà X", likely dynasty
    ]

    return any(re.search(pattern, q_lower) for pattern in entity_patterns)


# Pre-compile regex for faster matching
YEAR_PATTERN = re.compile(r"(?<![\d-])([1-9][0-9]{1,3})(?!\d)")

# Year range patterns - support multiple formats
YEAR_RANGE_PATTERNS = [
    # "từ năm 40 đến năm 2025"
    re.compile(
        r"(?:từ\s*(?:năm\s*)?|giai\s*đoạn\s*)"
        r"(\d{1,4})"
        r"\s*(?:đến|tới|[-–—])\s*(?:năm\s*)?"
        r"(\d{1,4})",
        re.IGNORECASE
    ),
    # "năm 40 đến 2025"
    re.compile(
        r"năm\s+(\d{1,4})\s+(?:đến|tới|[-–—])\s+(?:năm\s*)?(\d{1,4})",
        re.IGNORECASE
    ),
    # "40-2025", "40 đến 2025"
    re.compile(
        r"\b(\d{1,4})\s*(?:đến|tới|[-–—])\s*(\d{1,4})\b",
        re.IGNORECASE
    ),
    # "from 40 to 2025"
    re.compile(
        r"from\s+(\d{1,4})\s+to\s+(\d{1,4})",
        re.IGNORECASE
    ),
    # "between 40 and 2025"
    re.compile(
        r"between\s+(\d{1,4})\s+and\s+(\d{1,4})",
        re.IGNORECASE
    ),
]


def extract_single_year(text: str):
    """
    Extracts a single year between 40 and 2025 from text.
    """
    m = YEAR_PATTERN.search(text)
    if m:
        year = int(m.group(1))
        if 40 <= year <= 2025:
            return year
    return None


def extract_year_range(text: str):
    """
    Extracts a year range from text with multiple format support.
    
    Supported formats:
    - "từ năm 40 đến năm 2025"
    - "năm 40 đến 2025"
    - "40-2025", "40 đến 2025"
    - "from 40 to 2025"
    - "between 40 and 2025"
    - "giai đoạn 40-2025"
    
    Returns (start_year, end_year) or None.
    """
    for pattern in YEAR_RANGE_PATTERNS:
        m = pattern.search(text)
        if m:
            start = int(m.group(1))
            end = int(m.group(2))
            
            # Validate year range - minimum year is 40 (Hai Bà Trưng)
            if 40 <= start <= 2025 and 40 <= end <= 2025 and start < end:
                return (start, end)
    
    return None


def extract_multiple_years(text: str):
    """
    Extracts multiple distinct years from text.
    Returns list of years if 2+ found, else None.
    E.g.: 'năm 938 và năm 1288' → [938, 1288]
    """
    # First check if this is a year range query (handled separately)
    if extract_year_range(text):
        return None

    matches = YEAR_PATTERN.findall(text)
    years = []
    for m in matches:
        y = int(m)
        if 40 <= y <= 2025 and y not in years:
            years.append(y)
    return sorted(years) if len(years) >= 2 else None


MAX_EVENTS_PER_YEAR = 1
MAX_TOTAL_EVENTS = 5
MAX_TOTAL_EVENTS_DYNASTY = 10  # More results for dynasty-level queries
MAX_TOTAL_EVENTS_RANGE = 15   # More results for year range queries
MAX_TOTAL_EVENTS_ENTITY = 10  # Results for multi-entity queries (person + topic)
MIN_CLEAN_TEXT_LENGTH = 15    # Minimum text length after cleaning (filter metadata noise)

# Relationship patterns — is X related to Y?
RELATIONSHIP_PATTERNS = [
    "là gì của nhau", "có quan hệ gì", "liên quan gì",
    "là ai của", "và .+ là",
    # Unaccented fallbacks for queries without diacritics
    "la gi cua nhau", "co quan he gi", "lien quan gi",
    "la ai cua",
]

# Greeting patterns — casual conversation
GREETING_PATTERNS = [
    # English greetings - EXACT MATCH to avoid false positives
    r'\bhello\b', r'\bhi\b(?!\s+\w)', r'\bhey\b', 
    r'\bgood morning\b', r'\bgood afternoon\b', r'\bgood evening\b',
    r'\bhow are you\b', r'\bwhat\'s up\b', r'\bhow do you do\b', r'\bnice to meet you\b',
    # Vietnamese greetings - EXACT MATCH
    r'\bxin chào\b', r'\bchào bạn\b', r'\bchào\b(?!\s+\w)', 
    r'\bchào buổi sáng\b', r'\bchào buổi chiều\b', 
    r'\bchào buổi tối\b', r'\bbạn khỏe không\b', r'\bbạn có khỏe không\b', r'\bkhỏe không\b',
    r'\bdạo này thế nào\b', r'\bhôm nay thế nào\b', r'\bbạn thế nào\b', r'\bmọi việc thế nào\b',
    r'\brất vui được gặp\b', r'\bhân hạnh\b', r'\bchào mừng\b(?!\s+\w)',
    # Casual Vietnamese
    r'\balo\b', r'\balô\b', r'\bhế lô\b', r'\bhê lô\b', r'\bhê nhô\b', r'\bhê lô bạn\b',
    r'\bchào cậu\b', r'\bchào mừng bạn\b', r'\bchào mừng đến với\b',
]

# Thank you patterns
THANK_PATTERNS = [
    r'\bthank you\b', r'\bthanks\b', r'\bthank\b', r'\bthx\b', r'\bty\b',
    r'\bcảm ơn\b', r'\bcám ơn\b', r'\bthanks bạn\b', r'\bcảm ơn bạn\b', r'\bcảm ơn nhiều\b',
    r'\bcảm ơn bạn nhiều\b', r'\bthanks nhiều\b', r'\bcảm ơn nhé\b', r'\bcảm ơn nha\b',
    r'\bcảm ơn rất nhiều\b', r'\bxin cảm ơn\b',
]

# Goodbye patterns
GOODBYE_PATTERNS = [
    r'\bbye\b', r'\bgoodbye\b', r'\bsee you\b', r'\bsee ya\b', r'\bfarewell\b', r'\btake care\b',
    r'\btạm biệt\b', r'\bchào tạm biệt\b', r'\bhẹn gặp lại\b', r'\bgặp lại\b', r'\bbye bye\b',
    r'\bbái bai\b', r'\btạm biệt nhé\b', r'\bchào nhé\b', r'\bđi đây\b', r'\bđi nhé\b',
]

# Identity patterns — who are you?
IDENTITY_PATTERNS = [
    "who are you", "bạn là ai", "giới thiệu bản thân",
    "what is your name", "tên bạn là gì", "tên của bạn",
    "you are who", "giới thiệu về bạn", "bạn tên gì",
    "hãy giới thiệu", "cho tôi biết về bạn",
]

# Creator patterns — who made you?
CREATOR_PATTERNS = [
    "ai tạo ra", "ai phát triển", "ai xây dựng", "ai làm ra",
    "created by", "made by", "developed by", "built by",
    "tạo ra bạn", "phát triển bạn", "xây dựng bạn",
    "ai tạo bạn", "ai đã tạo", "do ai", "được tạo bởi",
    "tác giả", "nhà phát triển", "developer",
    "được tạo ra thế nào", "tạo ra thế nào", "được tạo thế nào",
]

IDENTITY_RESPONSE = (
    "Xin chào! Tôi là **History Mind AI** — trợ lý lịch sử Việt Nam.\n\n"
    "Tôi được tạo ra với mong muốn giúp bạn khám phá "
    "4.000 năm lịch sử dân tộc một cách dễ dàng và sinh động.\n\n"
    "Bạn có thể hỏi tôi về:\n\n"
    "- Tra cứu sự kiện theo năm, triều đại hoặc nhân vật\n"
    "- Những trận chiến nổi tiếng — Bạch Đằng, Chi Lăng, Điện Biên Phủ\n"
    "- Các triều đại — Lý, Trần, Lê, Nguyễn\n"
    "- So sánh các giai đoạn lịch sử\n\n"
    "Hãy thử đặt câu hỏi, tôi sẵn sàng giúp bạn!"
)

GREETING_RESPONSE = (
    "Xin chào! 👋\n\n"
    "Tôi là **History Mind AI** — trợ lý lịch sử Việt Nam của bạn.\n\n"
    "Tôi có thể giúp bạn khám phá 4.000 năm lịch sử dân tộc. "
    "Hãy thử hỏi tôi về:\n\n"
    "- Các sự kiện lịch sử: *\"Trận Bạch Đằng năm 1288\"*\n"
    "- Nhân vật anh hùng: *\"Ai là Trần Hưng Đạo?\"*\n"
    "- Triều đại: *\"Kể về nhà Trần\"*\n"
    "- So sánh: *\"So sánh nhà Lý và nhà Trần\"*\n\n"
    "Bạn muốn tìm hiểu về điều gì?"
)

THANK_RESPONSE = (
    "Rất vui được giúp bạn! 😊\n\n"
    "Nếu bạn có thêm câu hỏi về lịch sử Việt Nam, "
    "đừng ngại hỏi tôi nhé!"
)

GOODBYE_RESPONSE = (
    "Tạm biệt! 👋\n\n"
    "Hẹn gặp lại bạn. Chúc bạn một ngày tốt lành!\n\n"
    "Nếu cần tìm hiểu thêm về lịch sử Việt Nam, "
    "tôi luôn sẵn sàng giúp đỡ."
)

CREATOR_RESPONSE = (
    "Tôi được xây dựng bởi **Võ Đức Hiếu** (h1eudayne), "
    "một sinh viên đam mê công nghệ AI và lịch sử Việt Nam.\n\n"
    "**Về tác giả**\n\n"
    "- Thiết kế và phát triển toàn bộ hệ thống từ ý tưởng đến sản phẩm\n"
    "- Xây dựng bộ dữ liệu hơn 1.000.000 mẫu lịch sử Việt Nam\n"
    "- Huấn luyện mô hình AI hiểu tiếng Việt tự nhiên\n"
    "- Phát triển giao diện web\n\n"
    "**Công nghệ sử dụng**\n\n"
    "- Tìm kiếm ngữ nghĩa (Semantic Search)\n"
    "- FAISS + Embeddings cho truy vấn vector nhanh\n"
    "- Dữ liệu từ thời Hùng Vương đến hiện đại\n\n"
    "**Liên hệ**\n\n"
    "- GitHub: [h1eudayne](https://github.com/h1eudayne?tab=repositories)\n"
    "- Facebook: [Võ Đức Hiếu](https://www.facebook.com/vo.duc.hieu2005/)\n"
    "- Email: voduchieu42@gmail.com\n"
    "- Phone: 0915106276"
)


def clean_story_text(text: str, year: int | None = None) -> str:
    """
    Clean up story text by removing redundant prefixes and making it a complete sentence.
    Handles various data patterns from the Vietnam history dataset.
    """
    if not text:
        return ""
    
    # Coerce non-string types to string
    if not isinstance(text, str):
        text = str(text)
    
    result = text.strip()
    
    # Phase 0: Strip builder scaffolding (B1./B2./B3. patterns)
    # Data contains "B1. gắn mốc XXXX với Event. B2. nêu ... – "content". B3. kết luận – ..."
    # Extract content from between markers and reconstruct natural sentence
    if re.match(r'^B1\.?\s', result, re.IGNORECASE):
        # Extract content pieces from B1/B2/B3
        parts = []
        # B2 content: the quoted description after B2 pattern
        b2_match = re.search(r'B2\.\s*nêu\s+diễn biến\s+trọng tâm\s*[–—-]\s*["\"]?(.+?)["\"]?\.\s*(?:B3|$)', result, re.IGNORECASE)
        if b2_match:
            parts.append(b2_match.group(1).strip().rstrip('.'))
        # B3 content: conclusion after B3 pattern
        b3_match = re.search(r'B3\.\s*kết luận\s*[–—-]\s*(.+?)$', result, re.IGNORECASE)
        if b3_match:
            conclusion = b3_match.group(1).strip().rstrip('.')
            if conclusion:
                parts.append(conclusion)
        if parts:
            result = '. '.join(parts) + '.'
        else:
            # Fallback: just strip B1/B2/B3 prefixes
            result = re.sub(r'B[123]\.\s*(?:gắn mốc \d+ với|nêu diễn biến trọng tâm\s*[–—-]|kết luận\s*[–—-])\s*', '', result, flags=re.IGNORECASE)
    
    # Phase 0b: Strip "Câu hỏi nhắm tới sự kiện ... Cốt lõi." meta-prompt prefix
    result = re.sub(
        r'^Câu hỏi nhắm tới sự kiện\s+.+?\.\s*Cốt lõi\.\s*',
        '', result, flags=re.IGNORECASE
    )
    
    # Phase 0c: Strip "Sự kiện này có là" pattern
    result = re.sub(r'\.\s*Sự kiện này có là\s+', '. ', result, flags=re.IGNORECASE)
    
    # Phase 0d: Strip "Trả lời sẽ nêu rõ mốc, diễn biến chính và" trailing
    result = re.sub(r'\.\s*Trả lời sẽ nêu rõ.+$', '.', result, flags=re.IGNORECASE)
    
    result = result.strip()
    
    # Phase 1: Remove structural/query-style prefixes (these are data artifacts, not content)
    structural_patterns = [
        r'^Câu hỏi nhắm tới sự kiện\s*',
        r'^Tóm tắt bối cảnh\s*–\s*diễn biến\s*–\s*kết quả của\s*',
        r'^Bối cảnh:\s*',
        r'^Kể về .+ và đóng góp của .+ trong\s*',
    ]
    for pattern in structural_patterns:
        result = re.sub(pattern, '', result, flags=re.IGNORECASE)
    
    # Phase 1b: Remove semicolon-style summary prefixes
    # Pattern: "Event diễn ra năm 1960; Description..." → keep only Description
    # Pattern: "Event xảy ra năm 1284; Description..." → keep only Description
    result = re.sub(r'^.+\s+diễn ra năm\s+\d{3,4};\s*', '', result, flags=re.IGNORECASE)
    result = re.sub(r'^.+\s+xảy ra năm\s+\d{3,4};\s*', '', result, flags=re.IGNORECASE)
    
    # Phase 1c: Remove event-title prefix patterns
    # Pattern: "Event (1284): Description" → keep only Description
    result = re.sub(r'^.+\(\d{4}\):\s*', '', result, flags=re.IGNORECASE)
    # Pattern: "Hịch tướng sĩ (1284)." → remove if it's just a bare title+year
    # Only match short text (< 80 chars) to avoid stripping full sentences
    if len(result) < 80:
        result = re.sub(r'^[^.;!?]+\(\d{4}\)\.?\s*$', '', result, flags=re.IGNORECASE)
    
    # Phase 2: Remove year prefixes to avoid "Năm 1930: Năm 1930, ..." duplication
    year_prefixes = [
        r'^Năm \d+[,:]?\s*',
        r'^Vào năm \d+[,:]?\s*',
        r'^năm \d+[,:]?\s*',
        r'^\d{3,4}[,:]\s*',
    ]
    for pattern in year_prefixes:
        result = re.sub(pattern, '', result, flags=re.IGNORECASE)
    
    # Phase 3: Remove action-style prefixes
    action_prefixes = [
        r'^gắn mốc \d+ với\s*',
        r'^diễn ra\s*',
        r'^xảy ra\s*',
    ]
    for pattern in action_prefixes:
        result = re.sub(pattern, '', result, flags=re.IGNORECASE)
    
    # Phase 4: Remove trailing metadata
    result = re.sub(r'\(\d{4}\)[.:,]?\s*$', '', result)  # trailing (1911).
    result = re.sub(r',\s*địa điểm\s+.+$', '', result)   # trailing ", địa điểm Hà Nội"
    result = re.sub(r'\s+thuộc\s+.+\d{4}[.,]?\s*$', '', result)  # trailing "thuộc X 1945."
    
    # Phase 5: Normalize punctuation artifacts (double dots, orphan periods)
    result = re.sub(r'\.\s*\.\s*\.', '.', result)   # ".. ." → "."
    result = re.sub(r'\.{2,}', '.', result)          # ".." → "."
    result = re.sub(r'\.\s+\.', '.', result)         # ". ." → "."
    result = result.strip().rstrip('.')  # Remove trailing dot (will be re-added by formatter)
    if result and not result.endswith(('.', '!', '?')):
        result += '.'
    
    return result.strip()


# ── Pronoun replacement for repeated person names ──────────────────
# Special pronoun for HCM (only exception)
_HCM_CANONICAL = "hồ chí minh"
# Female canonical names → pronoun "bà"
_FEMALE_CANONICALS = frozenset({
    "hai bà trưng", "trưng trắc", "trưng nhị",
    "bà triệu", "triệu thị trinh",
    "âu cơ",
})
# Compound nouns that contain a person name but must NOT be touched
_PROTECTED_COMPOUNDS = [
    "chiến dịch hồ chí minh",
    "thành phố hồ chí minh",
    "tp hồ chí minh",
    "tp. hồ chí minh",
    "lăng chủ tịch hồ chí minh",
    "lăng bác",
    "đường hồ chí minh",
    "tư tưởng hồ chí minh",
    "bảo tàng hồ chí minh",
]


def _build_canonical_name_groups() -> dict:
    """
    Build canonical → [all name forms] mapping from PERSON_ALIASES.
    Returns dict: canonical_lower → list of name forms (longest first).
    """
    groups: dict = {}
    for alias, canonical in startup.PERSON_ALIASES.items():
        if canonical not in groups:
            groups[canonical] = set()
        groups[canonical].add(canonical)
        groups[canonical].add(alias)
    # Convert to sorted lists (longest first, so we match longer names before shorter)
    return {c: sorted(names, key=len, reverse=True) for c, names in groups.items()}


def _get_pronoun(canonical: str) -> str:
    """Return the correct pronoun for a canonical person name."""
    if canonical == _HCM_CANONICAL:
        return "Bác"
    # Check if canonical or any of its aliases is a known female
    canonical_lower = canonical.lower()
    if canonical_lower in _FEMALE_CANONICALS:
        return "bà"
    # Also check if any alias maps to a female canonical
    for female in _FEMALE_CANONICALS:
        if female == canonical_lower:
            return "bà"
        # Check reverse: the canonical itself may be an alias of a female canonical
        mapped = startup.PERSON_ALIASES.get(canonical_lower, "")
        if mapped in _FEMALE_CANONICALS:
            return "bà"
    return "ông"


def _is_protected_position(text_lower: str, start: int, end: int) -> bool:
    """Check if the name at [start:end] is part of a protected compound noun."""
    for compound in _PROTECTED_COMPOUNDS:
        # Find the compound in the text near our match position
        cpos = text_lower.find(compound)
        while cpos != -1:
            cend = cpos + len(compound)
            # Our name match overlaps with this compound → protected
            if start >= cpos and end <= cend:
                return True
            cpos = text_lower.find(compound, cpos + 1)
    return False


def replace_repeated_names(text: str) -> str:
    """
    Replace 2nd+ occurrences of the same person name (including aliases)
    with the appropriate Vietnamese pronoun.

    Rules:
    - Hồ Chí Minh (+ aliases) → "Bác"
    - Female figures → "bà"
    - All other persons → "ông"
    - Protected compound nouns (e.g. "Chiến dịch Hồ Chí Minh") are skipped

    Only replaces when the same canonical person appears 2+ times.
    Keeps the FIRST occurrence and replaces subsequent ones.
    """
    if not text or not isinstance(text, str) or len(text) < 10:
        return text

    # Build name groups from startup aliases
    if not hasattr(startup, 'PERSON_ALIASES') or not startup.PERSON_ALIASES:
        return text

    groups = _build_canonical_name_groups()
    if not groups:
        return text

    text_lower = text.lower()

    # Step 1: Find ALL name occurrences across all canonical groups
    # Each occurrence: (start, end, canonical, matched_name)
    all_matches = []
    for canonical, name_forms in groups.items():
        for name in name_forms:
            if len(name) < 2:  # Skip very short names to avoid false positives
                continue
            search_start = 0
            name_lower = name.lower()
            while True:
                pos = text_lower.find(name_lower, search_start)
                if pos == -1:
                    break
                end_pos = pos + len(name)

                # Word boundary check: ensure we're not matching inside another word
                # Check character before match
                if pos > 0 and text_lower[pos - 1].isalpha():
                    search_start = pos + 1
                    continue
                # Check character after match
                if end_pos < len(text_lower) and text_lower[end_pos].isalpha():
                    search_start = pos + 1
                    continue

                all_matches.append((pos, end_pos, canonical, name))
                search_start = end_pos

    if not all_matches:
        return text

    # Step 2: Remove overlapping matches (keep longest match at each position)
    all_matches.sort(key=lambda m: (m[0], -(m[1] - m[0])))
    filtered = []
    last_end = -1
    for match in all_matches:
        if match[0] >= last_end:
            filtered.append(match)
            last_end = match[1]

    # Step 3: Group by canonical, keeping order of appearance
    from collections import OrderedDict
    canonical_occurrences: dict = OrderedDict()
    for match in filtered:
        canonical = match[2]
        if canonical not in canonical_occurrences:
            canonical_occurrences[canonical] = []
        canonical_occurrences[canonical].append(match)

    # Step 4: Identify which matches to replace (2nd+ occurrence per canonical)
    replacements = {}  # (start, end) → pronoun
    for canonical, matches in canonical_occurrences.items():
        if len(matches) < 2:
            continue  # Only 1 mention — no replacement needed
        pronoun = _get_pronoun(canonical)
        for i, match in enumerate(matches):
            if i == 0:
                continue  # Keep the first occurrence
            start, end = match[0], match[1]
            # Skip if this is part of a protected compound noun
            if _is_protected_position(text_lower, start, end):
                continue
            replacements[(start, end)] = pronoun

    if not replacements:
        return text

    # Step 5: Apply replacements from end to start (to preserve positions)
    result = list(text)
    for (start, end), pronoun in sorted(replacements.items(), reverse=True):
        # Capitalize pronoun if it starts a sentence (after '. ' or start of text)
        cap_pronoun = pronoun
        if start == 0 or (start >= 2 and text[start - 2:start] == '. '):
            cap_pronoun = pronoun[0].upper() + pronoun[1:] if len(pronoun) > 1 else pronoun.upper()

        result[start:end] = list(cap_pronoun)

    return ''.join(result)


def extract_core_keywords(text: str) -> set:
    """
    Extract core keywords from event text for fuzzy deduplication.
    """
    if not text:
        return set()
    
    # Common words to ignore
    stop_words = {
        "năm", "của", "và", "trong", "là", "có", "được", "với", "các", "những",
        "diễn", "ra", "vào", "xảy", "kể", "về", "tóm", "tắt", "gì", "nào",
        "bối", "cảnh", "biến", "kết", "quả", "gắn", "mốc", "thời", "kỳ",
        "sự", "kiện", "lịch", "sử", "việt", "nam", "the", "of", "and", "in",
        "câu", "hỏi", "nhắm", "tới"
    }
    
    normalized = re.sub(r'[^\w\s]', ' ', text.lower())
    words = normalized.split()
    keywords = {w for w in words if len(w) > 2 and w not in stop_words}
    return keywords


from difflib import SequenceMatcher

def compute_text_similarity(text1: str, text2: str) -> float:
    """Compute similarity between two texts using SequenceMatcher."""
    return SequenceMatcher(None, text1, text2).ratio()

def _is_similar_event(text1_lower: str, text2_lower: str, kw1: set | None = None, kw2: set | None = None) -> bool:
    """
    Check if two cleaned event texts are similar enough to be considered duplicates.
    Uses multiple strategies: containment, SequenceMatcher, keyword overlap,
    and normalized-text comparison (strips year prefixes/bullets).
    """
    # Strategy 0: Normalized comparison (catches year-prefix-only differences)
    norm1 = normalize_for_dedup(text1_lower)
    norm2 = normalize_for_dedup(text2_lower)
    if norm1 and norm2:
        if norm1 == norm2:
            return True
        if norm1 in norm2 or norm2 in norm1:
            return True

    # Strategy 1: Direct containment (on raw text)
    if text1_lower in text2_lower or text2_lower in text1_lower:
        return True
    
    # Strategy 2: SequenceMatcher similarity
    # Use normalized text for more accurate comparison
    sim = compute_text_similarity(norm1 or text1_lower, norm2 or text2_lower)
    # Lower threshold for short texts (< 80 chars) to catch compact reformulations
    threshold = 0.55 if len(text1_lower) < 80 or len(text2_lower) < 80 else 0.6
    if sim > threshold:
        return True
    
    # Strategy 3: Keyword-based Jaccard overlap (catches reformulated sentences)
    if kw1 is not None and kw2 is not None and kw1 and kw2:
        intersection = kw1 & kw2
        union = kw1 | kw2
        jaccard = len(intersection) / len(union) if union else 0
        if jaccard > 0.7:
            return True
    
    return False


def deduplicate_and_enrich(raw_events: list, max_events: int = MAX_TOTAL_EVENTS) -> list:
    """
    Deduplicate events and enrich with complete information.
    Aggressively merges similar events to prevent repetition.
    Uses GLOBAL cross-year dedup to catch same-event across different year groups.
    """
    if not raw_events:
        return []
    
    # Group events by year
    by_year = {}
    for e in raw_events:
        year = e.get("year", 0)
        # Coerce non-int/non-hashable year types
        if year is None:
            year = 0
        elif not isinstance(year, (int, float)):
            try:
                year = int(year) if not isinstance(year, (list, dict, set)) else 0
            except (ValueError, TypeError):
                year = 0
        else:
            year = int(year)
        if year not in by_year:
            by_year[year] = []
        by_year[year].append(e)
    
    # Global cluster for cross-year dedup
    global_cluster = []  # [{"event": doc, "text": cleaned, "text_lower": lower, "keywords": set}]
    
    for year in sorted(by_year.keys(), key=lambda y: y if isinstance(y, (int, float)) else 0):
        year_events = by_year[year]
        if not year_events:
            continue

        # Sort by content length (descending) to prefer longer, detailed stories as base 
        year_events.sort(key=lambda x: len(str(x.get("story", "") or x.get("event", "") or "")), reverse=True)
        
        for event in year_events:
            event_text = clean_story_text(event.get("story", "") or event.get("event", "") or "")
            
            # Filter out texts that are too short after cleaning (metadata noise)
            if len(event_text.strip()) < MIN_CLEAN_TEXT_LENGTH:
                continue
            
            event_lower = event_text.lower()
            event_keywords = extract_core_keywords(event_text)
            
            is_duplicate = False
            
            # Compare against ALL previously accepted events (global cross-year dedup)
            for cluster_item in global_cluster:
                base_event = cluster_item["event"]
                base_lower = cluster_item["text_lower"]
                base_keywords = cluster_item["keywords"]
                
                if _is_similar_event(event_lower, base_lower, event_keywords, base_keywords):
                    is_duplicate = True
                    
                    # Merge info into base_event (the longer one usually)
                    current_persons = set(base_event.get("persons", []))
                    current_persons.update(event.get("persons", []))
                    base_event["persons"] = list(current_persons)
                    
                    current_places = set(base_event.get("places", []))
                    current_places.update(event.get("places", []))
                    base_event["places"] = list(current_places)
                    
                    # Keep the absolute longest story text
                    base_text = cluster_item["text"]
                    if len(event_text) > len(base_text):
                        base_event["story"] = event.get("story", "")
                        base_event["event"] = event.get("event", "")
                        cluster_item["text"] = event_text
                        cluster_item["text_lower"] = event_lower
                        cluster_item["keywords"] = event_keywords
                    
                    break  # Found a match, stop checking other clusters
            
            if not is_duplicate:
                global_cluster.append({
                    "event": event,
                    "text": event_text,
                    "text_lower": event_lower,
                    "keywords": event_keywords,
                })
            
            if len(global_cluster) >= max_events:
                break
        
        if len(global_cluster) >= max_events:
            break
    
    return [item["event"] for item in global_cluster[:max_events]]


# Pattern to detect question/prompt titles dynamically
_QUESTION_TITLE_RE = re.compile(
    r'(?:'
    r'kể tên|tóm tắt|vì sao|tại sao|vì lý do gì|'
    r'ai là|điều gì|hãy cho biết|nêu|giải thích|'
    r'bối cảnh nào|hậu quả|tác động|vai trò|'
    r'quan trọng đối với|ý nghĩa|kết quả ra sao|'
    r'xảy ra khi nào|diễn biến|liệt kê|mô tả|'
    r'so sánh|phân tích|nhân vật trung tâm|'
    r'sự kiện nổi bật|có ý nghĩa lịch sử|'
    r'trong năm \d{3,4}|ở việt nam'
    r')',
    re.IGNORECASE,
)


def _is_question_title(title: str) -> bool:
    """Dynamically detect if a title is actually a question/prompt."""
    if not title:
        return False
    t = title.lower().strip()
    if t.endswith('?'):
        return True
    return bool(_QUESTION_TITLE_RE.search(t))


def format_complete_answer(events: list, group_by: str = "year") -> str:
    """
    Format events into a concise answer.
    Supports two grouping modes:
      - "year" (default): group by year for chronological output
      - "dynasty": group by dynasty for dynasty-timeline output
    Avoids duplication and produces natural-sounding Vietnamese text.
    Dynamically detects and skips question-style titles.
    """
    if not events:
        return None

    if group_by == "dynasty":
        return _format_by_dynasty(events)

    return _format_by_year(events)


def _format_event_text(e: dict, year=None, seen_texts: list = None) -> str | None:
    """Format a single event into clean text. Returns None if duplicate."""
    story = e.get("story", "") or e.get("event", "") or ""
    # Coerce non-string types to string
    if not isinstance(story, str):
        story = str(story)
    clean_story = clean_story_text(story, year)

    # Bug #4 Fix: Ensure clean_story is valid before proceeding
    if not clean_story or not isinstance(clean_story, str) or len(clean_story.strip()) == 0:
        return None

    title = e.get("title", "")
    clean_title = clean_story_text(title, year) if title else ""

    # Bug #4 Fix: Additional validation for clean_title before string operations
    if clean_title and isinstance(clean_title, str) and clean_title.strip():
        if clean_story and clean_title.lower() != clean_story.lower():
            if not _is_question_title(clean_title):
                # Check both exact containment AND fuzzy similarity
                title_in_story = clean_title.lower() in clean_story.lower()
                # Fuzzy guard via token_set_ratio (order-agnostic)
                title_norm = normalize_for_dedup(clean_title)
                story_norm = normalize_for_dedup(clean_story)
                fuzzy_dup = _is_fuzzy_dup(title_norm, story_norm)
                if not title_in_story and not fuzzy_dup:
                    clean_story = f"{clean_title}: {clean_story}"

    # Bug #1 Fix: Check clean_story is not empty before indexing
    if not clean_story or len(clean_story) == 0:
        return None

    clean_story = clean_story[0].upper() + clean_story[1:]
    if not clean_story.endswith(('.', '!', '?')):
        clean_story += "."

    # Use normalize_for_dedup for year-prefix-agnostic dedup
    dedup_key = normalize_for_dedup(clean_story)

    if seen_texts is not None:
        # Gap #3 fix: fuzzy containment check instead of exact set membership
        if any(_is_fuzzy_dup(dedup_key, prev) for prev in seen_texts):
            return None
        seen_texts.append(dedup_key)

    return clean_story


def _format_by_year(events: list) -> str | None:
    """Group events by year (original behavior)."""
    by_year = {}
    for e in events:
        year = e.get("year")
        # Coerce non-hashable/non-int year types
        if year is None:
            year = 0
        elif not isinstance(year, (int, float)):
            try:
                year = int(year) if not isinstance(year, (list, dict, set)) else 0
            except (ValueError, TypeError):
                year = 0
        else:
            year = int(year)
        if year not in by_year:
            by_year[year] = []
        by_year[year].append(e)

    paragraphs = []
    sorted_years = sorted(by_year.keys()) if all(isinstance(y, int) for y in by_year.keys() if y) else by_year.keys()
    seen_texts = []  # Changed from set to list for fuzzy matching

    for year in sorted_years:
        event_texts = []
        for e in by_year[year]:
            text = _format_event_text(e, year, seen_texts)
            if text:
                event_texts.append(text)
        if event_texts:
            joined = " ".join(event_texts)
            # Gap #5 fix: dedup within joined paragraph
            joined = _dedup_intra_line(joined)
            if year:
                paragraphs.append(format_timeline_entry(year, joined))
            else:
                # Fallback: extract year from joined event text
                fallback_year = extract_year({}, joined)
                if fallback_year:
                    paragraphs.append(format_timeline_entry(fallback_year, joined))
                else:
                    paragraphs.append(joined)

    return "\n\n".join(paragraphs) if paragraphs else None


def _format_by_dynasty(events: list) -> str | None:
    """
    Group events by dynasty in canonical order.
    Produces output like:
      **Nhà Ngô (939):** ...
      **Nhà Đinh (968):** ...
      **Nhà Lý (1009–1225):** ...
    """
    # Build dynasty → events mapping
    by_dynasty: dict[str, list] = {}
    for e in events:
        dynasty = e.get("dynasty", "Khác")
        if dynasty not in by_dynasty:
            by_dynasty[dynasty] = []
        by_dynasty[dynasty].append(e)

    paragraphs = []
    seen_texts = []  # list for fuzzy matching

    for dynasty in DYNASTY_ORDER:
        dynasty_events = by_dynasty.get(dynasty, [])
        if not dynasty_events:
            continue

        # Sort events within dynasty by year
        dynasty_events.sort(key=lambda d: safe_year(d.get("year")))

        event_texts = []
        for e in dynasty_events:
            text = _format_event_text(e, e.get("year"), seen_texts)
            if text:
                event_texts.append(text)

        if event_texts:
            # Create dynasty header with year range
            # Bug #2b Fix: Ensure years list is not empty before min/max
            years = [e.get("year") for e in dynasty_events if e.get("year") and isinstance(e.get("year"), (int, str))]
            if years and len(years) > 0:
                try:
                    year_range = f"{min(years)}–{max(years)}" if min(years) != max(years) else str(min(years))
                    header = f"**{dynasty} ({year_range}):**"
                except (ValueError, TypeError):
                    header = f"**{dynasty}:**"
            else:
                header = f"**{dynasty}:**"
            paragraphs.append(f"{header} {' '.join(event_texts)}")

    return "\n\n".join(paragraphs) if paragraphs else None


def _filter_by_query_keywords(query: str, events: list) -> list:
    """
    Dynamic keyword relevance filter.
    Scores events by query-word overlap and removes low-scoring outliers.
    Uses relative scoring (remove bottom quartile) instead of absolute threshold
    to handle diverse query types gracefully.
    """
    # Stopwords — carry no semantic meaning for filtering
    STOPWORDS = {
        "là", "gì", "của", "và", "hay", "hoặc", "có", "không", "được", "bị",
        "cho", "với", "từ", "đến", "trong", "ngoài", "về", "theo", "như",
        "hãy", "kể", "nêu", "liệt", "tóm", "tắt", "mô", "tả", "giải",
        "thích", "tôi", "bạn", "ai", "nào", "đâu", "sao", "thế", "nhé",
        "ạ", "vậy", "rồi", "nha", "nhỉ", "này", "đó", "kia", "ấy",
        "những", "các", "một", "mọi", "mỗi", "nhiều", "ít", "ra",
        "lên", "xuống", "vào", "đi", "lại", "đã", "đang", "sẽ", "cũng",
        "rất", "quá", "lắm", "nhất", "hơn",
    }

    q_low = query.lower()
    # Extract meaningful keywords from query (2+ chars, not stopwords)
    query_words = set()
    for word in q_low.split():
        word_clean = word.strip(".,!?;:\"'()[]{}—–-")
        if len(word_clean) >= 2 and word_clean not in STOPWORDS:
            query_words.add(word_clean)

    if len(query_words) < 2:
        return events  # Not enough keywords to filter

    # Remove non-discriminating keywords (e.g., "việt nam" in a VN-history dataset)
    query_words = filter_discriminating_keywords(query_words)

    # Score each event by word overlap with query
    scored = []
    for doc in events:
        doc_text = (
            (doc.get("story", "") or "") + " " +
            (doc.get("event", "") or "") + " " +
            " ".join(doc.get("keywords", []) or [])
        ).lower()

        score = sum(1 for w in query_words if w in doc_text)
        scored.append((doc, score))

    if not scored:
        return events

    # Bug #2 Fix: Filter out None scores and check if any valid scores exist
    valid_scores = [s for _, s in scored if s is not None and s > 0]
    if not valid_scores:
        return events  # No valid scores to compare

    # Find the maximum score achieved
    max_score = max(valid_scores)
    if max_score <= 1:
        return events  # All events have low overlap, don't filter

    # Relative threshold: keep events with score >= 50% of max score
    # This removes clear outliers while keeping contextually relevant events
    threshold = max(2, max_score // 2)
    relevant = [doc for doc, score in scored if score >= threshold]

    # Fallback: if too aggressive, keep all events with score > 0
    if not relevant:
        relevant = [doc for doc, score in scored if score > 0]

    return relevant if relevant else events


def _strip_accents(text: str) -> str:
    """Strip Vietnamese diacritical marks for fuzzy matching."""
    import unicodedata
    nfkd = unicodedata.normalize('NFKD', text)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


def _detect_same_entity(query: str, resolved: dict) -> dict | None:
    """
    Detect if query mentions multiple names that are actually the same entity.
    Dynamically checks ALL alias sources: person_aliases, topic_synonyms, dynasty_aliases.
    Handles both accented and unaccented queries.
    Returns {"entity_type": str, "canonical": str, "names_mentioned": list, "all_aliases": list} or None.
    """
    q_low = query.lower()
    q_stripped = _strip_accents(q_low)

    # Define all alias sources to check dynamically
    # Each entry: (alias_dict, entity_type_label, entity_type_vi)
    alias_sources = [
        (startup.PERSON_ALIASES, "person", "người"),
        (startup.TOPIC_SYNONYMS, "topic", "chủ đề"),
        (startup.DYNASTY_ALIASES, "dynasty", "triều đại"),
    ]

    for alias_dict, entity_type, entity_type_vi in alias_sources:
        if not alias_dict:
            continue

        # Build complete name → canonical mapping for this source
        name_to_canonical = dict(alias_dict)  # alias → canonical
        # Add canonical → canonical for self-references
        for canonical in set(alias_dict.values()):
            name_to_canonical[canonical] = canonical

        # For persons, also include person index keys
        if entity_type == "person":
            for person_key in startup.PERSONS_INDEX:
                if person_key not in name_to_canonical:
                    name_to_canonical[person_key] = person_key

        # Find all names mentioned in query (longest-first to avoid partial matches)
        mentioned = []
        for name in sorted(name_to_canonical.keys(), key=len, reverse=True):
            if name in q_low or _strip_accents(name) in q_stripped:
                mentioned.append((name, name_to_canonical[name]))

        # Remove substrings — "trần" is substring of "trần hưng đạo"
        filtered = []
        for name, canonical in mentioned:
            is_substring = any(
                name != other_name and name in other_name
                for other_name, _ in mentioned
            )
            if not is_substring:
                filtered.append((name, canonical))

        if len(filtered) >= 2:
            # Check if 2+ distinct names resolve to same canonical entity
            canonical_set = set(m[1] for m in filtered)
            if len(canonical_set) == 1:
                canonical = list(canonical_set)[0]
                all_aliases = [alias for alias, can in alias_dict.items()
                              if can == canonical and alias != canonical]
                return {
                    "entity_type": entity_type,
                    "entity_type_vi": entity_type_vi,
                    "canonical": canonical,
                    "names_mentioned": [m[0] for m in filtered],
                    "all_aliases": all_aliases,
                }

    return None


def _generate_same_entity_response(info: dict) -> str:
    """
    Generate a response explaining multiple names refer to the same entity.
    Works dynamically for any entity type: person, topic, dynasty.
    """
    canonical = info["canonical"]
    names = info["names_mentioned"]
    all_aliases = info.get("all_aliases", [])
    entity_type = info.get("entity_type", "person")

    # Format the names mentioned
    name_parts = [f"**{n.title()}**" for n in names]
    names_str = " và ".join(name_parts)

    # Dynamic label based on entity type
    type_labels = {
        "person": ("cùng một người", "Tên chính", "Các tên gọi khác"),
        "topic": ("cùng một chủ đề / sự kiện", "Tên chính", "Các tên gọi khác"),
        "dynasty": ("cùng một triều đại / thời kỳ", "Tên chính", "Các tên gọi khác"),
    }
    same_label, main_label, alias_label = type_labels.get(
        entity_type, ("cùng một thực thể", "Tên chính", "Các tên gọi khác")
    )

    # Capitalize the names properly
    capitalized_canonical = " ".join([word.capitalize() for word in canonical.split()])

    response = f"{names_str} là **{same_label}**.\n\n"
    response += f"{main_label}: **{capitalized_canonical}**\n\n"

    if all_aliases:
        capitalized_aliases = [ " ".join([word.capitalize() for word in a.split()]) for a in all_aliases]
        alias_str = ", ".join(capitalized_aliases)
        response += f"{alias_label}: {alias_str}"

    return response


def _boost_year_match(events: list, target_year: int) -> list:
    """
    Reorder events so that events with years closest to target_year come first.
    Exact year match → highest priority, then sorted by distance.
    Events without year field go to the end.
    """
    def year_distance(event):
        y = event.get("year")
        if y is None:
            return 999999
        try:
            return abs(int(y) - target_year)
        except (ValueError, TypeError):
            return 999999
    return sorted(events, key=year_distance)


def _build_conflict_explanation(query_info, resolved: dict) -> str:
    """
    Build an informative Vietnamese answer explaining temporal conflict.
    Instead of returning 'no data', explain WHY the entities don't overlap.
    """
    persons = resolved.get("persons", [])
    
    if len(persons) >= 2:
        # Multi-person temporal conflict
        names = [p.title() for p in persons]
        names_str = " và ".join(names)
        explanation = (
            f"**{names_str}** sống ở các giai đoạn lịch sử khác nhau, "
            f"nên không có sự kiện chung trong cùng thời kỳ.\n\n"
        )
        # Suggest individual searches
        explanation += "Bạn có thể tìm hiểu riêng từng nhân vật:\n\n"
        for p in persons:
            explanation += f"- *\"{p.title()}\"*\n"
        
        return explanation
    
    # Generic conflict explanation
    reasons = query_info.conflict_reasons if hasattr(query_info, 'conflict_reasons') else []
    if reasons:
        return (
            "Câu hỏi có mâu thuẫn về mặt thời gian. "
            + " ".join(reasons)
            + "\n\nBạn có thể thử hỏi cụ thể hơn về từng nhân vật hoặc sự kiện."
        )
    
    return (
        "Câu hỏi chứa thông tin mâu thuẫn về mặt thời gian. "
        "Bạn có thể thử hỏi cụ thể hơn về từng nhân vật hoặc sự kiện."
    )


def engine_answer(query: str):
    # --- STEP 0: Query Understanding (NLU) ---
    # Rewrite query: fix typos, expand abbreviations, restore accents
    rewritten = rewrite_query(query)
    # Use rewritten for all downstream processing
    q = rewritten.lower()
    q_display = query  # Keep original for display

    # Detect high-level question intent for context
    question_intent = extract_question_intent(rewritten)

    # Handle greeting queries — "hello", "hi", "xin chào"
    # Use regex for exact matching to avoid false positives
    if any(re.search(pattern, q) for pattern in GREETING_PATTERNS):
        return {
            "query": q_display,
            "intent": "greeting",
            "answer": GREETING_RESPONSE,
            "events": [],
            "no_data": False
        }

    # Handle thank you queries
    if any(re.search(pattern, q) for pattern in THANK_PATTERNS):
        return {
            "query": q_display,
            "intent": "thank",
            "answer": THANK_RESPONSE,
            "events": [],
            "no_data": False
        }

    # Handle goodbye queries
    if any(re.search(pattern, q) for pattern in GOODBYE_PATTERNS):
        return {
            "query": q_display,
            "intent": "goodbye",
            "answer": GOODBYE_RESPONSE,
            "events": [],
            "no_data": False
        }

    # Handle creator queries — "ai tạo ra bạn?", "ai phát triển bạn?"
    # Check BEFORE identity to avoid 'bạn là ai' substring matching
    if any(pattern in q for pattern in CREATOR_PATTERNS):
        return {
            "query": q_display,
            "intent": "creator",
            "answer": CREATOR_RESPONSE,
            "events": [],
            "no_data": False
        }

    # Handle identity queries — "bạn là ai?", "giới thiệu bản thân"
    if any(pattern in q for pattern in IDENTITY_PATTERNS):
        return {
            "query": q_display,
            "intent": "identity",
            "answer": IDENTITY_RESPONSE,
            "events": [],
            "no_data": False
        }

    intent = "semantic"
    raw_events = []
    is_dynasty_query = False
    is_range_query = False
    is_entity_query = False
    same_person_info = None
    semantic_group_by = "year"  # Default grouping; "dynasty" for timeline intent

    # Dynamic entity resolution (data-driven, no hardcoded patterns)
    # Uses rewritten query for better entity matching
    resolved = resolve_query_entities(rewritten)
    has_persons = bool(resolved.get("persons"))
    has_topics = bool(resolved.get("topics"))
    has_dynasties = bool(resolved.get("dynasties"))
    has_places = bool(resolved.get("places"))
    has_entities = has_persons or has_topics or has_dynasties or has_places

    # --- STEP 1.5: INTENT CLASSIFICATION V2 ---
    # Structured query analysis with 10 intents, duration guard, question-type detection.
    year_range = extract_year_range(rewritten)
    multi_years = extract_multiple_years(rewritten)
    single_year = extract_single_year(rewritten)

    # Apply duration guard: "kỉ niệm 1000 năm" → duration_guard=True → year=None
    query_analysis = classify_intent(
        query=rewritten,
        resolved_entities=resolved,
        year=single_year,
        year_range=year_range,
        multi_years=multi_years,
        original_query=query,
    )

    # --- STEP 1.7: CONSTRAINT EXTRACTION (Phase 1 / Giai đoạn 11) ---
    # Build QueryInfo from QueryAnalysis + resolved entities
    # This consolidates all hard constraints into 1 object for downstream filtering
    _constraint_extractor = ConstraintExtractor()
    query_info = _constraint_extractor.extract(
        original_query=query,
        normalized_query=rewritten,
        query_analysis=query_analysis,
        resolved_entities=resolved,
    )

    # --- STEP 1.8: CONFLICT DETECTION (Temporal Consistency Guard) ---
    # Detect contradictions BEFORE search to avoid impossible answers
    # e.g., "Năm 1945 Trần Hưng Đạo" → Person died 1300 → CONFLICT
    _conflict_detector = ConflictDetector()
    query_info = _conflict_detector.detect(query_info)
    if query_info.has_conflict:
        conflict_msg = "; ".join(query_info.conflict_reasons)
        print(f"[CONFLICT_GATE] Query rejected: {conflict_msg}")
        # Build an informative answer explaining the temporal conflict
        conflict_explanation = _build_conflict_explanation(query_info, resolved)
        return {
            "query": q_display,
            "intent": intent,
            "answer": conflict_explanation,
            "events": [],
            "no_data": False,  # This IS an answer — explaining the conflict
            "conflict": True,
            "conflict_reasons": query_info.conflict_reasons,
        }

    # Data scope query — immediate return, no retrieval needed
    if query_analysis.intent == "data_scope":
        answer = synthesize_answer(query_analysis, [])
        return {
            "query": q_display,
            "intent": "data_scope",
            "answer": answer,
            "events": [],
            "no_data": False
        }

    # --- FACT-CHECK INTENT ---
    # User claims a fact and asks for confirmation ("...năm 1991 phải không?")
    # Retrieve events, then compare claimed year vs actual year
    if query_analysis.intent == "fact_check":
        fc_events = scan_by_entities(resolved)
        if not fc_events:
            fc_events = semantic_search(rewritten)
        # Deduplicate and pick best match
        fc_events = deduplicate_and_enrich(fc_events, max_events=5)
        # Year-proximity boost: sort events so claimed_year match comes first
        # Otherwise _build_fact_check picks events[0] which may be wrong year
        if query_analysis.fact_check_year and fc_events:
            fc_events = _boost_year_match(fc_events, query_analysis.fact_check_year)
        answer = synthesize_answer(query_analysis, fc_events)
        if answer:
            return {
                "query": q_display,
                "intent": "fact_check",
                "answer": answer,
                "events": fc_events[:3],
                "no_data": False
            }
        # Fallback: if no events found, generate no-data suggestion
        suggestion = _generate_no_data_suggestion(query, rewritten, resolved, question_intent)
        return {
            "query": q_display,
            "intent": "fact_check",
            "answer": suggestion,
            "events": [],
            "no_data": True
        }

    # --- STEP 1.6: SEMANTIC INTENT CLASSIFICATION ---
    # Classify war/resistance/territorial queries using linguistic analysis
    # This handles: "chiến tranh Việt Nam", "kháng chiến ở VN", etc.
    sem_intent = classify_semantic_intent(rewritten, resolved)
    war_intro = None  # Special intro for war/resistance queries

    # Map new intents to legacy dispatch flags
    if sem_intent.intent == "resistance_national" and sem_intent.confidence >= 0.85:
        # NATIONAL RESISTANCE — "chiến tranh Việt Nam", "kháng chiến chống ngoại xâm"
        intent = "resistance_national"
        is_range_query = True  # Use higher event limit
        raw_events = scan_national_resistance()
        # Also supplement with year-range scan for 1945-1975 (anti-French + anti-American)
        range_events = scan_by_year_range(1945, 1975)
        for e in range_events:
            if e not in raw_events:
                raw_events.append(e)
        # Also supplement with semantic search for broader coverage
        sem_results = semantic_search(rewritten)
        for e in sem_results:
            if e not in raw_events:
                raw_events.append(e)
        war_intro = (
            'Có phải bạn đang muốn tìm hiểu về: "Kháng chiến chống giặc ngoại xâm'
            ' – bản hùng ca giữ nước vang vọng suốt chiều dài'
            ' lịch sử vẻ vang của dân tộc Việt Nam ta."'
        )
    elif sem_intent.intent == "territorial_event" and sem_intent.confidence >= 0.80:
        # TERRITORIAL — "chiến tranh ở Việt Nam"
        intent = "territorial_event"
        is_range_query = True
        raw_events = scan_territorial_conflicts()
        range_events = scan_by_year_range(1945, 1975)
        for e in range_events:
            if e not in raw_events:
                raw_events.append(e)
        sem_results = semantic_search(rewritten)
        for e in sem_results:
            if e not in raw_events:
                raw_events.append(e)
        war_intro = (
            'Có phải bạn đang muốn tìm hiểu về: "Kháng chiến chống giặc ngoại xâm'
            ' – bản hùng ca giữ nước vang vọng suốt chiều dài'
            ' lịch sử vẻ vang của dân tộc Việt Nam ta."'
        )
    elif sem_intent.intent == "civil_war" and sem_intent.confidence >= 0.80:
        intent = "civil_war"
        is_range_query = True
        raw_events = scan_civil_wars()
    elif query_analysis.intent == "dynasty_timeline":
        intent = "dynasty_timeline"
        is_dynasty_query = True
        raw_events = scan_by_dynasty_timeline()
        semantic_group_by = "dynasty"
    elif query_analysis.intent == "broad_history":
        intent = "broad_history"
        is_dynasty_query = True
        raw_events = scan_broad_history()
    elif query_analysis.confidence >= 0.8 and query_analysis.intent in (
        "person_query", "event_query", "dynasty_query",
        "definition", "relationship"
    ):
        # High-confidence entity-based intents use entity scan
        intent = query_analysis.intent
        is_entity_query = True
        if query_analysis.intent == "dynasty_query":
            is_dynasty_query = True
        raw_events = scan_by_entities(resolved)
        # V2 high-confidence but entity scan empty → fallback to semantic search
        # (e.g., "Bác Hồ ra đi năm nào" → person resolved but entity index sparse)
        if not raw_events:
            raw_events = semantic_search(rewritten)

    # --- SAME-ENTITY DETECTION (Dynamic, ALWAYS runs) ---
    # Detects if 2+ names in query refer to same entity (person, topic, or dynasty)
    # E.g.: "Quang Trung và Nguyễn Huệ" → same person
    # E.g.: "Mông Cổ và Nguyên Mông" → same topic
    # Must run BEFORE event retrieval to prepend explanation regardless of data availability
    if has_persons or has_topics or has_dynasties:
        same_person_info = _detect_same_entity(rewritten, resolved)

    # Detect relationship/definition patterns
    # Check both rewritten (accented) and original (may be unaccented) queries
    q_rewritten = rewritten.lower()
    is_relationship = (any(p in q_rewritten for p in RELATIONSHIP_PATTERNS) or
                       any(p in q for p in RELATIONSHIP_PATTERNS))
    is_definition = ("là gì" in q_rewritten or "là ai" in q_rewritten or
                     "la gi" in q or "la ai" in q)

    # Detect if query is IMPLICITLY asking about entity relationship
    # "X và Y" / "X với Y" / "X hay Y" without further context → likely comparing/relating
    # GUARD: Only trigger when connector is BETWEEN the two alias names AND query is
    # short (primarily about identity). Long descriptive queries like
    # "nhà Trần và chiến công chống quân Nguyên Mông" should NOT trigger.
    _CONNECTOR_PATTERNS = [
        re.compile(r'\bvà\b', re.I),
        re.compile(r'\bvới\b', re.I),
        re.compile(r'\bhay\b', re.I),
        re.compile(r'\bvs\.?\b', re.I),
        re.compile(r'\bvoi\b', re.I),    # unaccented "với"
    ]
    is_implicit_relationship = False
    if same_person_info is not None:
        alias_names = same_person_info["names_mentioned"]
        if len(alias_names) >= 2:
            name_a, name_b = alias_names[0], alias_names[1]
            # Find positions in the rewritten (accented) query first, fallback to original
            _check_q = q_rewritten
            pos_a = _check_q.find(name_a)
            pos_b = _check_q.find(name_b)
            if pos_a < 0 or pos_b < 0:
                _check_q = q
                pos_a = _check_q.find(name_a)
                pos_b = _check_q.find(name_b)
            if pos_a >= 0 and pos_b >= 0:
                # Extract text between the two alias names
                if pos_a < pos_b:
                    between_start = pos_a + len(name_a)
                    between_end = pos_b
                else:
                    between_start = pos_b + len(name_b)
                    between_end = pos_a
                between = _check_q[between_start:between_end].strip() if between_start < between_end else ""
                # Connector must sit between the two alias names
                has_connector_between = bool(between) and any(
                    p.search(between) for p in _CONNECTOR_PATTERNS
                )
                # Query must be SHORT — primarily the two names + connector
                # Remove alias names from query and count remaining meaningful words
                q_remaining = _check_q
                for name in alias_names:
                    q_remaining = q_remaining.replace(name, "")
                _FILLER_WORDS = {"và", "với", "hay", "vs", "là", "có", "phải", "không",
                                 "có phải", "gì", "nhau", "một", "cùng"}
                remaining_words = [w for w in q_remaining.split()
                                   if len(w) >= 2 and w.lower() not in _FILLER_WORDS]
                is_short_identity_query = len(remaining_words) <= 3
                is_implicit_relationship = has_connector_between and is_short_identity_query

    if not raw_events:

        if year_range:
            # Year range query: "từ năm 1225 đến 1400"
            start_yr, end_yr = year_range
            intent = "year_range"
            is_range_query = True
            raw_events = scan_by_year_range(start_yr, end_yr)
            # Supplement with semantic search for richer results
            if len(raw_events) < 3:
                raw_events.extend(semantic_search(rewritten))
        elif multi_years:
            # Multiple years: "năm 938 và năm 1288"
            intent = "multi_year"
            is_range_query = True
            for yr in multi_years:
                raw_events.extend(scan_by_year(yr))
            # Also add semantic results for context
            raw_events.extend(semantic_search(rewritten))
        elif same_person_info and (is_relationship or is_definition):
            # Both "là gì của nhau" and "là ai" with both names → same person response
            intent = "relationship"
            is_entity_query = True
            raw_events = scan_by_entities(resolved)

            # --- PERSON-RELEVANCE FILTER ---
            # Keep only docs where the target person appears in doc's persons metadata
            # This prevents docs that merely mention the person in story text (e.g.,
            # "đánh bại Tây Sơn" in Nguyễn dynasty docs) from polluting results
            if has_persons and raw_events:
                target_persons = set(p.lower() for p in resolved["persons"])
                # Also include all aliases for each target person
                target_with_aliases = set(target_persons)
                for alias, canonical in startup.PERSON_ALIASES.items():
                    if canonical in target_persons:
                        target_with_aliases.add(alias)
                filtered = []
                for doc in raw_events:
                    doc_persons = set(p.lower() for p in doc.get("persons", []))
                    if doc_persons & target_with_aliases:
                        filtered.append(doc)
                if filtered:
                    raw_events = filtered

            if 0 < len(raw_events) < 3:
                raw_events.extend(semantic_search(rewritten))
        elif is_definition and has_persons:
            # "X là ai?" — use semantic search as primary, entity scan as supplement
            intent = "definition"
            is_entity_query = True
            raw_events = scan_by_entities(resolved)
            if 0 < len(raw_events) < 3:
                raw_events.extend(semantic_search(rewritten))
        elif has_entities:
            # Multi-entity query (data-driven): person, dynasty, topic, place
            # Determines sub-intent for more specific labeling
            if has_persons and has_dynasties:
                intent = "multi_entity"
            elif has_persons:
                intent = "person"
            elif has_dynasties:
                intent = "dynasty"
                is_dynasty_query = True
            elif has_places:
                intent = "place"
            elif has_topics:
                intent = "topic"
            else:
                intent = "multi_entity"
            
            is_entity_query = True
            # Use inverted index scan for fast O(1) lookup
            raw_events = scan_by_entities(resolved)

            # --- PERSON-RELEVANCE FILTER ---
            # When query specifies persons BUT NOT dynasties, keep only docs where
            # person appears in doc's persons metadata. Skip when dynasties are present
            # because dynasty matching is more reliable (person may be misresolved).
            # E.g., "nhà Trần + chiến công" might misresolve "bà triệu" as person,
            # but dynasty "trần" correctly finds nhà Trần docs.
            if has_persons and not has_dynasties and not has_topics and raw_events:
                target_persons = set(p.lower() for p in resolved["persons"])
                target_with_aliases = set(target_persons)
                for alias, canonical in startup.PERSON_ALIASES.items():
                    if canonical in target_persons:
                        target_with_aliases.add(alias)
                person_filtered = [
                    doc for doc in raw_events
                    if set(p.lower() for p in doc.get("persons", [])) & target_with_aliases
                ]
                # If person filter removed everything, the entity resolution may be wrong
                # → clear results so no_data=true and UI auto-response kicks in
                raw_events = person_filtered

            # --- DYNASTY-AWARE FILTERING ---
            # When query specifies a dynasty, filter out docs from unrelated dynasties
            # Prevents "nhà Nguyễn" docs from leaking into "nhà Trần" queries
            # EXCEPTION: Skip when query contains quốc hiệu (country names like
            # "Đại Việt", "Đại Cồ Việt", "Đại Nam") because these span multiple
            # dynasties and shouldn't be filtered to just one
            QUOC_HIEU = {"đại việt", "đại cồ việt", "đại nam", "việt nam"}
            has_quoc_hieu = bool(
                set(p.lower() for p in resolved.get("places", [])) & QUOC_HIEU
            )
            if has_dynasties and raw_events and not has_quoc_hieu:
                target_dynasties = set(d.lower() for d in resolved["dynasties"])
                filtered = []
                for doc in raw_events:
                    doc_dynasty = doc.get("dynasty", "").strip().lower()
                    # Keep if: no dynasty metadata, OR dynasty matches target
                    if not doc_dynasty or any(td in doc_dynasty or doc_dynasty in td for td in target_dynasties):
                        filtered.append(doc)
                # Only apply filter if it doesn't remove everything
                if filtered:
                    raw_events = filtered

            # --- DYNAMIC KEYWORD RELEVANCE FILTER ---
            # When query has specific action/context keywords, filter events to match
            # E.g.: "chiến công chống Nguyên Mông" → keep only combat-related events
            if raw_events:
                raw_events = _filter_by_query_keywords(rewritten, raw_events)

            # Only supplement with semantic search when entity scan found SOME results
            # but fewer than 3. When entity scan found ZERO results for specific
            # person/entity queries, DON'T fallback — this is a DATA GAP and semantic
            # search will only return noise. Let no_data=true so the UI can respond.
            entity_scan_count = len(raw_events)
            if 0 < entity_scan_count < 3:
                raw_events.extend(semantic_search(rewritten))
        elif is_definition:
            # GROUNDING CHECK: If definition query looks like asking about specific entity
            # but entity resolution found NOTHING, this is likely a DATA GAP (missing person in database).
            # Don't fallback to semantic search → force "no data" to prevent hallucination
            if _looks_like_entity_query(q) and not has_entities:
                # Query looks entity-specific but no entities resolved → data gap
                intent = "no_data"
                raw_events = []  # Force no_data=True to trigger "not found" message
            else:
                intent = "definition"
                raw_events = semantic_search(rewritten)
        else:
            # Use pre-extracted year (with duration guard already applied)
            year = query_analysis.year  # None if duration_guard is True
            if year:
                intent = "year"
                raw_events = scan_by_year(year)
                # If exact year scan found nothing, try semantic search BUT
                # filter to only docs whose year field matches
                if not raw_events:
                    sem_results = semantic_search(rewritten)
                    raw_events = [d for d in sem_results if d.get("year") == year]
                    if not raw_events:
                        # Still nothing → year not in database
                        raw_events = []  # Let no_data=true
            else:
                intent = "semantic"
                raw_events = semantic_search(rewritten)

    # --- IMPLICIT CONTEXT EXPANSION (Intent-Aware) ---
    # Only triggers when intent classifier didn't already resolve the query.
    # If query_analysis was high-confidence, we already have structured results.
    if query_analysis.confidence < 0.8:
        implicit_ctx = expand_query_with_implicit_context(rewritten, resolved)
        if len(raw_events) < 3 and (implicit_ctx["is_vietnam_scope"] or implicit_ctx["has_resistance"]):
            if implicit_ctx["is_broad"] or implicit_ctx["has_resistance"]:
                if not raw_events:
                    intent = "implicit_context"

                # Strategy 1: Search using expanded resistance/event terms
                for extra_query in implicit_ctx["extra_search_queries"]:
                    extra_results = semantic_search(extra_query)
                    raw_events.extend(extra_results)

                # Strategy 2: For very broad queries, scan all documents by dynasty
                if implicit_ctx["is_broad"] and len(raw_events) < 5:
                    for dynasty_key in list(startup.DYNASTY_INDEX.keys()):
                        for idx in startup.DYNASTY_INDEX[dynasty_key][:3]:
                            if idx < len(startup.DOCUMENTS):
                                doc = startup.DOCUMENTS[idx]
                                if doc not in raw_events:
                                    raw_events.append(doc)

                # Strategy 3: Scan by expanded terms in inverted keyword index
                for term in implicit_ctx["expanded_terms"]:
                    term_normalized = term.replace(" ", "_")
                    for idx in startup.KEYWORD_INDEX.get(term, []) + startup.KEYWORD_INDEX.get(term_normalized, []):
                        if idx < len(startup.DOCUMENTS):
                            doc = startup.DOCUMENTS[idx]
                            if doc not in raw_events:
                                raw_events.append(doc)

    # --- FALLBACK CHAIN ---
    # When primary search finds nothing, try harder
    # BUT: if entities were resolved and entity scan found nothing, it's a DATA GAP
    # → don't waste time on semantic search which will return irrelevant results
    if not raw_events and not (is_entity_query and has_entities):
        # Fallback 1: Semantic search with rewritten query
        # (may help if rewrite changed the query significantly)
        if rewritten.lower() != query.lower():
            raw_events = semantic_search(rewritten)
        
        # Fallback 2: Try search variations (entity-focused queries)
        if not raw_events and has_entities:
            variations = generate_search_variations(rewritten, resolved)
            for var_query in variations:
                var_results = semantic_search(var_query)
                if var_results:
                    raw_events.extend(var_results)
                    break  # Use first successful variation
        
        # Fallback 3: Pure semantic search with original query
        if not raw_events and query.lower() != rewritten.lower():
            raw_events = semantic_search(query)

    # --- CONTEXT7 FILTERING & RANKING ---
    # Apply Context7 to filter and rank events based on query relevance
    # This ensures the answer stays focused on the question
    if raw_events:
        raw_events = filter_and_rank_events(raw_events, query, max_results=50)

    # --- NLI ANSWER VALIDATION ---
    # Use NLI model to verify events actually address the question
    # SKIP for entity/dynasty queries — events already passed 4 filter layers:
    #   entity-scan → dynasty filter → keyword filter → cross-encoder
    # NLI is too aggressive for broad queries like "kể về X" and causes
    # false negatives (e.g., removes "Trận Bạch Đằng 1288" from nhà Trần query)
    # Only apply NLI for pure semantic searches where there's no structural match
    if raw_events and not (is_entity_query or is_dynasty_query or is_range_query):
        raw_events = validate_events_nli(query, raw_events)

    # --- STEP 5.5: HARD CONSTRAINT FILTER (Phase 1 / Giai đoạn 11) ---
    # LỚP BẢO VỆ QUAN TRỌNG NHẤT — enforce year/entity/answer_type constraints
    # Runs AFTER NLI to work on already-validated candidates
    if raw_events:
        _answer_validator = AnswerValidator()
        raw_events = _answer_validator.filter_events(query_info, raw_events)

    # --- FINAL RELEVANCE GUARD ---
    # When query mentions specific persons, verify at least one result actually
    # discusses that person. Only check persons that appear in the ORIGINAL query
    # text — entity resolution may produce false matches (e.g., "họ" → "hồ").
    if raw_events and has_persons and resolved.get("persons"):
        query_lower = query.lower()
        # Only validate persons that actually appear in the original query
        query_persons = [p.lower() for p in resolved["persons"] if p.lower() in query_lower]
        
        if query_persons:
            # Check if at least one result mentions the queried person
            has_relevant = False
            for doc in raw_events:
                doc_text = (
                    (doc.get("story", "") or "") + " " +
                    (doc.get("event", "") or "") + " " +
                    (doc.get("title", "") or "") + " " +
                    " ".join(p for p in doc.get("persons", []) or [])
                ).lower()
                for person in query_persons:
                    person_words = person.split()
                    if len(person_words) >= 2 and all(w in doc_text for w in person_words):
                        has_relevant = True
                        break
                    elif len(person_words) == 1 and person in doc_text:
                        has_relevant = True
                        break
                if has_relevant:
                    break
            if not has_relevant:
                raw_events = []  # No doc mentions the queried person → noise

    # --- ĐẠI VIỆT TEMPORAL FILTER ---
    # Quốc hiệu (country names) have known date ranges.
    # Filter events outside the quốc hiệu's temporal bounds to avoid anachronisms.
    QUOC_HIEU_TEMPORAL = {
        "đại việt": (1054, 1804),   # Lý Thánh Tông đổi quốc hiệu 1054 → Gia Long đổi thành Việt Nam 1804
        "đại cồ việt": (968, 1054), # Đinh Tiên Hoàng 968 → Lý Thánh Tông 1054
        "đại nam": (1820, 1945),    # Minh Mạng đổi quốc hiệu → end of Nguyễn dynasty
    }
    if raw_events and resolved.get("places"):
        resolved_places_lower = set(p.lower() for p in resolved["places"])
        for quoc_hieu, (start_yr, end_yr) in QUOC_HIEU_TEMPORAL.items():
            if quoc_hieu in resolved_places_lower:
                # Filter out events outside the quốc hiệu's temporal bounds
                temporal_filtered = [
                    e for e in raw_events
                    if start_yr <= (e.get("year", 0) or 0) <= end_yr
                ]
                # Only apply filter if it keeps at least some results
                if temporal_filtered:
                    raw_events = temporal_filtered
                break  # Only apply one quốc hiệu filter

    no_data = not raw_events

    # Use higher event limit for range/dynasty/entity queries
    if is_range_query:
        max_events = MAX_TOTAL_EVENTS_RANGE
    elif is_dynasty_query:
        max_events = MAX_TOTAL_EVENTS_DYNASTY
    elif is_entity_query:
        max_events = MAX_TOTAL_EVENTS_ENTITY
    else:
        max_events = MAX_TOTAL_EVENTS

    # --- AGGREGATION LAYER: docs → unique events (prevents source-level duplication) ---
    if not no_data and raw_events:
        raw_events = aggregate_events(raw_events)

    # Deduplicate and enrich events (cross-year fuzzy dedup)
    unique_events = deduplicate_and_enrich(raw_events, max_events) if not no_data else []

    # --- CLEAN EVENT TEXT ---
    # Strip builder scaffolding (B1/B2/B3), meta-prompts, and data artifacts
    # from all event text fields BEFORE answer synthesis.
    # This ensures both structured and legacy pipelines get clean data.
    for evt in unique_events:
        year_val = evt.get("year")
        for field in ("event", "story"):
            raw_text = evt.get(field)
            if raw_text and isinstance(raw_text, str) and raw_text.strip():
                cleaned = clean_story_text(raw_text, year_val)
                # Apply year prefix so all pipelines get "Năm XXXX, content"
                if cleaned and year_val:
                    try:
                        yr = int(year_val)
                        if 40 <= yr <= 2025:
                            cleaned = format_timeline_entry(yr, cleaned)
                    except (ValueError, TypeError):
                        pass
                evt[field] = cleaned

    # --- PRONOUN REPLACEMENT ---
    # Replace 2nd+ occurrences of the same person name with ông/bà/Bác
    for evt in unique_events:
        for field in ("event", "story"):
            text = evt.get(field)
            if text and isinstance(text, str) and len(text) >= 10:
                evt[field] = replace_repeated_names(text)



    # --- STEP 7: CONFIDENCE SCORING (Phase 1 / Giai đoạn 11) ---
    # Score events and check if confidence is high enough to answer
    if unique_events:
        unique_events = confidence_scorer.score_events(
            unique_events,
            rerank_weight=RERANK_WEIGHT,
            entailment_weight=ENTAILMENT_WEIGHT,
        )
        # Gate: reject if best confidence < threshold (context-aware)
        if not confidence_scorer.should_answer(unique_events, CONFIDENCE_THRESHOLD, intent=intent):
            # Override no_data — confidence too low
            safe_resp = confidence_scorer.safe_fallback()
            return {
                "query": q_display,
                "intent": intent,
                "answer": safe_resp["answer"],
                "events": unique_events[:3],  # Still return top events for debug
                "no_data": True
            }

    # --- STEP 8: ANSWER SYNTHESIS (Phase 1 / Giai đoạn 11) ---
    # Try new AnswerBuilder → AnswerFormatter pipeline first
    # Falls back to legacy synthesize_answer / format_complete_answer
    answer = None

    if unique_events:
        # Phase 1: Structured answer pipeline
        structured = answer_builder.build_answer(query_info, unique_events)
        if structured:
            formatted = answer_formatter.format_answer(structured, query_info)
            if formatted:
                # Apply LLM rewrite (currently disabled — placeholder)
                _rewriter = RewriteEngine(enabled=USE_LLM_REWRITE)
                answer = _rewriter.rewrite(structured, formatted)

    # Fallback: legacy synthesis
    if not answer:
        synthesized = synthesize_answer(query_analysis, unique_events)
        if synthesized:
            answer = synthesized
        else:
            # Legacy: comprehensive answer formatting
            answer = format_complete_answer(unique_events, group_by=semantic_group_by)

    # --- SPECIAL & QUỐC HIỆU INTRO SENTENCES ---
    # Prepend a poetic, engaging intro based on semantic intent or quốc hiệu
    if answer and not no_data:
        intro_added = False

        # 1) War/resistance intro from semantic intent classification
        if war_intro:
            answer = war_intro + "\n\n" + answer
            intro_added = True

        # 2) Quốc hiệu intros (checked against resolved places)
        if not intro_added:
            _QUOC_HIEU_INTROS = {
                "đại việt": (
                    "**Đại Việt** – biểu tượng của ý chí quật cường và tinh thần bất khuất"
                    " – đã ghi vào lịch sử những chiến tích lẫy lừng;"
                    " chúng ta cùng nhau xem lại vài nét trong bản hùng ca rạng rỡ ấy nhé :"
                ),
                "đại cồ việt": (
                    "**Đại Cồ Việt** – quốc hiệu đầu tiên khẳng định nền độc lập"
                    " – đánh dấu bước ngoặt vĩ đại trong hành trình dựng nước;"
                    " hãy cùng nhìn lại những dấu mốc quan trọng ấy :"
                ),
                "đại nam": (
                    "**Đại Nam** – quốc hiệu thời Nguyễn, biểu trưng cho sự thống nhất"
                    " – chứa đựng bao thăng trầm của lịch sử cận đại;"
                    " hãy cùng khám phá những sự kiện nổi bật :"
                ),
            }
            resolved_places = set(p.lower() for p in resolved.get("places", []))
            for quoc_hieu, intro in _QUOC_HIEU_INTROS.items():
                if quoc_hieu in resolved_places:
                    answer = intro + "\n\n" + answer
                    break

    # Prepend same-entity explanation when:
    # 1. User explicitly asks: "X và Y là gì?" (is_relationship or is_definition)
    # 2. User mentions 2+ alias names with connector: "X và Y", "X với Y"
    # 3. Works with reversed order too: "Nguyễn Huệ và Quang Trung"
    if same_person_info and (is_relationship or is_definition or is_implicit_relationship):
        same_entity_response = _generate_same_entity_response(same_person_info)
        if answer:
            answer = same_entity_response + "\n\n" + answer
        else:
            answer = same_entity_response

    # Remove dangling events label if we don't have any events, but do have same entity response
    if same_person_info and (is_relationship or is_definition or is_implicit_relationship):
        if not unique_events:
            answer = same_entity_response

    # Smart no_data response — suggest alternative phrasing
    if no_data:
        # If we already have a same-entity explanation, don't overwrite it with a generic "no data" message
        if same_person_info and (is_relationship or is_definition or is_implicit_relationship):
            no_data = False
        else:
            answer = _generate_no_data_suggestion(q_display, rewritten, resolved, question_intent)
    
    # --- PHASE 5: OUTPUT VERIFICATION PASS (Guardrails) ---
    # Final quality checks before returning to user.
    # Detects truncation, topic drift, year hallucination.
    # Auto-corrects where possible (severity=AUTO_FIX).
    if answer and not no_data:
        _verifier = OutputVerifier()
        verification = _verifier.verify(answer, query_info)
        if verification.corrected_answer:
            answer = verification.corrected_answer
        if verification.hard_failed:
            print(f"[GUARDRAIL] Hard fail: {[c.message for c in verification.checks if c.severity.value == 'HARD_FAIL']}")
            answer = "Hiện tại tôi chưa tìm được thông tin phù hợp chính xác với câu hỏi này."
            no_data = True
        elif not verification.passed:
            for check in verification.checks:
                if check.message:
                    print(f"[GUARDRAIL] {check.name}: {check.message}")

    # --- LEGACY VALIDATION (Cross-Encoder based) ---
    # Kept as secondary check; NLI validation above is the primary filter
    if answer and not no_data:
        validation = validate_answer_relevance(answer, query)
        if not validation["is_relevant"]:
            pass  # Logged but not acted upon (NLI handles filtering)

    # --- ANSWER-LEVEL DEDUP: final sentence dedup safety net ---
    # Keep strict location answers as-authored; timeline enforcement rewrites
    # "ở đâu" answers into event-style prose and makes them drift again.
    if answer and not no_data:
        if query_info.answer_type_required != "location":
            answer = canonicalize_year_format(answer)
            answer = deduplicate_answer(answer)

    # --- ENTITY NORMALIZATION: alias consistency + truncation fix ---
    if answer and not no_data:
        answer = normalize_entity_names(answer)

    # --- PRONOUN REPLACEMENT on final answer ---
    # Ensures the answer text (from answer synthesis) also uses pronouns
    # But ONLY if it's not a definition/relationship query, to preserve names
    if answer and not no_data and len(answer) >= 10:
        if not (same_person_info and (is_relationship or is_definition or is_implicit_relationship)):
            answer = replace_repeated_names(answer)

    # --- CONFIDENCE & EVIDENCE ATTRIBUTION ---
    best_confidence = 0.0
    evidence_ids = []
    if unique_events and not no_data:
        scored = [e for e in unique_events if e.get("_final_confidence", -1.0) >= 0.0]
        if scored:
            best_confidence = max(e.get("_final_confidence", 0.0) for e in scored)
        evidence_ids = [e.get("id", f"doc_{e.get('year', 'unknown')}_{i:02d}")
                        for i, e in enumerate(unique_events[:5])]

    return {
        "query": q_display,
        "intent": intent,
        "answer": answer,
        "events": unique_events,  # Return deduplicated, enriched events
        "no_data": no_data,
        "confidence": round(best_confidence, 4),
        "evidence_ids": evidence_ids,
    }


def _generate_no_data_suggestion(original_query: str, rewritten: str, resolved: dict, question_intent: str | None) -> str:
    """
    Generate a helpful suggestion when no data is found.
    Instead of just saying "không tìm thấy", guide the user to rephrase.
    """
    suggestions = []
    
    # Check if query was rewritten (means user may have typos)
    if rewritten.lower() != original_query.lower():
        suggestions.append(f"Tôi đã hiểu câu hỏi của bạn là: *\"{rewritten}\"*")
    
    suggestions.append("Tôi chưa tìm thấy thông tin phù hợp. Bạn có thể thử:")
    suggestions.append("")
    suggestions.append("- **Hỏi cụ thể hơn** — ví dụ: *\"Trận Bạch Đằng năm 1288\"*")
    suggestions.append("- **Dùng tên nhân vật** — ví dụ: *\"Trần Hưng Đạo đánh quân Nguyên\"*")
    suggestions.append("- **Nêu triều đại** — ví dụ: *\"Nhà Trần có sự kiện gì nổi bật?\"*")
    suggestions.append("- **Tra theo năm** — ví dụ: *\"Năm 1945 có sự kiện gì?\"*")
    
    return "\n".join(suggestions)
