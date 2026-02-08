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

# Maximum stories to return to prevent verbose responses
MAX_STORIES = 3

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


def normalize_event_signature(event: str) -> str:
    """
    Create a normalized signature from event text for deduplication.
    Takes first 50 chars, lowercase, removes extra spaces.
    """
    if not event:
        return ""
    return re.sub(r'\s+', ' ', event.lower().strip())[:50]


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
    events = []

    # Detect intent
    if "là gì" in q or "là ai" in q:
        intent = "definition"
        events = semantic_search(query)
    else:
        year = extract_single_year(query)
        if year:
            intent = "year"
            events = scan_by_year(year)
        else:
            intent = "semantic"
            events = semantic_search(query)

    no_data = not events

    # Generate answer from found events
    answer = None
    if not no_data:
        # Deduplicate by normalized event signature (not exact story match)
        seen_signatures = set()
        unique_stories = []

        # Sort events by year
        for e in sorted(events, key=lambda x: x.get("year", 0)):
            event_text = e.get("event", "")
            sig = normalize_event_signature(event_text)
            
            if sig and sig not in seen_signatures:
                seen_signatures.add(sig)
                # Prefer story if available, fallback to event
                story = e.get("story") or event_text
                if story:
                    unique_stories.append(story)
                    # Limit output to prevent verbose responses
                    if len(unique_stories) >= MAX_STORIES:
                        break

        if unique_stories:
            answer = "\n".join(unique_stories)

    return {
        "query": query,
        "intent": intent,
        "answer": answer,
        "events": events,
        "no_data": no_data
    }
