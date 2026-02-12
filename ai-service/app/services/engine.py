from app.services.search_service import (
    semantic_search, scan_by_year, scan_by_year_range,
    detect_dynasty_from_query, detect_place_from_query,
    resolve_query_entities, scan_by_entities,
)
from app.services.query_understanding import (
    rewrite_query, extract_question_intent,
    generate_search_variations,
)
import app.core.startup as startup
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


def _strip_accents(text: str) -> str:
    """Strip Vietnamese diacritical marks for fuzzy matching."""
    import unicodedata
    nfkd = unicodedata.normalize('NFKD', text)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


def _detect_same_person(query: str, resolved: dict) -> dict | None:
    """
    Detect if query mentions multiple names that are actually the same person.
    Handles both accented and unaccented queries.
    Returns {"canonical": str, "names_mentioned": list, "all_aliases": list} or None.
    """
    q_low = query.lower()
    q_stripped = _strip_accents(q_low)

    # Build complete name → canonical mapping
    name_to_canonical = dict(startup.PERSON_ALIASES)  # alias → canonical
    # Add canonical → canonical for self-references
    for canonical in set(startup.PERSON_ALIASES.values()):
        name_to_canonical[canonical] = canonical
    # Also include person index keys
    for person_key in startup.PERSONS_INDEX:
        if person_key not in name_to_canonical:
            name_to_canonical[person_key] = person_key

    # Find all names mentioned in query (longest-first to avoid partial matches)
    # Try both accented and stripped versions
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
        # Check if 2+ distinct names resolve to same canonical person
        canonical_set = set(m[1] for m in filtered)
        if len(canonical_set) == 1:
            canonical = list(canonical_set)[0]
            all_aliases = [alias for alias, can in startup.PERSON_ALIASES.items()
                          if can == canonical and alias != canonical]
            return {
                "canonical": canonical,
                "names_mentioned": [m[0] for m in filtered],
                "all_aliases": all_aliases,
            }

    return None


def _generate_same_person_response(info: dict) -> str:
    """Generate a response explaining two names refer to the same person."""
    canonical = info["canonical"]
    names = info["names_mentioned"]
    all_aliases = info["all_aliases"]

    # Format the names mentioned
    name_parts = [f"**{n.title()}**" for n in names]
    names_str = " và ".join(name_parts)

    response = f"{names_str} là **cùng một người**.\n\n"
    response += f"Tên chính: **{canonical.title()}**\n"

    if all_aliases:
        alias_str = ", ".join(a.title() for a in all_aliases)
        response += f"Các tên gọi khác: {alias_str}\n"

    response += "\n---\n\nDưới đây là các sự kiện liên quan:"
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

    # Detect intent — priority: year_range > multi_year > relationship > definition > entity > single_year > semantic
    year_range = extract_year_range(rewritten)
    multi_years = extract_multiple_years(rewritten)

    # Dynamic entity resolution (data-driven, no hardcoded patterns)
    # Uses rewritten query for better entity matching
    resolved = resolve_query_entities(rewritten)
    has_persons = bool(resolved.get("persons"))
    has_topics = bool(resolved.get("topics"))
    has_dynasties = bool(resolved.get("dynasties"))
    has_places = bool(resolved.get("places"))
    has_entities = has_persons or has_topics or has_dynasties or has_places

    # --- SAME-PERSON DETECTION ---
    # "Quang Trung và Nguyễn Huệ là gì của nhau?" → same person
    if has_persons:
        same_person_info = _detect_same_person(rewritten, resolved)

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
    elif same_person_info and is_relationship:
        # "Quang Trung và Nguyễn Huệ là gì của nhau?" → explain same person
        # NOTE: "QT và NH là ai?" falls through to definition branch (normal events)
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

        if len(raw_events) < 3:
            raw_events.extend(semantic_search(rewritten))
    elif is_definition and has_persons:
        # "X là ai?" — use semantic search as primary, entity scan as supplement
        intent = "definition"
        is_entity_query = True
        raw_events = scan_by_entities(resolved)
        if len(raw_events) < 3:
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

        # --- DYNASTY-AWARE FILTERING ---
        # When query specifies a dynasty, filter out docs from unrelated dynasties
        # Prevents "nhà Nguyễn" docs from leaking into "nhà Trần" queries
        if has_dynasties and raw_events:
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

        # Only supplement with semantic search when entity scan returns too few
        if len(raw_events) < 3:
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
    answer = format_complete_answer(unique_events)

    # Prepend same-person explanation ONLY for relationship queries
    # "là ai" (definition) should return normal events without same-person header
    if same_person_info and intent == "relationship" and answer:
        same_person_response = _generate_same_person_response(same_person_info)
        answer = same_person_response + "\n\n" + answer
    elif same_person_info and intent == "relationship" and not answer:
        answer = _generate_same_person_response(same_person_info)

    # Smart no_data response — suggest alternative phrasing
    if no_data:
        answer = _generate_no_data_suggestion(q_display, rewritten, resolved, question_intent)

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
