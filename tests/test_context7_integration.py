"""
Test Context7 Integration

Kiểm tra việc tích hợp Context7 để đảm bảo câu trả lời bám sát câu hỏi.
"""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from collections import defaultdict
import pytest

# Ensure ai-service is in path
AI_SERVICE_DIR = Path(__file__).parent.parent / "ai-service"
if str(AI_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_DIR))

# Mock heavy dependencies before import
sys.modules.setdefault('faiss', MagicMock())
sys.modules.setdefault('sentence_transformers', MagicMock())


# ===================================================================
# MOCK DATA - Nhà Trần và chiến công chống Nguyên Mông
# ===================================================================

MOCK_TRAN_THANH_LAP = {
    "year": 1225,
    "event": "Nhà Trần thành lập",
    "story": "Lý Chiêu Hoàng nhường ngôi cho Trần Cảnh, mở đầu triều Trần, về lâu dài mở ra thời kỳ hưng thịnh, nổi bật với ba lần kháng Mông-Nguyên.",
    "tone": "neutral",
    "persons": ["Trần Cảnh", "Lý Chiêu Hoàng"],
    "persons_all": ["Trần Cảnh", "Lý Chiêu Hoàng"],
    "places": [],
    "dynasty": "Trần",
    "keywords": ["nhà_trần", "thành_lập", "triều_đại"],
    "title": "Nhà Trần thành lập"
}

MOCK_KHANG_CHIEN_LAN_1 = {
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
}

MOCK_HICH_TUONG_SI = {
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
}

MOCK_KHANG_CHIEN_LAN_2 = {
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
}

MOCK_KHANG_CHIEN_LAN_3 = {
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
}

MOCK_BACH_DANG = {
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
}

# Sự kiện KHÔNG liên quan - năm 1255 (không phải chiến công chống Nguyên Mông)
MOCK_SU_KIEN_KHAC_1255 = {
    "year": 1255,
    "event": "Sự kiện hành chính",
    "story": "Triều đình nhà Trần tiến hành cải cách hành chính, tăng cường quản lý địa phương.",
    "tone": "neutral",
    "persons": [],
    "persons_all": [],
    "places": [],
    "dynasty": "Trần",
    "keywords": ["hành_chính", "cải_cách"],
    "title": "Cải cách hành chính"
}

# Sự kiện nhà Lý - KHÔNG liên quan đến nhà Trần
MOCK_LY_THUONG_KIET = {
    "year": 1077,
    "event": "Phòng tuyến Như Nguyệt",
    "story": "Lý Thường Kiệt chặn quân Tống ở sông Như Nguyệt, bài Nam quốc sơn hà vang vọng.",
    "tone": "heroic",
    "persons": ["Lý Thường Kiệt"],
    "persons_all": ["Lý Thường Kiệt"],
    "places": ["Như Nguyệt"],
    "dynasty": "Lý",
    "keywords": ["lý_thường_kiệt", "chiến_thắng"],
    "title": "Phòng tuyến Như Nguyệt"
}

ALL_MOCK_DOCS = [
    MOCK_TRAN_THANH_LAP,
    MOCK_KHANG_CHIEN_LAN_1,
    MOCK_HICH_TUONG_SI,
    MOCK_KHANG_CHIEN_LAN_2,
    MOCK_KHANG_CHIEN_LAN_3,
    MOCK_BACH_DANG,
    MOCK_SU_KIEN_KHAC_1255,
    MOCK_LY_THUONG_KIET,
]


def _setup_full_mocks():
    """Configure startup with mock data."""
    import app.core.startup as startup

    startup.DOCUMENTS = list(ALL_MOCK_DOCS)
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
        "lý thường kiệt": "lý thường kiệt",
    }
    startup.DYNASTY_ALIASES = {
        "trần": "trần",
        "nhà trần": "trần",
        "triều trần": "trần",
        "lý": "lý",
        "nhà lý": "lý",
    }
    startup.TOPIC_SYNONYMS = {
        "nguyên mông": "nguyên mông",
        "mông cổ": "nguyên mông",
        "mông nguyên": "nguyên mông",
        "quân nguyên": "nguyên mông",
        "quân mông": "nguyên mông",
    }


