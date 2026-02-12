"""
Demo script để kiểm tra Context7 integration

Chạy script này để xem sự khác biệt trước và sau khi có Context7.
"""
import sys
from pathlib import Path

# Add ai-service to path
AI_SERVICE_DIR = Path(__file__).parent.parent
if str(AI_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_DIR))

from app.services.context7_service import (
    extract_query_focus,
    calculate_relevance_score,
    filter_and_rank_events,
    validate_answer_relevance,
)


# Mock data
MOCK_EVENTS = [
    {
        "year": 1225,
        "event": "Nhà Trần thành lập",
        "story": "Lý Chiêu Hoàng nhường ngôi cho Trần Cảnh, mở đầu triều Trần.",
        "tone": "neutral",
        "dynasty": "Trần",
        "keywords": ["nhà_trần", "thành_lập"],
        "persons": ["Trần Cảnh"],
    },
    {
        "year": 1255,
        "event": "Cải cách hành chính",
        "story": "Triều đình nhà Trần tiến hành cải cách hành chính.",
        "tone": "neutral",
        "dynasty": "Trần",
        "keywords": ["hành_chính"],
        "persons": [],
    },
    {
        "year": 1258,
        "event": "Kháng chiến lần 1 chống Mông Cổ",
        "story": "Đại Việt đánh bại cuộc xâm lược đầu tiên của quân Mông Cổ.",
        "tone": "heroic",
        "dynasty": "Trần",
        "keywords": ["kháng_chiến", "mông_cổ"],
        "persons": [],
    },
    {
        "year": 1284,
        "event": "Hịch tướng sĩ",
        "story": "Trần Hưng Đạo soạn Hịch tướng sĩ khích lệ quân dân.",
        "tone": "heroic",
        "dynasty": "Trần",
        "keywords": ["kháng_chiến", "trần_hưng_đạo"],
        "persons": ["Trần Hưng Đạo"],
    },
    {
        "year": 1285,
        "event": "Kháng chiến lần 2 chống Nguyên",
        "story": "Quân dân Đại Việt giành thắng lợi lớn trước quân Nguyên.",
        "tone": "heroic",
        "dynasty": "Trần",
        "keywords": ["kháng_chiến", "nguyên"],
        "persons": [],
    },
    {
        "year": 1288,
        "event": "Trận Bạch Đằng",
        "story": "Trần Hưng Đạo nhử địch vào bãi cọc ngầm, tiêu diệt thủy quân Nguyên.",
        "tone": "heroic",
        "dynasty": "Trần",
        "keywords": ["bạch_đằng", "trần_hưng_đạo", "nguyên"],
        "persons": ["Trần Hưng Đạo"],
    },
    {
        "year": 1077,
        "event": "Phòng tuyến Như Nguyệt",
        "story": "Lý Thường Kiệt chặn quân Tống ở sông Như Nguyệt.",
        "tone": "heroic",
        "dynasty": "Lý",
        "keywords": ["lý_thường_kiệt"],
        "persons": ["Lý Thường Kiệt"],
    },
]


def print_separator():
    print("\n" + "=" * 80 + "\n")


def demo_query_focus():
    print("📊 DEMO 1: Phân tích câu hỏi (Query Focus Extraction)")
    print_separator()
    
    query = "Hãy kể cho tôi về triều đại nhà Trần và những chiến công chống quân Nguyên Mông"
    print(f"Câu hỏi: {query}")
    print()
    
    focus = extract_query_focus(query)
    
    print("Kết quả phân tích:")
    print(f"  - Chủ đề chính: {focus['main_topics']}")
    print(f"  - Từ khóa bắt buộc: {focus['required_keywords']}")
    print(f"  - Loại câu hỏi: {focus['question_type']}")


def demo_relevance_scoring():
    print("🎯 DEMO 2: Tính điểm liên quan (Relevance Scoring)")
    print_separator()
    
    query = "Chiến công chống Nguyên Mông của nhà Trần"
    print(f"Câu hỏi: {query}")
    print()
    
    focus = extract_query_focus(query)
    
    print("Điểm số các sự kiện:")
    print()
    
    for event in MOCK_EVENTS:
        score = calculate_relevance_score(event, focus, query)
        year = event.get("year")
        title = event.get("event")
        dynasty = event.get("dynasty")
        
        # Emoji dựa trên điểm
        if score >= 20:
            emoji = "🟢"
        elif score >= 10:
            emoji = "🟡"
        else:
            emoji = "🔴"
        
        print(f"{emoji} Năm {year} ({dynasty}): {title}")
        print(f"   Điểm: {score:.2f}")
        print()


