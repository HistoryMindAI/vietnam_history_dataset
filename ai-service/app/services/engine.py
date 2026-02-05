from app.services.search_service import semantic_search, scan_by_year
import re

def extract_single_year(text: str):
    m = re.search(r"(1[0-9]{3})", text)
    return int(m.group(1)) if m else None


def engine_answer(query: str):
    q = query.lower()

    intent = "semantic"
    events = []

    # definition intent
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

    no_data = len(events) == 0

    return {
        "query": query,
        "intent": intent,
        "answer": None,      # ⛔ FastAPI KHÔNG sinh văn bản
        "events": events,
        "no_data": no_data
    }
