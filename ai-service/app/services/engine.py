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
MAX_EVENTS_PER_YEAR = 2
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


def compute_similarity(keywords1: set, keywords2: set) -> float:
    """Compute Jaccard similarity between two keyword sets."""
    if not keywords1 or not keywords2:
        return 0.0
    intersection = len(keywords1 & keywords2)
    union = len(keywords1 | keywords2)
    return intersection / union if union > 0 else 0.0


def deduplicate_and_enrich(raw_events: list) -> list:
    """
    Deduplicate events and enrich with complete information.
    Groups similar events, keeps the most comprehensive one, and adds metadata.
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
        used_indices = set()
        year_unique = []
        
        for i, event in enumerate(year_events):
            if i in used_indices:
                continue
            
            # Get event text for comparison
            event_text = event.get("title", "") or event.get("event", "") or event.get("story", "")
            event_keywords = extract_core_keywords(event_text)
            
            # Collect all related events and merge their info
            best_event = dict(event)
            best_story = event.get("story", "") or event.get("event", "")
            all_persons = set(event.get("persons", []))
            all_places = set(event.get("places", []))
            all_keywords = set(event.get("keywords", []))
            
            for j, other in enumerate(year_events):
                if j <= i or j in used_indices:
                    continue
                
                other_text = other.get("title", "") or other.get("event", "") or other.get("story", "")
                other_keywords = extract_core_keywords(other_text)
                
                similarity = compute_similarity(event_keywords, other_keywords)
                
                # If similar (>40% overlap), merge information
                if similarity > 0.4:
                    used_indices.add(j)
                    
                    # Collect persons, places, keywords from all versions
                    all_persons.update(other.get("persons", []))
                    all_places.update(other.get("places", []))
                    all_keywords.update(other.get("keywords", []))
                    
                    # Keep the longest story
                    other_story = other.get("story", "") or other.get("event", "")
                    if len(other_story) > len(best_story):
                        best_story = other_story
                        best_event = dict(other)
            
            used_indices.add(i)
            
            # Create enriched event with merged info
            enriched = {
                "year": year,
                "title": best_event.get("title", ""),
                "event": best_event.get("event", ""),
                "story": best_story,
                "persons": list(all_persons),
                "places": list(all_places),
                "keywords": list(all_keywords),
                "tone": best_event.get("tone", ""),
                "dynasty": best_event.get("dynasty", "")
            }
            
            year_unique.append(enriched)
            
            if len(year_unique) >= MAX_EVENTS_PER_YEAR:
                break
        
        result_events.extend(year_unique)
        
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