# ===================================================================
# TEST CASES
# ===================================================================

class TestContext7Integration:
    """Test Context7 integration for accurate query-answer matching."""

    def setup_method(self):
        _setup_full_mocks()

    @patch("app.services.engine.semantic_search")
    @patch("app.services.engine.scan_by_entities")
    def test_tran_dynasty_mongol_wars_query(self, mock_scan, mock_search):
        """
        Test case: "Hãy kể cho tôi về triều đại nhà Trần và những chiến công chống quân Nguyên Mông"
        
        Expected behavior:
        - Chỉ trả về các sự kiện liên quan đến nhà Trần
        - Chỉ trả về các sự kiện liên quan đến chiến công chống Nguyên Mông
        - KHÔNG trả về năm 1255 (không phải chiến công)
        - KHÔNG trả về sự kiện nhà Lý
        """
        # Mock trả về tất cả sự kiện (bao gồm cả không liên quan)
        mock_scan.return_value = list(ALL_MOCK_DOCS)
        mock_search.return_value = []

        from app.services.engine import engine_answer
        
        query = "Hãy kể cho tôi về triều đại nhà Trần và những chiến công chống quân Nguyên Mông"
        result = engine_answer(query)

        # Kiểm tra intent
        assert result["intent"] in ["multi_entity", "dynasty", "topic", "dynasty_query", "event_query", "person_query"]
        assert not result["no_data"]

        # Kiểm tra events
        events = result["events"]
        assert len(events) > 0

        # Kiểm tra: TẤT CẢ events phải thuộc nhà Trần
        for event in events:
            dynasty = event.get("dynasty", "").lower()
            assert "trần" in dynasty, f"Event năm {event.get('year')} không thuộc nhà Trần: {dynasty}"

        # Kiểm tra: TẤT CẢ events phải liên quan đến chiến công/kháng chiến
        for event in events:
            story = (event.get("story", "") or event.get("event", "")).lower()
            keywords = [k.lower() for k in event.get("keywords", [])]
            all_text = f"{story} {' '.join(keywords)}"
            
            # Phải có ít nhất một từ khóa quân sự
            military_keywords = ["chiến", "kháng", "đánh", "thắng", "quân", "nguyên", "mông"]
            has_military = any(kw in all_text for kw in military_keywords)
            assert has_military, f"Event năm {event.get('year')} không liên quan đến chiến công: {story}"

        # Kiểm tra: KHÔNG có năm 1255 (sự kiện hành chính, không phải chiến công)
        years = [e.get("year") for e in events]
        assert 1255 not in years, "Năm 1255 (sự kiện hành chính) không nên xuất hiện trong kết quả"

        # Kiểm tra: KHÔNG có sự kiện nhà Lý
        for event in events:
            dynasty = event.get("dynasty", "").lower()
            assert "lý" not in dynasty or "trần" in dynasty, "Không nên có sự kiện nhà Lý"

        # Kiểm tra answer
        answer = result["answer"]
        assert answer is not None
        assert "trần" in answer.lower()
        
        # Answer phải nhắc đến Nguyên Mông hoặc Mông Cổ
        assert any(keyword in answer.lower() for keyword in ["nguyên", "mông"]), \
            "Câu trả lời phải nhắc đến Nguyên Mông"

    @patch("app.services.engine.semantic_search")
    @patch("app.services.engine.scan_by_entities")
    def test_context7_filters_irrelevant_events(self, mock_scan, mock_search):
        """
        Test that Context7 filters out irrelevant events.
        """
        # Mock trả về cả sự kiện liên quan và không liên quan
        mock_scan.return_value = [
            MOCK_BACH_DANG,  # Liên quan
            MOCK_KHANG_CHIEN_LAN_1,  # Liên quan
            MOCK_SU_KIEN_KHAC_1255,  # KHÔNG liên quan (hành chính)
            MOCK_LY_THUONG_KIET,  # KHÔNG liên quan (nhà Lý)
        ]
        mock_search.return_value = []

        from app.services.engine import engine_answer
        
        query = "Chiến công chống Nguyên Mông của nhà Trần"
        result = engine_answer(query)

        events = result["events"]
        
        # Chỉ nên có 2 sự kiện liên quan
        assert len(events) <= 3, "Nên lọc bỏ các sự kiện không liên quan"
        
        # Không có năm 1255
        years = [e.get("year") for e in events]
        assert 1255 not in years
        
        # Không có năm 1077 (nhà Lý)
        assert 1077 not in years

    @patch("app.services.engine.semantic_search")
    @patch("app.services.engine.scan_by_entities")
    def test_context7_ranks_by_relevance(self, mock_scan, mock_search):
        """
        Test that Context7 ranks events by relevance.
        More relevant events should appear first.
        """
        mock_scan.return_value = [
            MOCK_TRAN_THANH_LAP,  # Ít liên quan (chỉ thành lập)
            MOCK_BACH_DANG,  # Rất liên quan (chiến thắng lớn)
            MOCK_KHANG_CHIEN_LAN_1,  # Rất liên quan
        ]
        mock_search.return_value = []

        from app.services.engine import engine_answer
        
        query = "Chiến thắng chống Nguyên Mông"
        result = engine_answer(query)

        events = result["events"]
        assert len(events) > 0
        
        # Sự kiện đầu tiên nên là chiến thắng, không phải thành lập triều đại
        first_event = events[0]
        first_year = first_event.get("year")
        
        # Năm 1225 (thành lập) không nên là sự kiện đầu tiên
        assert first_year != 1225, "Sự kiện thành lập triều đại không nên xếp đầu tiên"

    def test_context7_service_extract_query_focus(self):
        """Test extract_query_focus function."""
        from app.services.context7_service import extract_query_focus
        
        query = "Hãy kể cho tôi về triều đại nhà Trần và những chiến công chống quân Nguyên Mông"
        focus = extract_query_focus(query)
        
        # Kiểm tra main_topics
        assert any("dynasty:trần" in topic for topic in focus["main_topics"])
        assert any("event:" in topic for topic in focus["main_topics"])
        
        # Kiểm tra required_keywords
        assert "trần" in focus["required_keywords"]
        
        # Kiểm tra question_type
        assert focus["question_type"] == "narrative"

    def test_context7_service_calculate_relevance_score(self):
        """Test calculate_relevance_score function."""
        from app.services.context7_service import calculate_relevance_score, extract_query_focus
        
        query = "Chiến công chống Nguyên Mông của nhà Trần"
        focus = extract_query_focus(query)
        
        # Sự kiện liên quan nên có điểm cao
        score_relevant = calculate_relevance_score(MOCK_BACH_DANG, focus, query)
        
        # Sự kiện không liên quan nên có điểm thấp
        score_irrelevant = calculate_relevance_score(MOCK_SU_KIEN_KHAC_1255, focus, query)
        
        assert score_relevant > score_irrelevant, \
            f"Sự kiện liên quan ({score_relevant}) phải có điểm cao hơn sự kiện không liên quan ({score_irrelevant})"
        
        # Sự kiện nhà Lý nên có điểm rất thấp
        score_ly = calculate_relevance_score(MOCK_LY_THUONG_KIET, focus, query)
        assert score_ly < score_relevant

    def test_context7_service_filter_and_rank(self):
        """Test filter_and_rank_events function."""
        from app.services.context7_service import filter_and_rank_events
        
        query = "Chiến công chống Nguyên Mông của nhà Trần"
        events = list(ALL_MOCK_DOCS)
        
        filtered = filter_and_rank_events(events, query, max_results=10)
        
        # Nên lọc bỏ sự kiện không liên quan
        years = [e.get("year") for e in filtered]
        
        # Không có năm 1255 (hành chính)
        assert 1255 not in years
        
        # Không có năm 1077 (nhà Lý)
        assert 1077 not in years
        
        # Chỉ có sự kiện nhà Trần liên quan đến chiến tranh
        for event in filtered:
            assert event.get("dynasty", "").lower() == "trần"

    def test_context7_service_validate_answer(self):
        """Test validate_answer_relevance function."""
        from app.services.context7_service import validate_answer_relevance
        
        query = "Chiến công chống Nguyên Mông của nhà Trần"
        
        # Câu trả lời tốt
        good_answer = "Năm 1258: Đại Việt đánh bại quân Mông Cổ. Năm 1288: Trận Bạch Đằng."
        validation_good = validate_answer_relevance(good_answer, query)
        assert validation_good["is_relevant"]
        
        # Câu trả lời không liên quan (không nhắc đến Nguyên Mông)
        bad_answer = "Năm 1225: Nhà Trần thành lập. Năm 1255: Cải cách hành chính."
        validation_bad = validate_answer_relevance(bad_answer, query)
        assert not validation_bad["is_relevant"]
        assert len(validation_bad["issues"]) > 0

    def test_hai_ba_trung_wrong_person_filter(self):
        """
        Test case: "Ai là Hai Bà Trưng và cuộc khởi nghĩa của họ có ý nghĩa như thế nào?"
        
        Expected behavior:
        - KHÔNG trả về sự kiện về Hồ Quý Ly (năm 1400)
        - CHỈ trả về sự kiện về Hai Bà Trưng (năm 40)
        """
        _setup_full_mocks()
        
        # Thêm mock data vào DOCUMENTS
        import app.core.startup as startup
        
        mock_hai_ba_trung = {
            "year": 40,
            "event": "Khởi nghĩa Hai Bà Trưng",
            "story": "Trưng Trắc và Trưng Nhị lãnh đạo khởi nghĩa chống quân Hán.",
            "tone": "heroic",
            "persons": ["Hai Bà Trưng"],
            "persons_all": ["Trưng Trắc", "Trưng Nhị"],
            "places": [],
            "dynasty": "Trưng Vương",
            "keywords": ["khởi_nghĩa"],
            "title": "Khởi nghĩa Hai Bà Trưng"
        }
        
        mock_ho_quy_ly = {
            "year": 1400,
            "event": "Hồ Quý Ly lập nhà Hồ",
            "story": "Hồ Quý Ly lập nhà Hồ. Ông cải cách mạnh, đổi quốc hiệu Đại Ngu.",
            "tone": "neutral",
            "persons": ["Hồ Quý Ly"],
            "persons_all": ["Hồ Quý Ly"],
            "places": [],
            "dynasty": "Hồ",
            "keywords": ["cải_cách"],
            "title": "Nhà Hồ thành lập"
        }
        
        # Thêm vào DOCUMENTS
        startup.DOCUMENTS.append(mock_hai_ba_trung)
        startup.DOCUMENTS.append(mock_ho_quy_ly)
        
        # Cập nhật indexes
        hai_ba_idx = len(startup.DOCUMENTS) - 2
        ho_quy_idx = len(startup.DOCUMENTS) - 1
        
        startup.PERSONS_INDEX["hai bà trưng"].append(hai_ba_idx)
        startup.PERSONS_INDEX["trưng trắc"].append(hai_ba_idx)
        startup.PERSONS_INDEX["trưng nhị"].append(hai_ba_idx)
        startup.PERSONS_INDEX["hồ quý ly"].append(ho_quy_idx)
        
        startup.DYNASTY_INDEX["trưng vương"].append(hai_ba_idx)
        startup.DYNASTY_INDEX["hồ"].append(ho_quy_idx)

        from app.services.engine import engine_answer
        
        query = "Ai là Hai Bà Trưng và cuộc khởi nghĩa của họ có ý nghĩa như thế nào?"
        result = engine_answer(query)

        # Kiểm tra
        assert not result["no_data"], f"Result: {result}"
        events = result["events"]
        assert len(events) > 0

        # Kiểm tra: KHÔNG có Hồ Quý Ly
        for event in events:
            persons = event.get("persons", []) + event.get("persons_all", [])
            persons_lower = [p.lower() for p in persons]
            assert "hồ quý ly" not in persons_lower, \
                f"Sự kiện năm {event.get('year')} không nên có Hồ Quý Ly khi hỏi về Hai Bà Trưng"
        
        # Kiểm tra: CHỈ có Hai Bà Trưng
        years = [e.get("year") for e in events]
        assert 40 in years, "Phải có sự kiện năm 40 (Hai Bà Trưng)"
        assert 1400 not in years, "Không nên có sự kiện năm 1400 (Hồ Quý Ly)"
        
        # Kiểm tra answer
        answer = result["answer"]
        assert answer is not None
        answer_lower = answer.lower()
        
        # Answer phải nhắc đến Hai Bà Trưng hoặc Trưng
        assert any(keyword in answer_lower for keyword in ["trưng", "hai bà"]), \
            "Câu trả lời phải nhắc đến Hai Bà Trưng"
        
        # Answer KHÔNG được nhắc đến Hồ Quý Ly
        assert "hồ quý ly" not in answer_lower, \
            "Câu trả lời không được nhắc đến Hồ Quý Ly khi hỏi về Hai Bà Trưng"

    def test_dai_viet_keyword_filter(self):
        """
        Test case: "Đại Việt đã được thành lập như thế nào và phát triển qua các thời kỳ ra sao?"
        
        Expected behavior:
        - CHỈ trả về các sự kiện có nhắc đến "Đại Việt"
        - KHÔNG trả về năm 1010 (Chiếu dời đô - không có "Đại Việt")
        - Phải có năm 1054 (Đổi quốc hiệu thành Đại Việt)
        """
        import app.core.startup as startup
        
        # Reset DOCUMENTS để chỉ có data cho test này
        startup.DOCUMENTS = []
        startup.DOCUMENTS_BY_YEAR = defaultdict(list)
        startup.PERSONS_INDEX = defaultdict(list)
        startup.DYNASTY_INDEX = defaultdict(list)
        startup.KEYWORD_INDEX = defaultdict(list)
        startup.PLACES_INDEX = defaultdict(list)
        startup.PERSON_ALIASES = {}
        startup.DYNASTY_ALIASES = {}
        startup.TOPIC_SYNONYMS = {}
        
        # Mock data
        mock_chieu_doi_do = {
            "year": 1010,
            "event": "Chiếu dời đô",
            "story": "Văn kiện nêu lý do dời đô và tầm nhìn phát triển ở Đại La.",
            "tone": "neutral",
            "persons": [],
            "persons_all": ["Lý Thái Tổ"],
            "places": ["Đại La"],
            "dynasty": "Lý",
            "keywords": ["dời_đô"],
            "title": "Chiếu dời đô"
        }
        
        mock_doi_quoc_hieu = {
            "year": 1054,
            "event": "Đổi quốc hiệu thành Đại Việt",
            "story": "Thời Lý Thánh Tông, quốc hiệu đổi từ Đại Cồ Việt sang Đại Việt. Khẳng định bản sắc và vị thế quốc gia độc lập.",
            "tone": "neutral",
            "persons": [],
            "persons_all": ["Lý Thánh Tông"],
            "places": ["Đại Việt"],
            "dynasty": "Lý",
            "keywords": ["đại_việt", "quốc_hiệu"],
            "title": "Đổi quốc hiệu thành Đại Việt"
        }
        
        mock_ly_thuong_kiet_1075 = {
            "year": 1075,
            "event": "Lý Thường Kiệt tiến công Ung–Khâm–Liêm",
            "story": "Quân Đại Việt tấn công trước để phá thế xâm lược của nhà Tống.",
            "tone": "heroic",
            "persons": ["Lý Thường Kiệt"],
            "persons_all": ["Lý Thường Kiệt"],
            "places": ["Đại Việt"],
            "dynasty": "Lý",
            "keywords": ["chiến_tranh"],
            "title": "Tiến công Ung–Khâm–Liêm"
        }
        
        mock_nhu_nguyet = {
            "year": 1077,
            "event": "Phòng tuyến Như Nguyệt",
            "story": "Quân Đại Việt chặn quân Tống ở sông Như Nguyệt; bài 'Nam quốc sơn hà' vang vọng.",
            "tone": "heroic",
            "persons": ["Lý Thường Kiệt"],
            "persons_all": ["Lý Thường Kiệt"],
            "places": ["Đại Việt", "Như Nguyệt"],
            "dynasty": "Lý",
            "keywords": ["chiến_tranh", "nam_quốc_sơn_hà"],
            "title": "Phòng tuyến Như Nguyệt"
        }
        
        # Thêm vào DOCUMENTS
        startup.DOCUMENTS = [mock_chieu_doi_do, mock_doi_quoc_hieu, 
                            mock_ly_thuong_kiet_1075, mock_nhu_nguyet]
        
        # Cập nhật DOCUMENTS_BY_YEAR
        for doc in startup.DOCUMENTS:
            y = doc.get("year")
            if y is not None:
                startup.DOCUMENTS_BY_YEAR[y].append(doc)
        
        # Cập nhật indexes
        for idx, doc in enumerate(startup.DOCUMENTS):
            # Index cho places
            for place in doc.get("places", []):
                startup.PLACES_INDEX[place.lower()].append(idx)
            
            # Index cho persons
            for person in doc.get("persons", []) + doc.get("persons_all", []):
                startup.PERSONS_INDEX[person.lower()].append(idx)
            
            # Index cho dynasty
            dynasty = doc.get("dynasty", "").strip().lower()
            if dynasty:
                startup.DYNASTY_INDEX[dynasty].append(idx)
            
            # Index cho keywords
            for kw in doc.get("keywords", []):
                startup.KEYWORD_INDEX[kw.lower().replace("_", " ")].append(idx)
        
        from app.services.engine import engine_answer
        
        query = "Đại Việt đã được thành lập như thế nào và phát triển qua các thời kỳ ra sao?"
        result = engine_answer(query)

        # Kiểm tra
        assert not result["no_data"]
        events = result["events"]
        assert len(events) > 0

        # Kiểm tra: TẤT CẢ events phải có "Đại Việt" trong story hoặc places
        for event in events:
            story = (event.get("story", "") or "").lower()
            places = [p.lower() for p in event.get("places", [])]
            keywords = [k.lower() for k in event.get("keywords", [])]
            
            has_dai_viet = (
                "đại việt" in story or 
                any("đại việt" in p for p in places) or
                any("đại_việt" in k or "đại việt" in k for k in keywords)
            )
            
            assert has_dai_viet, \
                f"Sự kiện năm {event.get('year')} không có 'Đại Việt': {story}"
        
        # Kiểm tra: KHÔNG có năm 1010 (Chiếu dời đô)
        years = [e.get("year") for e in events]
        assert 1010 not in years, "Năm 1010 (Chiếu dời đô) không nên xuất hiện vì không có 'Đại Việt'"
        
        # Kiểm tra: Phải có năm 1054 (Đổi quốc hiệu)
        assert 1054 in years, "Phải có năm 1054 (Đổi quốc hiệu thành Đại Việt)"
        
        # Kiểm tra answer
        answer = result["answer"]
        assert answer is not None
        answer_lower = answer.lower()
        
        # Answer phải nhắc đến Đại Việt
        assert "đại việt" in answer_lower, "Câu trả lời phải nhắc đến Đại Việt"
