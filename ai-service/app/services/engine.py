from app.services.search_service import semantic_search, scan_by_year, scan_by_year_range, detect_dynasty_from_query, detect_place_from_query
import re

# Pre-compile regex for faster matching
YEAR_PATTERN = re.compile(r"(?<![\d-])([1-9][0-9]{1,3})(?!\d)")

# Year range: "từ năm 1225 đến năm 1400", "từ 1225 đến 1400", "giai đoạn 1225-1400"
YEAR_RANGE_PATTERN = re.compile(
    r"(?:từ\s*(?:năm\s*)?|giai\s*đoạn\s*)"
    r"(\d{3,4})"
    r"\s*(?:đến|tới|[-–—])\s*(?:năm\s*)?"
    r"(\d{3,4})",
    re.IGNORECASE
)


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
    Extracts a year range from text (e.g., 'từ năm 1225 đến 1400').
    Returns (start_year, end_year) or None.
    """
    m = YEAR_RANGE_PATTERN.search(text)
    if m:
        start = int(m.group(1))
        end = int(m.group(2))
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
]

IDENTITY_RESPONSE = (
    "## 🏛️ Xin chào! Tôi là **History Mind AI** — Trợ lý Lịch sử Việt Nam.\n\n"
    "Tôi được sinh ra từ niềm đam mê với **4.000 năm lịch sử dân tộc Việt Nam**, "
    "với sứ mệnh giúp mọi người tiếp cận và khám phá di sản lịch sử một cách dễ dàng, "
    "chính xác và sinh động.\n\n"
    "### 📚 Tôi có thể giúp bạn:\n"
    "- 🔍 **Tra cứu sự kiện** theo năm, triều đại, hoặc nhân vật\n"
    "- 📖 **Kể chuyện lịch sử** từ thời Hùng Vương đến hiện đại\n"
    "- ⚔️ **Phân tích chiến công** — Bạch Đằng, Chi Lăng, Điện Biên Phủ...\n"
    "- 🏰 **Tìm hiểu triều đại** — Lý, Trần, Lê, Nguyễn...\n"
    "- 📅 **So sánh giai đoạn** — từ năm X đến năm Y\n\n"
    "Hãy hỏi tôi bất cứ điều gì về lịch sử Việt Nam! 🇻🇳"
)

CREATOR_RESPONSE = (
    "## 🛠️ Ai đã tạo ra tôi?\n\n"
    "Tôi — **History Mind AI** — được xây dựng bởi **đội ngũ HistoryMindAI**, "
    "một nhóm sinh viên và kỹ sư đam mê công nghệ AI và lịch sử Việt Nam.\n\n"
    "### 🧠 Công nghệ đằng sau tôi:\n"
    "- **AI & NLP**: Sử dụng mô hình ngôn ngữ và tìm kiếm ngữ nghĩa (Semantic Search) "
    "để hiểu câu hỏi của bạn bằng tiếng Việt tự nhiên\n"
    "- **FAISS + Embeddings**: Tìm kiếm vector nhanh chóng trong hàng nghìn sự kiện lịch sử\n"
    "- **Dữ liệu**: Được huấn luyện trên bộ dữ liệu lịch sử Việt Nam gồm hơn 50.000 mẫu, "
    "bao phủ từ thời kỳ Hùng Vương dựng nước đến hiện đại\n\n"
    "### 🎯 Sứ mệnh:\n"
    "Mang lịch sử Việt Nam đến gần hơn với mọi người thông qua công nghệ AI, "
    "giúp thế hệ trẻ hiểu và trân trọng di sản văn hóa dân tộc.\n\n"
    "💡 *Hãy thử hỏi tôi: \"Trận Bạch Đằng 938 diễn ra như thế nào?\"*"
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

def deduplicate_and_enrich(raw_events: list, max_events: int = MAX_TOTAL_EVENTS) -> list:
    """
    Deduplicate events and enrich with complete information.
    Aggressively merges similar events to prevent repetition.
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
    
    result_events = []
    
    for year in sorted(by_year.keys()):
        year_events = by_year[year]
        if not year_events:
            continue

        # Sort by content length (descending) to prefer longer, detailed stories as base 
        year_events.sort(key=lambda x: len(x.get("story", "") or x.get("event", "")), reverse=True)
        
        unique_cluster = []
        
        for event in year_events:
            event_text = clean_story_text(event.get("story", "") or event.get("event", ""))
            event_lower = event_text.lower()
            
            is_duplicate = False
            
            for cluster_item in unique_cluster:
                base_event = cluster_item["event"]
                base_text = clean_story_text(base_event.get("story", "") or base_event.get("event", ""))
                base_lower = base_text.lower()
                
                # Check for containment or high similarity
                if (event_lower in base_lower or base_lower in event_lower):
                    is_duplicate = True
                else:
                    sim = compute_text_similarity(event_lower, base_lower)
                    if sim > 0.5:  # Tuned threshold: 0.3 too aggressive, 0.6 too loose
                        is_duplicate = True
                
                if is_duplicate:
                    # Merge info into base_event (the longer one usually)
                    # Merge persons/places
                    current_persons = set(base_event.get("persons", []))
                    current_persons.update(event.get("persons", []))
                    base_event["persons"] = list(current_persons)
                    
                    current_places = set(base_event.get("places", []))
                    current_places.update(event.get("places", []))
                    base_event["places"] = list(current_places)
                    
                    # Keep the absolute longest story text
                    if len(event_text) > len(base_text):
                         base_event["story"] = event.get("story", "")
                         base_event["event"] = event.get("event", "")
                    
                    break # Found a match, stop checking other clusters
            
            if not is_duplicate:
                unique_cluster.append({"event": event, "text": event_text})
        
        # Add enriched unique events from this year
        for item in unique_cluster:
            result_events.append(item["event"])
            
        if len(result_events) >= max_events:
            break
            
    return result_events[:max_events]


