"""
Test User Query - Verify Context7 Fix

Test query: "Hãy kể cho tôi về triều đại nhà Trần và những chiến công chống quân Nguyên Mông"
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock
from collections import defaultdict

# Setup path
AI_SERVICE_DIR = Path(__file__).parent / "ai-service"
sys.path.insert(0, str(AI_SERVICE_DIR))

# Mock heavy dependencies
sys.modules.setdefault('faiss', MagicMock())
sys.modules.setdefault('sentence_transformers', MagicMock())

# Mock data - Nhà Trần và chiến công chống Nguyên Mông
MOCK_EVENTS = [
    {
        "year": 1225,
        "event": "Nhà Trần thành lập",
        "story": "Lý Chiêu Hoàng nhường ngôi cho Trần Cảnh, mở đầu triều Trần.",
        "tone": "neutral",
        "persons": ["Trần Cảnh"],
        "persons_all": ["Trần Cảnh", "Lý Chiêu Hoàng"],
        "places": [],
        "dynasty": "Trần",
        "keywords": ["nhà_trần", "thành_lập"],
        "title": "Nhà Trần thành lập"
    },
    {
        "year": 1258,
        "event": "Kháng chiến lần 1 chống Mông Cổ",
        "story": "Đại Việt đánh bại cuộc xâm lược đầu tiên của quân Mông Cổ, qua đó bảo vệ độc lập, mở ra chuỗi thắng lợi chống xâm lăng phương Bắc.",
        "tone": "heroic",
        "persons": [],
        "persons_all": [],
        "places": ["Đại Việt"],
        "dynasty": "Trần",
        "keywords": ["kháng_chiến", "mông_cổ", "chiến_thắng"],
        "title": "Kháng chiến lần 1 chống Mông Cổ"
    },
    {
        "year": 1284,
        "event": "Hịch tướng sĩ",
        "story": "Trần Hưng Đạo soạn Hịch tướng sĩ khích lệ quân dân trước kháng chiến lần 2, về lâu dài tác phẩm quân sự – chính trị cổ vũ mạnh mẽ.",
        "tone": "heroic",
        "persons": ["Trần Hưng Đạo"],
        "persons_all": ["Trần Hưng Đạo"],
        "places": [],
        "dynasty": "Trần",
        "keywords": ["kháng_chiến", "trần_hưng_đạo", "hịch_tướng_sĩ"],
        "title": "Hịch tướng sĩ"
    },
    {
        "year": 1285,
        "event": "Kháng chiến lần 2 chống Nguyên",
        "story": "Quân dân Đại Việt giành thắng lợi lớn trước quân Nguyên, qua đó củng cố sức mạnh quốc gia và nghệ thuật chiến tranh nhân dân.",
        "tone": "heroic",
        "persons": [],
        "persons_all": [],
        "places": ["Đại Việt"],
        "dynasty": "Trần",
        "keywords": ["kháng_chiến", "nguyên", "chiến_thắng"],
        "title": "Kháng chiến lần 2 chống Nguyên"
    },
    {
        "year": 1287,
        "event": "Kháng chiến lần 3 chống Nguyên",
        "story": "Quân Nguyên tấn công lần thứ ba, quân dân Đại Việt kiên cường kháng chiến, chuẩn bị cho trận quyết chiến Bạch Đằng.",
        "tone": "heroic",
        "persons": [],
        "persons_all": [],
        "places": ["Đại Việt"],
        "dynasty": "Trần",
        "keywords": ["kháng_chiến", "nguyên", "chiến_tranh"],
        "title": "Kháng chiến lần 3 chống Nguyên"
    },
    {
        "year": 1288,
        "event": "Trận Bạch Đằng",
        "story": "Trần Hưng Đạo nhử địch vào bãi cọc ngầm trên sông Bạch Đằng, tiêu diệt thủy quân Nguyên, qua đó đập tan ý đồ xâm lược, kết thúc chiến tranh, ghi dấu mốc chói lọi.",
        "tone": "heroic",
        "persons": ["Trần Hưng Đạo"],
        "persons_all": ["Trần Hưng Đạo"],
        "places": ["Bạch Đằng"],
        "dynasty": "Trần",
        "keywords": ["bạch_đằng", "trần_hưng_đạo", "chiến_thắng", "nguyên"],
        "title": "Trận Bạch Đằng"
    },
]

def setup_mock_data():
    """Setup mock data for testing."""
    import app.core.startup as startup
    
    startup.DOCUMENTS = list(MOCK_EVENTS)
    startup.DOCUMENTS_BY_YEAR = defaultdict(list)
    for doc in startup.DOCUMENTS:
        y = doc.get("year")
        if y is not None:
            startup.DOCUMENTS_BY_YEAR[y].append(doc)
    
    startup.PERSONS_INDEX = defaultdict(list)
    startup.DYNASTY_INDEX = defaultdict(list)
    startup.KEYWORD_INDEX = defaultdict(list)
    startup.PLACES_INDEX = defaultdict(list)
    
    for idx, doc in enumerate(startup.DOCUMENTS):
        all_persons = set(doc.get("persons", []) + doc.get("persons_all", []))
        for person in all_persons:
            startup.PERSONS_INDEX[person.strip().lower()].append(idx)
        dynasty = doc.get("dynasty", "").strip().lower()
        if dynasty:
            startup.DYNASTY_INDEX[dynasty].append(idx)
        for kw in doc.get("keywords", []):
            startup.KEYWORD_INDEX[kw.lower().replace("_", " ")].append(idx)
        for place in doc.get("places", []):
            startup.PLACES_INDEX[place.strip().lower()].append(idx)
    
    startup.PERSON_ALIASES = {
        "trần hưng đạo": "trần hưng đạo",
        "trần quốc tuấn": "trần hưng đạo",
    }
    startup.DYNASTY_ALIASES = {
        "trần": "trần",
        "nhà trần": "trần",
        "triều trần": "trần",
    }
    startup.TOPIC_SYNONYMS = {
        "nguyên mông": "nguyên mông",
        "mông cổ": "nguyên mông",
        "mông nguyên": "nguyên mông",
        "quân nguyên": "nguyên mông",
        "quân mông": "nguyên mông",
    }

def test_user_query():
    """Test the user's query."""
    from unittest.mock import patch
    
    # Setup mock data
    setup_mock_data()
    
    # Mock semantic_search and scan_by_entities
    with patch("app.services.engine.semantic_search") as mock_search, \
         patch("app.services.engine.scan_by_entities") as mock_scan:
        
        # Return all mock events
        mock_scan.return_value = list(MOCK_EVENTS)
        mock_search.return_value = []
        
        from app.services.engine import engine_answer
        
        query = "Hãy kể cho tôi về triều đại nhà Trần và những chiến công chống quân Nguyên Mông"
        
        print("=" * 80)
        print("QUERY:", query)
        print("=" * 80)
        
        result = engine_answer(query)
        
        print("\nINTENT:", result["intent"])
        print("NO_DATA:", result["no_data"])
        print("\nEVENTS RETURNED:", len(result["events"]))
        
        # Print years
        years = [e.get("year") for e in result["events"]]
        print("YEARS:", sorted(years))
        
        print("\n" + "=" * 80)
        print("ANSWER:")
        print("=" * 80)
        print(result["answer"])
        print("=" * 80)
        
        # Verify
        print("\n" + "=" * 80)
        print("VERIFICATION:")
        print("=" * 80)
        
        expected_years = [1258, 1284, 1285, 1287, 1288]
        missing_years = [y for y in expected_years if y not in years]
        extra_years = [y for y in years if y not in expected_years and y != 1225]
        
        if missing_years:
            print(f"❌ MISSING YEARS: {missing_years}")
        else:
            print("✅ All expected years present")
        
        if extra_years:
            print(f"⚠️  EXTRA YEARS: {extra_years}")
        
        # Check for duplicates in answer
        answer_lines = result["answer"].split("\n")
        seen_lines = set()
        duplicates = []
        for line in answer_lines:
            line_clean = line.strip()
            if line_clean and line_clean.startswith("**Năm"):
                if line_clean in seen_lines:
                    duplicates.append(line_clean)
                seen_lines.add(line_clean)
        
        if duplicates:
            print(f"❌ DUPLICATE LINES: {len(duplicates)}")
            for dup in duplicates:
                print(f"   - {dup[:50]}...")
        else:
            print("✅ No duplicate lines")
        
        print("=" * 80)
        
        return result

if __name__ == "__main__":
    test_user_query()
