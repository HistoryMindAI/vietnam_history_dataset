from app.services.search_service import semantic_search, scan_by_year
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

# Maximum events per year to prevent verbose responses  
MAX_EVENTS_PER_YEAR = 1
MAX_TOTAL_EVENTS = 5

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


def clean_story_text(text: str) -> str:
    """
    Clean up story text by removing redundant prefixes and making it a complete sentence.
    """
    if not text:
        return ""
    
    # Remove common redundant prefixes
    patterns_to_remove = [
        r'^Năm \d+[,:]?\s*',                    # "Năm 1911, "
        r'^Vào năm \d+[,:]?\s*',                # "Vào năm 1911, "
        r'^năm \d+[,:]?\s*',                    # "năm 1911, "
        r'^\d+:\s*',                            # "1911: "
        r'^gắn mốc \d+ với\s*',                 # "gắn mốc 1911 với"
        r'^Câu hỏi nhắm tới sự kiện\s*',        # Technical prefix
        r'^Tóm tắt bối cảnh – diễn biến – kết quả của\s*',
        r'^Kể về .+ và đóng góp của .+ trong\s*',
        r'diễn ra năm \d+[.;]?\s*',             # "diễn ra năm 1911"
        r'xảy ra năm \d+[.;]?\s*',              # "xảy ra năm 1911"
    ]
    
    result = text.strip()
    for pattern in patterns_to_remove:
        result = re.sub(pattern, '', result, flags=re.IGNORECASE)
    
    # Remove duplicate year mentions
    result = re.sub(r'\(\d{4}\)[.:,]?\s*$', '', result)  # Remove trailing (1911).
    
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

def deduplicate_and_enrich(raw_events: list) -> list:
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
                    if sim > 0.5: # Aggressive threshold
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
            
        if len(result_events) >= MAX_TOTAL_EVENTS:
            break
            
    return result_events[:MAX_TOTAL_EVENTS]


def format_complete_answer(events: list) -> str:
    """
    Format events into a complete, comprehensive answer.
    Creates full sentences with all relevant information.
    """
    if not events:
        return None
    
    paragraphs = []
    
    for e in events:
        year = e.get("year", "")
        story = e.get("story", "") or e.get("event", "")
        persons = e.get("persons", [])
        places = e.get("places", [])
        dynasty = e.get("dynasty", "")
        
        # Clean the story text
        clean_story = clean_story_text(story)
        
        if not clean_story:
            continue
        
        # Build a complete paragraph
        parts = []
        
        # Main event description with year
        if year:
            # Check if story already starts with event name
            if clean_story[0].isupper():
                parts.append(f"Năm {year}, {clean_story[0].lower()}{clean_story[1:]}")
            else:
                parts.append(f"Năm {year}, {clean_story}")
        else:
            parts.append(clean_story)
        
        # Add persons if available and not already in story
        if persons:
            persons_str = ", ".join(persons)
            if not any(p.lower() in clean_story.lower() for p in persons):
                parts.append(f"Nhân vật liên quan: {persons_str}.")
        
        # Add places if available and not already in story  
        if places:
            places_str = ", ".join(places)
            if not any(p.lower() in clean_story.lower() for p in places):
                parts.append(f"Địa điểm: {places_str}.")
        
        # Add dynasty context if available
        if dynasty and dynasty not in clean_story:
            parts.append(f"Thời kỳ: {dynasty}.")
        
        paragraph = " ".join(parts)
        
        # Ensure paragraph ends with period
        if not paragraph.endswith(('.', '!', '?')):
            paragraph += "."
        
        paragraphs.append(paragraph)
    
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

    # Detect intent
    if "là gì" in q or "là ai" in q:
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

    # Deduplicate and enrich events
    unique_events = deduplicate_and_enrich(raw_events) if not no_data else []
    
    # Generate complete, comprehensive answer
    answer = format_complete_answer(unique_events)

    return {
        "query": query,
        "intent": intent,
        "answer": answer,
        "events": unique_events,  # Return deduplicated, enriched events
        "no_data": no_data
    }