def format_complete_answer(events: list) -> str:
    """
    Format events into a concise answer, grouped by year.
    Avoids duplication and produces natural-sounding Vietnamese text.
    """
    if not events:
        return None
    
    # Group by year for cleaner output
    by_year = {}
    for e in events:
        year = e.get("year")
        if year not in by_year:
            by_year[year] = []
        by_year[year].append(e)
    
    paragraphs = []
    
    # Sort years
    sorted_years = sorted(by_year.keys()) if all(isinstance(y, int) for y in by_year.keys() if y) else by_year.keys()
    
    seen_texts = set()  # Prevent exact duplicate sentences across years
    
    for year in sorted_years:
        year_events = by_year[year]
        event_texts = []
        
        for e in year_events:
            # Prefer story (longer, more detailed), fallback to event
            story = e.get("story", "") or e.get("event", "")
            clean_story = clean_story_text(story, year)
            
            # Skip if empty
            if not clean_story:
                continue
            
            # Extract title for context if available
            title = e.get("title", "")
            clean_title = clean_story_text(title, year) if title else ""
            
            # If story is very short or same as title, try to combine
            if clean_title and clean_story and clean_title.lower() != clean_story.lower():
                # Check if title is already part of the story
                if clean_title.lower() not in clean_story.lower():
                    clean_story = f"{clean_title}: {clean_story}"
            
            # Capitalize first letter
            clean_story = clean_story[0].upper() + clean_story[1:]
            
            # Ensure ends with punctuation
            if not clean_story.endswith(('.', '!', '?')):
                clean_story += "."
            
            # Dedup check AFTER normalization so key is consistent
            dedup_key = clean_story.lower().strip()
            if dedup_key in seen_texts:
                continue
            seen_texts.add(clean_story.lower())
            event_texts.append(clean_story)
        
        if event_texts:
            joined_events = " ".join(event_texts)
            if year:
                paragraphs.append(f"**Năm {year}:** {joined_events}")
            else:
                paragraphs.append(joined_events)
            
    return "\n\n".join(paragraphs) if paragraphs else None


def engine_answer(query: str):
    q = query.lower()

    # Handle creator queries — "ai tạo ra bạn?", "ai phát triển bạn?"
    # Check BEFORE identity to avoid 'bạn là ai' substring matching
    if any(pattern in q for pattern in CREATOR_PATTERNS):
        return {
            "query": query,
            "intent": "creator",
            "answer": CREATOR_RESPONSE,
            "events": [],
            "no_data": False
        }

    # Handle identity queries — "bạn là ai?", "giới thiệu bản thân"
    if any(pattern in q for pattern in IDENTITY_PATTERNS):
        return {
            "query": query,
            "intent": "identity",
            "answer": IDENTITY_RESPONSE,
            "events": [],
            "no_data": False
        }

    intent = "semantic"
    raw_events = []
    is_dynasty_query = False
    is_range_query = False

    # Detect intent — priority: year_range > multi_year > dynasty > definition > single_year > semantic
    year_range = extract_year_range(query)
    multi_years = extract_multiple_years(query)
    dynasty = detect_dynasty_from_query(query)
    place = detect_place_from_query(query)

    if year_range:
        # Year range query: "từ năm 1225 đến 1400"
        start_yr, end_yr = year_range
        intent = "year_range"
        is_range_query = True
        raw_events = scan_by_year_range(start_yr, end_yr)
        # Supplement with semantic search for richer results
        if len(raw_events) < 3:
            raw_events.extend(semantic_search(query))
    elif multi_years:
        # Multiple years: "năm 938 và năm 1288"
        intent = "multi_year"
        is_range_query = True
        for yr in multi_years:
            raw_events.extend(scan_by_year(yr))
        # Also add semantic results for context
        raw_events.extend(semantic_search(query))
    elif dynasty or place:
        # Dynasty/place query — use semantic search with filters
        intent = "dynasty" if dynasty else "place"
        is_dynasty_query = True
        raw_events = semantic_search(query)
    elif "là gì" in q or "là ai" in q:
        intent = "definition"
        raw_events = semantic_search(query)
    else:
        year = extract_single_year(query)
        if year:
            intent = "year"
            raw_events = scan_by_year(year)
        else:
            intent = "semantic"
            raw_events = semantic_search(query)

    no_data = not raw_events

    # Use higher event limit for range/dynasty queries
    if is_range_query:
        max_events = MAX_TOTAL_EVENTS_RANGE
    elif is_dynasty_query:
        max_events = MAX_TOTAL_EVENTS_DYNASTY
    else:
        max_events = MAX_TOTAL_EVENTS

    # Deduplicate and enrich events
    unique_events = deduplicate_and_enrich(raw_events, max_events) if not no_data else []
    
    # Generate complete, comprehensive answer
    answer = format_complete_answer(unique_events)

    return {
        "query": query,
        "intent": intent,
        "answer": answer,
        "events": unique_events,  # Return deduplicated, enriched events
        "no_data": no_data
    }
