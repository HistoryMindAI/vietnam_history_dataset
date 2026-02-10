from app.services.search_service import semantic_search, scan_by_year, detect_dynasty_from_query, detect_place_from_query
import re

# Pre-compile regex for faster matching
YEAR_PATTERN = re.compile(r"(?<![\d-])([1-9][0-9]{1,3})(?!\d)")

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

MAX_EVENTS_PER_YEAR = 1
MAX_TOTAL_EVENTS = 5
MAX_TOTAL_EVENTS_DYNASTY = 10  # More results for dynasty-level queries

# Identity patterns - moved from FE
IDENTITY_PATTERNS = [
    "who are you", "bạn là ai", "giới thiệu", 
    "what is your name", "tên bạn là gì"
]

IDENTITY_RESPONSE = (
    "Xin chào, tôi là History Mind AI. "
    "Tôi ở đây để giúp bạn tìm hiểu về lịch sử Việt Nam và thế giới. "
    "Bạn có câu hỏi nào không?"
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

    # Handle identity queries (moved from FE)
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

    # Detect intent
    dynasty = detect_dynasty_from_query(query)
    place = detect_place_from_query(query)
    
    if dynasty or place:
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

    # Use higher event limit for dynasty/place queries
    max_events = MAX_TOTAL_EVENTS_DYNASTY if is_dynasty_query else MAX_TOTAL_EVENTS

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