def demo_filtering():
    print("🔍 DEMO 3: Lọc và xếp hạng (Filtering & Ranking)")
    print_separator()
    
    query = "Chiến công chống Nguyên Mông của nhà Trần"
    print(f"Câu hỏi: {query}")
    print()
    
    print(f"Tổng số sự kiện ban đầu: {len(MOCK_EVENTS)}")
    print()
    
    filtered = filter_and_rank_events(MOCK_EVENTS, query, max_results=10)
    
    print(f"Số sự kiện sau khi lọc: {len(filtered)}")
    print()
    print("Các sự kiện được giữ lại (theo thứ tự ưu tiên):")
    print()
    
    for i, event in enumerate(filtered, 1):
        year = event.get("year")
        title = event.get("event")
        print(f"  {i}. Năm {year}: {title}")
    
    print()
    print("Các sự kiện bị loại bỏ:")
    filtered_years = {e.get("year") for e in filtered}
    for event in MOCK_EVENTS:
        if event.get("year") not in filtered_years:
            year = event.get("year")
            title = event.get("event")
            dynasty = event.get("dynasty")
            print(f"  ❌ Năm {year} ({dynasty}): {title}")


def demo_validation():
    print("✅ DEMO 4: Validate câu trả lời")
    print_separator()
    
    query = "Chiến công chống Nguyên Mông của nhà Trần"
    print(f"Câu hỏi: {query}")
    print()
    
    # Câu trả lời tốt
    good_answer = """
Năm 1258: Đại Việt đánh bại cuộc xâm lược đầu tiên của quân Mông Cổ.
Năm 1284: Trần Hưng Đạo soạn Hịch tướng sĩ khích lệ quân dân.
Năm 1285: Quân dân Đại Việt giành thắng lợi lớn trước quân Nguyên.
Năm 1288: Trần Hưng Đạo nhử địch vào bãi cọc ngầm, tiêu diệt thủy quân Nguyên.
    """.strip()
    
    print("Câu trả lời:")
    print(good_answer)
    print()
    
    validation = validate_answer_relevance(good_answer, query)
    
    if validation["is_relevant"]:
        print("✅ Câu trả lời BÁM SÁT câu hỏi")
    else:
        print("❌ Câu trả lời KHÔNG BÁM SÁT câu hỏi")
        print()
        print("Vấn đề phát hiện:")
        for issue in validation["issues"]:
            print(f"  - {issue}")
        print()
        print("Gợi ý:")
        for suggestion in validation["suggestions"]:
            print(f"  - {suggestion}")
    
    print()
    print_separator()
    
    # Câu trả lời xấu
    bad_answer = """
Năm 1225: Nhà Trần thành lập.
Năm 1255: Cải cách hành chính.
    """.strip()
    
    print("Câu trả lời (không tốt):")
    print(bad_answer)
    print()
    
    validation = validate_answer_relevance(bad_answer, query)
    
    if validation["is_relevant"]:
        print("✅ Câu trả lời BÁM SÁT câu hỏi")
    else:
        print("❌ Câu trả lời KHÔNG BÁM SÁT câu hỏi")
        print()
        print("Vấn đề phát hiện:")
        for issue in validation["issues"]:
            print(f"  - {issue}")
        print()
        print("Gợi ý:")
        for suggestion in validation["suggestions"]:
            print(f"  - {suggestion}")


def main():
    print("\n" + "🚀 " * 20)
    print("CONTEXT7 INTEGRATION DEMO")
    print("🚀 " * 20)
    
    demo_query_focus()
    print_separator()
    
    demo_relevance_scoring()
    print_separator()
    
    demo_filtering()
    print_separator()
    
    demo_validation()
    
    print("\n" + "✨ " * 20)
    print("DEMO HOÀN TẤT")
    print("✨ " * 20 + "\n")


if __name__ == "__main__":
    main()
