from app.services.search_service import (
    semantic_search, scan_by_year, scan_by_year_range,
    detect_dynasty_from_query, detect_place_from_query,
    resolve_query_entities, scan_by_entities,
    scan_by_dynasty_timeline, scan_national_resistance,
    scan_territorial_conflicts, scan_civil_wars, scan_broad_history,
    DYNASTY_ORDER,
)
from app.services.query_understanding import (
    rewrite_query, extract_question_intent,
    generate_search_variations,
)
from app.services.cross_encoder_service import (
    filter_and_rank_events,
    validate_answer_relevance,
)
from app.services.nli_validator_service import validate_events_nli
from app.services.semantic_intent import (
    classify_semantic_intent, SemanticIntent,
)
from app.services.implicit_context import (
    expand_query_with_implicit_context,
    filter_discriminating_keywords,
    is_vietnam_scope_query,
    is_broad_vietnam_query,
    has_resistance_terms,
    NON_DISCRIMINATING_KEYWORDS,
)
import app.core.startup as startup
import re

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
    
    result = text.strip()
    
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
    
    return result.strip()


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
    Uses multiple strategies: containment, SequenceMatcher, and keyword overlap.
    """
    # Strategy 1: Direct containment
    if text1_lower in text2_lower or text2_lower in text1_lower:
        return True
    
    # Strategy 2: SequenceMatcher similarity
    sim = compute_text_similarity(text1_lower, text2_lower)
    if sim > 0.6:
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
        if year not in by_year:
            by_year[year] = []
        by_year[year].append(e)
    
    # Global cluster for cross-year dedup
    global_cluster = []  # [{"event": doc, "text": cleaned, "text_lower": lower, "keywords": set}]
    
    for year in sorted(by_year.keys()):
        year_events = by_year[year]
        if not year_events:
            continue

        # Sort by content length (descending) to prefer longer, detailed stories as base 
        year_events.sort(key=lambda x: len(x.get("story", "") or x.get("event", "")), reverse=True)
        
        for event in year_events:
            event_text = clean_story_text(event.get("story", "") or event.get("event", ""))
            
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


def _format_event_text(e: dict, year=None, seen_texts: set = None) -> str | None:
    """Format a single event into clean text. Returns None if duplicate."""
    story = e.get("story", "") or e.get("event", "")
    clean_story = clean_story_text(story, year)

    if not clean_story:
        return None

    title = e.get("title", "")
    clean_title = clean_story_text(title, year) if title else ""

    if clean_title and clean_story and clean_title.lower() != clean_story.lower():
        if not _is_question_title(clean_title):
            if clean_title.lower() not in clean_story.lower():
                clean_story = f"{clean_title}: {clean_story}"

    clean_story = clean_story[0].upper() + clean_story[1:]
    if not clean_story.endswith(('.', '!', '?')):
        clean_story += "."

    dedup_key = re.sub(r'[^\w\s]', '', clean_story.lower()).strip()
    dedup_key = re.sub(r'\s+', ' ', dedup_key)

    if seen_texts is not None:
        if dedup_key in seen_texts:
            return None
        seen_texts.add(dedup_key)

    return clean_story


def _format_by_year(events: list) -> str | None:
    """Group events by year (original behavior)."""
    by_year = {}
    for e in events:
        year = e.get("year")
        if year not in by_year:
            by_year[year] = []
        by_year[year].append(e)

    paragraphs = []
    sorted_years = sorted(by_year.keys()) if all(isinstance(y, int) for y in by_year.keys() if y) else by_year.keys()
    seen_texts = set()

    for year in sorted_years:
        event_texts = []
        for e in by_year[year]:
            text = _format_event_text(e, year, seen_texts)
            if text:
                event_texts.append(text)
        if event_texts:
            joined = " ".join(event_texts)
            if year:
                paragraphs.append(f"**Năm {year}:** {joined}")
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
    seen_texts = set()

    for dynasty in DYNASTY_ORDER:
        dynasty_events = by_dynasty.get(dynasty, [])
        if not dynasty_events:
            continue

        # Sort events within dynasty by year
        dynasty_events.sort(key=lambda d: d.get("year", 9999))

        event_texts = []
        for e in dynasty_events:
            text = _format_event_text(e, e.get("year"), seen_texts)
            if text:
                event_texts.append(text)

        if event_texts:
            # Create dynasty header with year range
            years = [e.get("year") for e in dynasty_events if e.get("year")]
            if years:
                year_range = f"{min(years)}–{max(years)}" if min(years) != max(years) else str(min(years))
                header = f"**{dynasty} ({year_range}):**"
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

    # Find the maximum score achieved
    max_score = max(s for _, s in scored)
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

    response = f"{names_str} là **{same_label}**.\n\n"
    response += f"{main_label}: **{canonical.title()}**\n\n"

    if all_aliases:
        alias_str = ", ".join(a.title() for a in all_aliases)
        response += f"{alias_label}: {alias_str}\n\n"

    response += "---\n\nDưới đây là các sự kiện liên quan:"
    return response


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

    # --- STEP 1.5: SEMANTIC INTENT CLASSIFICATION ---
    # Classify query BEFORE keyword-based intent chain.
    # High-confidence semantic intents shortcircuit directly to structured retrieval.
    semantic_intent = classify_semantic_intent(rewritten, resolved)

    if semantic_intent.confidence >= 0.8:
        if semantic_intent.intent == "dynasty_timeline":
            intent = "dynasty_timeline"
            is_dynasty_query = True
            raw_events = scan_by_dynasty_timeline()
            semantic_group_by = "dynasty"
        elif semantic_intent.intent == "resistance_national":
            intent = "resistance_national"
            is_entity_query = True
            raw_events = scan_national_resistance()
        elif semantic_intent.intent == "territorial_event":
            intent = "territorial_event"
            is_entity_query = True
            raw_events = scan_territorial_conflicts()
        elif semantic_intent.intent == "civil_war":
            intent = "civil_war"
            is_entity_query = True
            raw_events = scan_civil_wars()
        elif semantic_intent.intent == "broad_history":
            intent = "broad_history"
            is_dynasty_query = True
            raw_events = scan_broad_history()

    # If semantic intent resolved with results, skip legacy intent chain
    # Otherwise, fall through to existing keyword/entity-based logic
    year_range = None
    multi_years = None

    if not raw_events:
        # Detect intent — priority: year_range > multi_year > relationship > definition > entity > single_year > semantic
        year_range = extract_year_range(rewritten)
        multi_years = extract_multiple_years(rewritten)

        # --- SAME-ENTITY DETECTION (Dynamic) ---
        # Detects if 2+ names in query refer to same entity (person, topic, or dynasty)
        # E.g.: "Quang Trung và Nguyễn Huệ" → same person
        # E.g.: "Mông Cổ và Nguyên Mông" → same topic
        if has_persons or has_topics or has_dynasties:
            same_person_info = _detect_same_entity(rewritten, resolved)

        # Detect relationship/definition patterns
        # Check both rewritten (accented) and original (may be unaccented) queries
        q_rewritten = rewritten.lower()
        is_relationship = (any(p in q_rewritten for p in RELATIONSHIP_PATTERNS) or
                           any(p in q for p in RELATIONSHIP_PATTERNS))
        is_definition = ("là gì" in q_rewritten or "là ai" in q_rewritten or
                         "la gi" in q or "la ai" in q)

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
            intent = "definition"
            raw_events = semantic_search(rewritten)
        else:
            year = extract_single_year(rewritten)
            if year:
                intent = "year"
                raw_events = scan_by_year(year)
            else:
                intent = "semantic"
                raw_events = semantic_search(rewritten)

    # --- IMPLICIT CONTEXT EXPANSION (Semantic-Intent-Aware) ---
    # Only triggers when semantic intent didn't already resolve the query.
    # If semantic_intent was high-confidence, we already have structured results.
    if semantic_intent.confidence < 0.8:
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

    # Deduplicate and enrich events
    unique_events = deduplicate_and_enrich(raw_events, max_events) if not no_data else []
    
    # Generate complete, comprehensive answer
    answer = format_complete_answer(unique_events, group_by=semantic_group_by)

    # --- SPECIAL & QUỐC HIỆU INTRO SENTENCES ---
    # Prepend a poetic, engaging intro based on query keywords or quốc hiệu
    if answer and not no_data:
        intro_added = False

        # 1) Keyword-based special intros (checked against original query text)
        _KEYWORD_INTROS = {
            "chiến tranh việt nam": (
                'Bạn đang muốn tìm hiểu về: "Kháng chiến chống giặc ngoại xâm'
                " – bản hùng ca giữ nước vang vọng suốt chiều dài"
                ' lịch sử dân tộc Việt Nam ta."'
            ),
        }
        query_lower = query.lower()
        for keyword, intro in _KEYWORD_INTROS.items():
            if keyword in query_lower:
                answer = intro + "\n\n" + answer
                intro_added = True
                break

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

    # Prepend same-entity explanation ONLY when user explicitly asks about relationship
    # "Quang Trung và Nguyễn Huệ là gì?" → show same-entity
    # "Kể tên chiến công chống quân Nguyên Mông" → DON'T show same-entity
    if same_person_info and (is_relationship or is_definition) and answer:
        same_entity_response = _generate_same_entity_response(same_person_info)
        answer = same_entity_response + "\n\n" + answer
    elif same_person_info and (is_relationship or is_definition) and not answer:
        answer = _generate_same_entity_response(same_person_info)

    # Smart no_data response — suggest alternative phrasing
    if no_data:
        answer = _generate_no_data_suggestion(q_display, rewritten, resolved, question_intent)
    
    # --- LEGACY VALIDATION (Cross-Encoder based) ---
    # Kept as secondary check; NLI validation above is the primary filter
    if answer and not no_data:
        validation = validate_answer_relevance(answer, query)
        if not validation["is_relevant"]:
            pass  # Logged but not acted upon (NLI handles filtering)

    return {
        "query": q_display,
        "intent": intent,
        "answer": answer,
        "events": unique_events,  # Return deduplicated, enriched events
        "no_data": no_data
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
