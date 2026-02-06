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


def engine_answer(query: str):
    q = query.lower()

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

    # Sinh câu trả lời từ các sự kiện tìm được
    answer = None
    if not no_data:
        # Optimization: Use a set for O(1) deduplication and maintain order
        seen_stories = set()
        unique_stories = []

        # Sort events by year once
        for e in sorted(events, key=lambda x: x.get("year", 0)):
            story = e.get("story")
            if story and story not in seen_stories:
                seen_stories.add(story)
                unique_stories.append(story)

        if unique_stories:
            answer = "\n".join(unique_stories)

    return {
        "query": query,
        "intent": intent,
        "answer": answer,
        "events": events,
        "no_data": no_data
    }
