from app.services.search_service import semantic_search, scan_by_year
import re

def extract_single_year(text: str):
    # Hỗ trợ tìm năm từ 40 đến 2025
    m = re.search(r"(?<![\d-])([1-9][0-9]{1,3})(?!\d)", text)
    if m:
        year = int(m.group(1))
        if 40 <= year <= 2025:
            return year
    return None


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

    # Sinh câu trả lời từ các sự kiện tìm được
    # Ưu tiên sử dụng trường 'story' đã được storyteller xử lý trong pipeline
    answer = None
    if not no_data:
        # Sắp xếp theo năm và loại bỏ trùng lặp nội dung
        seen_stories = set()
        unique_events = []
        for e in sorted(events, key=lambda x: x.get("year", 0)):
            story = e.get("story")
            if story and story not in seen_stories:
                seen_stories.add(story)
                unique_events.append(e)

        answer = "\n".join([e["story"] for e in unique_events])

    return {
        "query": query,
        "intent": intent,
        "answer": answer,
        "events": events,
        "no_data": no_data
    }
