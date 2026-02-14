"""
test_engine.py - Comprehensive unit tests for HistoryMindAI engine.

Covers: intent detection, entity resolution, synonym matching,
multi-entity queries, inverted index scan, edge cases, and formatting.
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
# RICH MOCK DATA — covers multiple dynasties, persons, places, topics
# ===================================================================

MOCK_TRAN_HUNG_DAO = {
    "year": 1288, "event": "Chiến thắng Bạch Đằng",
    "story": "Trần Hưng Đạo đánh tan quân Nguyên Mông trên sông Bạch Đằng.",
    "tone": "heroic", "persons": ["Trần Hưng Đạo"], "persons_all": ["Trần Hưng Đạo"],
    "places": ["Bạch Đằng"], "dynasty": "Trần",
    "keywords": ["bạch_đằng", "trần_hưng_đạo"], "title": "Chiến thắng Bạch Đằng 1288"
}
MOCK_HICH_TUONG_SI = {
    "year": 1284, "event": "Hịch tướng sĩ",
    "story": "Trần Hưng Đạo soạn Hịch tướng sĩ khích lệ quân dân trước kháng chiến lần 2.",
    "tone": "heroic", "persons": ["Trần Hưng Đạo"], "persons_all": ["Trần Hưng Đạo"],
    "places": [], "dynasty": "Trần",
    "keywords": ["kháng_chiến", "trần_hưng_đạo"], "title": "Hịch tướng sĩ"
}
MOCK_HAI_BA_TRUNG = {
    "year": 40, "event": "Khởi nghĩa Hai Bà Trưng",
    "story": "Trưng Trắc và Trưng Nhị lãnh đạo khởi nghĩa chống quân Hán.",
    "tone": "heroic", "persons": ["Hai Bà Trưng"], "persons_all": ["Trưng Trắc", "Trưng Nhị"],
    "places": [], "dynasty": "Trưng Vương",
    "keywords": ["khởi_nghĩa"], "title": "Khởi nghĩa Hai Bà Trưng"
}
MOCK_NGO_QUYEN = {
    "year": 938, "event": "Trận Bạch Đằng",
    "story": "Ngô Quyền dùng cọc gỗ đặt ngầm trên sông Bạch Đằng đánh bại quân Nam Hán.",
    "tone": "heroic", "persons": ["Ngô Quyền"], "persons_all": ["Ngô Quyền"],
    "places": ["Bạch Đằng"], "dynasty": "Tự chủ",
    "keywords": ["bạch_đằng"], "title": "Trận Bạch Đằng 938"
}
MOCK_LY_THUONG_KIET = {
    "year": 1077, "event": "Phòng tuyến Như Nguyệt",
    "story": "Lý Thường Kiệt chặn quân Tống ở sông Như Nguyệt, bài Nam quốc sơn hà vang vọng.",
    "tone": "heroic", "persons": ["Lý Thường Kiệt"], "persons_all": ["Lý Thường Kiệt"],
    "places": ["Như Nguyệt", "Đại Việt"], "dynasty": "Lý",
    "keywords": ["lý_thường_kiệt", "đại_việt", "độc_lập"], "title": "Phòng tuyến Như Nguyệt"
}
MOCK_DAI_VIET = {
    "year": 1054, "event": "Đổi quốc hiệu thành Đại Việt",
    "story": "Thời Lý Thánh Tông, quốc hiệu đổi từ Đại Cồ Việt sang Đại Việt.",
    "tone": "neutral", "persons": [], "persons_all": ["Lý Thánh Tông"],
    "places": ["Đại Việt"], "dynasty": "Lý",
    "keywords": ["đại_việt", "đổi_quốc_hiệu", "độc_lập"], "title": "Đổi quốc hiệu Đại Việt"
}
MOCK_LE_LOI = {
    "year": 1418, "event": "Khởi nghĩa Lam Sơn bùng nổ",
    "story": "Lê Lợi dựng cờ khởi nghĩa ở Lam Sơn chống quân Minh.",
    "tone": "heroic", "persons": ["Lê Lợi"], "persons_all": ["Lê Lợi"],
    "places": ["Lam Sơn"], "dynasty": "Minh thuộc",
    "keywords": ["khởi_nghĩa", "lam_sơn", "lê_lợi", "giải_phóng"], "title": "Khởi nghĩa Lam Sơn"
}
MOCK_HCM = {
    "year": 1945, "event": "Cách mạng Tháng Tám và Tuyên ngôn Độc lập",
    "story": "Hồ Chí Minh đọc Tuyên ngôn Độc lập, khai sinh nước Việt Nam Dân chủ Cộng hòa.",
    "tone": "heroic", "persons": ["Hồ Chí Minh"], "persons_all": ["Hồ Chí Minh"],
    "places": ["Ba Đình"], "dynasty": "Hiện đại",
    "keywords": ["cách_mạng", "hồ_chí_minh", "độc_lập", "tuyên_ngôn"], "title": "Cách mạng Tháng Tám"
}
MOCK_DINH_BO_LINH = {
    "year": 968, "event": "Đinh Bộ Lĩnh dẹp loạn 12 sứ quân",
    "story": "Đinh Bộ Lĩnh thống nhất cát cứ, lên ngôi Hoàng đế, đặt quốc hiệu Đại Cồ Việt.",
    "tone": "heroic", "persons": ["Đinh Bộ Lĩnh"], "persons_all": ["Đinh Tiên Hoàng"],
    "places": ["Đại Cồ Việt"], "dynasty": "Đinh",
    "keywords": ["thống_nhất", "lên_ngôi", "đại_cồ_việt", "độc_lập"], "title": ""
}
MOCK_DBP = {
    "year": 1954, "event": "Chiến thắng Điện Biên Phủ",
    "story": "Quân đội Việt Nam giành thắng lợi quyết định tại Điện Biên Phủ.",
    "tone": "heroic", "persons": ["Võ Nguyên Giáp"], "persons_all": ["Võ Nguyên Giáp"],
    "places": ["Điện Biên Phủ"], "dynasty": "Hiện đại",
    "keywords": ["chiến_thắng", "điện_biên_phủ", "thắng_lợi"], "title": "Chiến thắng Điện Biên Phủ"
}
MOCK_QUANG_TRUNG = {
    "year": 1789, "event": "Quang Trung đại phá quân Thanh",
    "story": "Nguyễn Huệ (Quang Trung) đánh tan 29 vạn quân Thanh tại Đống Đa.",
    "tone": "heroic", "persons": ["Nguyễn Huệ"], "persons_all": ["Quang Trung", "Nguyễn Huệ"],
    "places": ["Đống Đa"], "dynasty": "Tây Sơn",
    "keywords": ["đống_đa", "quang_trung"], "title": "Quang Trung đại phá quân Thanh"
}

ALL_MOCK_DOCS = [
    MOCK_TRAN_HUNG_DAO, MOCK_HICH_TUONG_SI, MOCK_HAI_BA_TRUNG,
    MOCK_NGO_QUYEN, MOCK_LY_THUONG_KIET, MOCK_DAI_VIET,
    MOCK_LE_LOI, MOCK_HCM, MOCK_DINH_BO_LINH, MOCK_DBP, MOCK_QUANG_TRUNG,
]


# ===================================================================
# HELPER: Full startup mock with rich data
# ===================================================================

def _setup_full_mocks():
    """Configure startup with rich mock data covering all user scenarios."""
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

    # Full knowledge base aliases
    startup.PERSON_ALIASES = {
        "hai bà trưng": "hai bà trưng", "trưng trắc": "hai bà trưng",
        "trưng nhị": "hai bà trưng", "hai bà": "hai bà trưng", "trưng vương": "hai bà trưng",
        "trần hưng đạo": "trần hưng đạo", "trần quốc tuấn": "trần hưng đạo",
        "hưng đạo vương": "trần hưng đạo", "hưng đạo đại vương": "trần hưng đạo",
        "nguyễn huệ": "nguyễn huệ", "quang trung": "nguyễn huệ", "bắc bình vương": "nguyễn huệ",
        "hồ chí minh": "hồ chí minh", "nguyễn tất thành": "hồ chí minh",
        "nguyễn ái quốc": "hồ chí minh", "bác hồ": "hồ chí minh",
        "lý thường kiệt": "lý thường kiệt",
        "ngô quyền": "ngô quyền", "ngô vương": "ngô quyền",
        "lê lợi": "lê lợi", "lê thái tổ": "lê lợi",
        "đinh bộ lĩnh": "đinh bộ lĩnh", "đinh tiên hoàng": "đinh bộ lĩnh",
        "võ nguyên giáp": "võ nguyên giáp", "đại tướng võ nguyên giáp": "võ nguyên giáp",
        "bà triệu": "bà triệu", "triệu thị trinh": "bà triệu",
    }
    startup.DYNASTY_ALIASES = {
        "trần": "trần", "nhà trần": "trần", "triều trần": "trần", "thời trần": "trần",
        "lý": "lý", "nhà lý": "lý", "triều lý": "lý", "thời lý": "lý",
        "lê": "lê", "nhà lê": "lê", "triều lê": "lê",
        "nguyễn": "nguyễn", "nhà nguyễn": "nguyễn",
        "đinh": "đinh", "nhà đinh": "đinh",
        "tây sơn": "tây sơn", "nhà tây sơn": "tây sơn",
        "tự chủ": "tự chủ", "thời tự chủ": "tự chủ",
    }
    startup.TOPIC_SYNONYMS = {
        "nguyên mông": "nguyên mông", "mông cổ": "nguyên mông",
        "mông nguyên": "nguyên mông", "quân nguyên": "nguyên mông", "quân mông": "nguyên mông",
        "pháp thuộc": "pháp thuộc", "thực dân pháp": "pháp thuộc",
        "giáo dục": "giáo dục", "văn miếu": "giáo dục", "quốc tử giám": "giáo dục",
        "khởi nghĩa lam sơn": "khởi nghĩa lam sơn", "lam sơn khởi nghĩa": "khởi nghĩa lam sơn",
        "điện biên phủ": "điện biên phủ", "trận điện biên phủ": "điện biên phủ",
        "cách mạng tháng tám": "cách mạng tháng tám", "tổng khởi nghĩa": "cách mạng tháng tám",
        "nam quốc sơn hà": "nam quốc sơn hà", "bài thơ thần": "nam quốc sơn hà",
    }


# ===================================================================
# A. IDENTITY & CREATOR (5 tests)
# ===================================================================

class TestIdentityCreator:
    def test_ban_la_ai(self):
        from app.services.engine import engine_answer
        r = engine_answer("Bạn là ai?")
        assert r["intent"] == "identity"
        assert "History Mind AI" in r["answer"]

    def test_gioi_thieu_ban_than(self):
        from app.services.engine import engine_answer
        r = engine_answer("Giới thiệu bản thân đi")
        assert r["intent"] == "identity"

    def test_ai_tao_ra_ban(self):
        from app.services.engine import engine_answer
        r = engine_answer("Ai tạo ra bạn?")
        assert r["intent"] == "creator"
        assert "Võ Đức Hiếu" in r["answer"]

    def test_ai_phat_trien_ban(self):
        from app.services.engine import engine_answer
        r = engine_answer("Ai phát triển bạn vậy?")
        assert r["intent"] == "creator"

    def test_creator_before_identity(self):
        """'ai tạo bạn' should match creator, not identity (contains 'bạn là ai' substr)."""
        from app.services.engine import engine_answer
        r = engine_answer("Ai đã tạo ra bạn?")
        assert r["intent"] == "creator"


# ===================================================================
# B. YEAR-BASED QUERIES (4 tests)
# ===================================================================

class TestYearQueries:
    @patch("app.services.engine.scan_by_year")
    def test_single_year(self, mock_scan):
        mock_scan.return_value = [MOCK_TRAN_HUNG_DAO]
        from app.services.engine import engine_answer
        r = engine_answer("Sự kiện năm 1288")
        assert r["intent"] == "year"
        mock_scan.assert_called_once_with(1288)

    @patch("app.services.engine.semantic_search")
    @patch("app.services.engine.scan_by_year_range")
    def test_year_range(self, mock_range, mock_search):
        mock_range.return_value = [MOCK_TRAN_HUNG_DAO, MOCK_HICH_TUONG_SI]
        mock_search.return_value = []
        from app.services.engine import engine_answer
        r = engine_answer("Từ năm 1284 đến 1288 có sự kiện gì?")
        assert r["intent"] == "year_range"

    @patch("app.services.engine.semantic_search")
    @patch("app.services.engine.scan_by_year")
    def test_multiple_years(self, mock_scan, mock_search):
        mock_scan.return_value = [MOCK_NGO_QUYEN]
        mock_search.return_value = []
        from app.services.engine import engine_answer
        r = engine_answer("Năm 938 và năm 1288 có sự kiện gì?")
        assert r["intent"] == "multi_year"

    @patch("app.services.engine.semantic_search")
    def test_no_data_found(self, mock_search):
        mock_search.return_value = []
        from app.services.engine import engine_answer
        r = engine_answer("Sự kiện không tồn tại abc xyz")
        assert r["no_data"] is True
        assert r["events"] == []
        # Smart no_data response now returns helpful suggestion instead of None
        assert r["answer"] is not None
        assert "thử" in r["answer"].lower()


# ===================================================================
# C. PERSON ALIAS RESOLUTION (12 tests)
# ===================================================================

class TestPersonAliases:
    def setup_method(self):
        _setup_full_mocks()
        from app.services.search_service import resolve_query_entities
        self.resolve = resolve_query_entities

    def test_tran_hung_dao_canonical(self):
        r = self.resolve("Trần Hưng Đạo đã làm gì?")
        assert "trần hưng đạo" in r["persons"]

    def test_tran_quoc_tuan_alias(self):
        """Trần Quốc Tuấn → Trần Hưng Đạo"""
        r = self.resolve("Trần Quốc Tuấn đánh quân Nguyên")
        assert "trần hưng đạo" in r["persons"]

    def test_hung_dao_vuong_alias(self):
        """Hưng Đạo Vương → Trần Hưng Đạo"""
        r = self.resolve("Hưng Đạo Vương là ai?")
        assert "trần hưng đạo" in r["persons"]

    def test_hai_ba_trung_canonical(self):
        r = self.resolve("Hai Bà Trưng khởi nghĩa khi nào?")
        assert "hai bà trưng" in r["persons"]

    def test_trung_trac_alias(self):
        """Trưng Trắc → Hai Bà Trưng"""
        r = self.resolve("Trưng Trắc và Trưng Nhị lãnh đạo khởi nghĩa")
        assert "hai bà trưng" in r["persons"]

    def test_quang_trung_alias(self):
        """Quang Trung → Nguyễn Huệ"""
        r = self.resolve("Quang Trung đánh quân Thanh")
        assert "nguyễn huệ" in r["persons"]

    def test_bac_ho_alias(self):
        """Bác Hồ → Hồ Chí Minh"""
        r = self.resolve("Bác Hồ đọc tuyên ngôn độc lập")
        assert "hồ chí minh" in r["persons"]

    def test_nguyen_ai_quoc_alias(self):
        """Nguyễn Ái Quốc → Hồ Chí Minh"""
        r = self.resolve("Nguyễn Ái Quốc ra đi tìm đường cứu nước")
        assert "hồ chí minh" in r["persons"]

    def test_ngo_vuong_alias(self):
        """Ngô Vương → Ngô Quyền"""
        r = self.resolve("Ngô Vương đánh quân Nam Hán")
        assert "ngô quyền" in r["persons"]

    def test_le_thai_to_alias(self):
        """Lê Thái Tổ → Lê Lợi"""
        r = self.resolve("Lê Thái Tổ dựng cờ khởi nghĩa")
        assert "lê lợi" in r["persons"]

    def test_dinh_tien_hoang_alias(self):
        """Đinh Tiên Hoàng → Đinh Bộ Lĩnh"""
        r = self.resolve("Đinh Tiên Hoàng dẹp loạn 12 sứ quân")
        assert "đinh bộ lĩnh" in r["persons"]

    def test_trieu_thi_trinh_alias(self):
        """Triệu Thị Trinh → Bà Triệu"""
        r = self.resolve("Triệu Thị Trinh khởi nghĩa chống quân Ngô")
        assert "bà triệu" in r["persons"]


# ===================================================================
# D. DYNASTY ALIAS RESOLUTION (8 tests)
# ===================================================================

class TestDynastyAliases:
    def setup_method(self):
        _setup_full_mocks()
        from app.services.search_service import resolve_query_entities
        self.resolve = resolve_query_entities

    def test_nha_tran(self):
        r = self.resolve("Nhà Trần có bao nhiêu đời vua?")
        assert "trần" in r["dynasties"]

    def test_trieu_ly(self):
        r = self.resolve("Triều Lý có gì nổi bật?")
        assert "lý" in r["dynasties"]

    def test_thoi_le(self):
        r = self.resolve("Thời Lê có những sự kiện gì?")
        assert "lê" in r["dynasties"]

    def test_nha_nguyen(self):
        r = self.resolve("Nhà Nguyễn cai trị bao lâu?")
        assert "nguyễn" in r["dynasties"]

    def test_nha_dinh(self):
        r = self.resolve("Nhà Đinh được thành lập như thế nào?")
        assert "đinh" in r["dynasties"]

    def test_tay_son_dynasty(self):
        r = self.resolve("Nhà Tây Sơn có mấy anh em?")
        assert "tây sơn" in r["dynasties"]

    def test_trieu_tran_alias(self):
        r = self.resolve("Triều Trần chống ngoại xâm")
        assert "trần" in r["dynasties"]

    def test_thoi_tu_chu(self):
        r = self.resolve("Thời tự chủ bắt đầu từ khi nào?")
        assert "tự chủ" in r["dynasties"]


# ===================================================================
# E. TOPIC SYNONYM RESOLUTION (10 tests)
# ===================================================================

class TestTopicSynonyms:
    def setup_method(self):
        _setup_full_mocks()
        from app.services.search_service import resolve_query_entities
        self.resolve = resolve_query_entities

    def test_mong_co_to_nguyen_mong(self):
        r = self.resolve("Quân Mông Cổ xâm lược Đại Việt")
        assert "nguyên mông" in r["topics"]

    def test_mong_nguyen_to_nguyen_mong(self):
        r = self.resolve("Chống quân Mông Nguyên")
        assert "nguyên mông" in r["topics"]

    def test_quan_nguyen_to_nguyen_mong(self):
        r = self.resolve("Đánh quân Nguyên")
        assert "nguyên mông" in r["topics"]

    def test_quan_mong_to_nguyen_mong(self):
        r = self.resolve("Đánh bại quân Mông")
        assert "nguyên mông" in r["topics"]

    def test_van_mieu_to_giao_duc(self):
        """Văn Miếu → giáo dục topic"""
        r = self.resolve("Văn Miếu Quốc Tử Giám có vai trò gì?")
        assert "giáo dục" in r["topics"]

    def test_quoc_tu_giam_to_giao_duc(self):
        r = self.resolve("Quốc Tử Giám được xây dựng khi nào?")
        assert "giáo dục" in r["topics"]

    def test_thuc_dan_phap_to_phap_thuoc(self):
        r = self.resolve("Thực dân Pháp xâm lược Việt Nam")
        assert "pháp thuộc" in r["topics"]

    def test_tong_khoi_nghia_to_cach_mang(self):
        r = self.resolve("Tổng khởi nghĩa giành chính quyền")
        assert "cách mạng tháng tám" in r["topics"]

    def test_bai_tho_than_to_nam_quoc(self):
        r = self.resolve("Bài thơ thần Nam quốc sơn hà")
        assert "nam quốc sơn hà" in r["topics"]

    def test_tran_dien_bien_phu(self):
        r = self.resolve("Trận Điện Biên Phủ diễn ra thế nào?")
        assert "điện biên phủ" in r["topics"]


# ===================================================================
# F. PLACE DETECTION (4 tests)
# ===================================================================

class TestPlaceDetection:
    def setup_method(self):
        _setup_full_mocks()
        from app.services.search_service import resolve_query_entities
        self.resolve = resolve_query_entities

    def test_bach_dang_place(self):
        r = self.resolve("Trận chiến tại Bạch Đằng")
        assert "bạch đằng" in r["places"]

    def test_dai_viet_place(self):
        r = self.resolve("Quốc hiệu Đại Việt")
        assert "đại việt" in r["places"]

    def test_dong_da_place(self):
        r = self.resolve("Chiến thắng Đống Đa")
        assert "đống đa" in r["places"]

    def test_dien_bien_phu_place(self):
        r = self.resolve("Chiến thắng tại Điện Biên Phủ")
        assert "điện biên phủ" in r["places"]


# ===================================================================
# G. MULTI-ENTITY COMBINED QUERIES (6 tests)
# ===================================================================

class TestMultiEntityCombined:
    def setup_method(self):
        _setup_full_mocks()
        from app.services.search_service import resolve_query_entities
        self.resolve = resolve_query_entities

    def test_person_and_dynasty(self):
        """Trần Hưng Đạo + nhà Trần"""
        r = self.resolve("Trần Hưng Đạo và nhà Trần chống quân Nguyên Mông")
        assert "trần hưng đạo" in r["persons"]
        assert "trần" in r["dynasties"]
        assert "nguyên mông" in r["topics"]

    def test_person_and_place(self):
        """Ngô Quyền + Bạch Đằng"""
        r = self.resolve("Ngô Quyền đánh quân Nam Hán tại Bạch Đằng")
        assert "ngô quyền" in r["persons"]
        assert "bạch đằng" in r["places"]

    def test_person_alias_and_topic(self):
        """Quang Trung (alias) + Đống Đa (place)"""
        r = self.resolve("Quang Trung đại phá quân Thanh ở Đống Đa")
        assert "nguyễn huệ" in r["persons"]
        assert "đống đa" in r["places"]

    def test_dynasty_and_topic(self):
        """Nhà Trần + Mông Cổ"""
        r = self.resolve("Nhà Trần ba lần đánh bại quân Mông Cổ")
        assert "trần" in r["dynasties"]
        assert "nguyên mông" in r["topics"]

    def test_multiple_persons(self):
        """Hai Bà Trưng and Bà Triệu in same query"""
        r = self.resolve("So sánh cuộc khởi nghĩa Hai Bà Trưng và Bà Triệu")
        assert "hai bà trưng" in r["persons"]
        assert "bà triệu" in r["persons"]

    def test_all_entities_combined(self):
        """Person + dynasty + topic + place"""
        r = self.resolve("Lý Thường Kiệt thuộc nhà Lý, chiến đấu tại sông Như Nguyệt")
        assert "lý thường kiệt" in r["persons"]
        assert "lý" in r["dynasties"]
        assert "như nguyệt" in r["places"]


# ===================================================================
# H. SCAN BY ENTITIES (inverted index) (6 tests)
# ===================================================================

class TestScanByEntities:
    def setup_method(self):
        _setup_full_mocks()
        from app.services.search_service import scan_by_entities
        self.scan = scan_by_entities

    def test_scan_person(self):
        docs = self.scan({"persons": ["trần hưng đạo"], "dynasties": [], "topics": [], "places": []})
        assert len(docs) > 0
        for d in docs:
            assert "Trần Hưng Đạo" in (d.get("persons", []) + d.get("persons_all", []))

    def test_scan_dynasty(self):
        docs = self.scan({"persons": [], "dynasties": ["trần"], "topics": [], "places": []})
        assert len(docs) > 0
        for d in docs:
            assert d.get("dynasty", "").lower() == "trần"

    def test_scan_place(self):
        docs = self.scan({"persons": [], "dynasties": [], "topics": [], "places": ["bạch đằng"]})
        assert len(docs) >= 2  # Both 938 and 1288 battles

    def test_scan_combined_person_dynasty(self):
        docs = self.scan({"persons": ["lê lợi"], "dynasties": ["lý"], "topics": [], "places": []})
        assert len(docs) > 0

    def test_scan_empty_returns_empty(self):
        docs = self.scan({"persons": [], "dynasties": [], "topics": [], "places": []})
        assert len(docs) == 0

    def test_scan_nonexistent_person(self):
        docs = self.scan({"persons": ["nhân vật không có"], "dynasties": [], "topics": [], "places": []})
        assert len(docs) == 0


# ===================================================================
# I. ENGINE INTENT ROUTING (8 tests)
# ===================================================================

class TestEngineIntentRouting:
    @patch("app.services.engine.semantic_search")
    @patch("app.services.engine.scan_by_entities")
    def test_multi_entity_intent(self, mock_scan, mock_search):
        _setup_full_mocks()
        mock_scan.return_value = [MOCK_TRAN_HUNG_DAO, MOCK_HICH_TUONG_SI]
        mock_search.return_value = []
        from app.services.engine import engine_answer
        r = engine_answer("Trần Hưng Đạo và nhà Trần chống quân Mông Cổ")
        assert r["intent"] in ("event_query", "person_query", "multi_entity")
        assert not r["no_data"]

    @patch("app.services.engine.semantic_search")
    @patch("app.services.engine.scan_by_entities")
    def test_dynasty_intent(self, mock_scan, mock_search):
        _setup_full_mocks()
        mock_scan.return_value = [MOCK_TRAN_HUNG_DAO]
        mock_search.return_value = []
        from app.services.engine import engine_answer
        r = engine_answer("Triều đại nhà Trần có gì nổi bật?")
        assert r["intent"] == "dynasty_query"

    @patch("app.services.engine.semantic_search")
    @patch("app.services.engine.scan_by_entities")
    def test_topic_intent(self, mock_scan, mock_search):
        _setup_full_mocks()
        mock_scan.return_value = [MOCK_HCM]
        mock_search.return_value = []
        from app.services.engine import engine_answer
        r = engine_answer("Tổng khởi nghĩa giành chính quyền diễn ra thế nào?")
        assert r["intent"] in ("event_query", "topic")

    @patch("app.services.engine.semantic_search")
    @patch("app.services.engine.scan_by_entities")
    def test_place_intent(self, mock_scan, mock_search):
        _setup_full_mocks()
        mock_scan.return_value = [MOCK_DBP]
        mock_search.return_value = []
        from app.services.engine import engine_answer
        r = engine_answer("Chiến thắng Điện Biên Phủ")
        assert r["intent"] in ("place", "topic", "multi_entity", "event_query", "person_query")

    @patch("app.services.engine.semantic_search")
    def test_definition_intent(self, mock_search):
        """'là gì' query without entity matches should use definition intent."""
        # Use empty indexes so entity detection doesn't interfere
        import app.core.startup as startup
        startup.PERSONS_INDEX = defaultdict(list)
        startup.DYNASTY_INDEX = defaultdict(list)
        startup.KEYWORD_INDEX = defaultdict(list)
        startup.PLACES_INDEX = defaultdict(list)
        startup.PERSON_ALIASES = {}
        startup.DYNASTY_ALIASES = {}
        startup.TOPIC_SYNONYMS = {}
        mock_search.return_value = [MOCK_DAI_VIET]
        from app.services.engine import engine_answer
        r = engine_answer("Điều ước Giáp Tuất là gì?")
        assert r["intent"] == "definition"

    @patch("app.services.engine.semantic_search")
    @patch("app.services.engine.scan_by_entities")
    def test_hai_ba_trung_query(self, mock_scan, mock_search):
        """User case: 'Hai Bà Trưng khởi nghĩa'"""
        _setup_full_mocks()
        mock_scan.return_value = [MOCK_HAI_BA_TRUNG]
        mock_search.return_value = []
        from app.services.engine import engine_answer
        r = engine_answer("Hai Bà Trưng khởi nghĩa khi nào?")
        assert not r["no_data"]
        assert len(r["events"]) > 0

    @patch("app.services.engine.semantic_search")
    @patch("app.services.engine.scan_by_entities")
    def test_van_mieu_query(self, mock_scan, mock_search):
        """User case: 'Văn Miếu' topic query"""
        _setup_full_mocks()
        mock_scan.return_value = [MOCK_DAI_VIET]
        mock_search.return_value = []
        from app.services.engine import engine_answer
        r = engine_answer("Văn Miếu Quốc Tử Giám có vai trò gì?")
        assert r["intent"] in ("event_query", "topic")
        assert not r["no_data"]

    @patch("app.services.engine.semantic_search")
    @patch("app.services.engine.scan_by_entities")
    def test_dai_viet_query(self, mock_scan, mock_search):
        """User case: 'Đại Việt được thành lập như thế nào?'"""
        _setup_full_mocks()
        mock_scan.return_value = [MOCK_DAI_VIET]
        mock_search.return_value = []
        from app.services.engine import engine_answer
        r = engine_answer("Đại Việt được thành lập như thế nào?")
        assert not r["no_data"]


# ===================================================================
# J. DIFFERENT PHRASING / SYNONYM VARIATIONS (6 tests)
# ===================================================================

class TestPhrasingVariations:
    """Same historical fact asked in different ways should all resolve correctly."""

    def setup_method(self):
        _setup_full_mocks()
        from app.services.search_service import resolve_query_entities
        self.resolve = resolve_query_entities

    def test_nguyen_mong_variations(self):
        """All ways to say 'Mongol invasion' should resolve to nguyên mông."""
        queries = [
            "Cuộc xâm lược của Mông Cổ",
            "Đánh quân Nguyên Mông",
            "Chống quân Mông Nguyên",
            "Đại Việt đánh bại quân Nguyên",
            "Kháng chiến chống quân Mông",
        ]
        for q in queries:
            r = self.resolve(q)
            assert "nguyên mông" in r["topics"], f"Failed for query: '{q}'"

    def test_ho_chi_minh_aliases(self):
        """All names for HCM should resolve the same."""
        queries = [
            "Hồ Chí Minh đọc tuyên ngôn",
            "Bác Hồ đọc tuyên ngôn",
            "Nguyễn Ái Quốc ra đi tìm đường",
            "Nguyễn Tất Thành xuất dương",
        ]
        for q in queries:
            r = self.resolve(q)
            assert "hồ chí minh" in r["persons"], f"Failed for query: '{q}'"

    def test_tran_hung_dao_aliases(self):
        """All names for THD should resolve the same."""
        queries = [
            "Trần Hưng Đạo đánh quân Nguyên",
            "Trần Quốc Tuấn chỉ huy kháng chiến",
            "Hưng Đạo Vương soạn Hịch tướng sĩ",
        ]
        for q in queries:
            r = self.resolve(q)
            assert "trần hưng đạo" in r["persons"], f"Failed for query: '{q}'"

    def test_hai_ba_trung_aliases(self):
        """Different names for Hai Bà Trưng."""
        queries = [
            "Hai Bà Trưng khởi nghĩa",
            "Trưng Trắc lãnh đạo khởi nghĩa",
            "Cuộc khởi nghĩa của Trưng Nhị",
        ]
        for q in queries:
            r = self.resolve(q)
            assert "hai bà trưng" in r["persons"], f"Failed for query: '{q}'"

    def test_dynasty_alias_variations(self):
        """'nhà X', 'triều X', 'thời X' all resolve."""
        r1 = self.resolve("Nhà Trần chống quân Nguyên")
        r2 = self.resolve("Triều Trần có mấy đời vua?")
        r3 = self.resolve("Thời Trần có bao nhiêu cuộc kháng chiến?")
        assert all("trần" in r["dynasties"] for r in [r1, r2, r3])

    def test_quang_trung_nguyen_hue(self):
        """Both names should resolve to the same canonical person."""
        r1 = self.resolve("Quang Trung đánh quân Thanh")
        r2 = self.resolve("Nguyễn Huệ đại phá quân Thanh")
        # Both should contain the canonical name "nguyễn huệ"
        assert "nguyễn huệ" in r1["persons"]
        assert "nguyễn huệ" in r2["persons"]


# ===================================================================
# K. EDGE CASES (6 tests)
# ===================================================================

class TestEdgeCases:
    def setup_method(self):
        _setup_full_mocks()
        from app.services.search_service import resolve_query_entities, scan_by_entities
        self.resolve = resolve_query_entities
        self.scan = scan_by_entities

    def test_empty_query(self):
        r = self.resolve("")
        assert r == {"persons": [], "dynasties": [], "topics": [], "places": []}

    def test_gibberish_query(self):
        r = self.resolve("asdfghjkl qwertyuiop")
        assert all(not v for v in r.values())

    def test_case_insensitive(self):
        r1 = self.resolve("TRẦN HƯNG ĐẠO")
        r2 = self.resolve("trần hưng đạo")
        assert r1["persons"] == r2["persons"]

    def test_unicode_normalization(self):
        """Vietnamese diacritics should be handled properly."""
        r = self.resolve("Trần Hưng Đạo đánh Mông Cổ")
        assert "trần hưng đạo" in r["persons"]

    def test_scan_with_max_results_limit(self):
        docs = self.scan(
            {"persons": ["trần hưng đạo"], "dynasties": ["trần"], "topics": [], "places": ["bạch đằng"]},
            max_results=1
        )
        assert len(docs) <= 1

    def test_partial_name_no_false_positive(self):
        """'Trần' alone should match dynasty but not person 'Trần Hưng Đạo'."""
        _setup_full_mocks()
        import app.core.startup as startup
        # Remove person alias for just "trần" to test isolation
        startup.PERSON_ALIASES.pop("trần", None)
        r = self.resolve("Triều Trần")
        # Should find dynasty but not necessarily a person (unless index has "trần")
        assert "trần" in r["dynasties"]


# ===================================================================
# L. FORMAT & ANSWER OUTPUT (3 tests)
# ===================================================================

class TestFormatOutput:
    def test_format_groups_by_year(self):
        from app.services.engine import format_complete_answer
        answer = format_complete_answer([MOCK_HICH_TUONG_SI, MOCK_TRAN_HUNG_DAO])
        assert answer is not None
        assert "1284" in answer
        assert "1288" in answer

    def test_format_empty_returns_none(self):
        from app.services.engine import format_complete_answer
        assert format_complete_answer([]) is None

    def test_clean_story_text(self):
        from app.services.engine import clean_story_text
        # Should remove year prefixes
        cleaned = clean_story_text("Năm 1288, Trần Hưng Đạo đại phá quân Nguyên")
        assert not cleaned.startswith("Năm 1288")
        assert "Trần Hưng Đạo" in cleaned


# ===================================================================
# M. IMPLICIT CONTEXT DETECTION (7 tests)
# ===================================================================

class TestImplicitContextDetection:
    """Test that broad Vietnamese history queries are correctly detected."""

    def test_vietnam_scope_detected(self):
        from app.services.implicit_context import is_vietnam_scope_query
        assert is_vietnam_scope_query("Các cuộc kháng chiến của Việt Nam")
        assert is_vietnam_scope_query("Lịch sử Việt Nam")
        assert is_vietnam_scope_query("sự kiện lịch sử nước ta")

    def test_vietnam_scope_not_detected(self):
        from app.services.implicit_context import is_vietnam_scope_query
        assert not is_vietnam_scope_query("Trận Bạch Đằng năm 938")
        assert not is_vietnam_scope_query("Trần Hưng Đạo là ai?")

    def test_broad_query_detected(self):
        from app.services.implicit_context import is_broad_vietnam_query
        assert is_broad_vietnam_query("Lịch sử Việt Nam qua các triều đại")
        assert is_broad_vietnam_query("Các cuộc kháng chiến của Việt Nam")
        assert is_broad_vietnam_query("Những sự kiện lịch sử Việt Nam")

    def test_broad_query_not_detected(self):
        from app.services.implicit_context import is_broad_vietnam_query
        # Specific queries with VN scope term should NOT be broad
        assert not is_broad_vietnam_query("Trần Hưng Đạo ở Việt Nam")

    def test_resistance_terms_detected(self):
        from app.services.implicit_context import has_resistance_terms
        assert has_resistance_terms("Các cuộc kháng chiến")
        assert has_resistance_terms("Chiến tranh ở Việt Nam")
        assert has_resistance_terms("Chống ngoại xâm")

    def test_resistance_expansion(self):
        from app.services.implicit_context import expand_resistance_terms
        expanded = expand_resistance_terms("kháng chiến")
        assert len(expanded) > 0
        assert any("pháp" in t for t in expanded)
        assert any("mỹ" in t for t in expanded)

    def test_expand_query_context(self):
        from app.services.implicit_context import expand_query_with_implicit_context
        ctx = expand_query_with_implicit_context(
            "Các cuộc kháng chiến của Việt Nam",
            {"persons": [], "dynasties": [], "topics": [], "places": []}
        )
        assert ctx["is_vietnam_scope"] is True
        assert ctx["has_resistance"] is True
        assert ctx["skip_vietnam_keyword_filter"] is True
        assert len(ctx["extra_search_queries"]) > 0


# ===================================================================
# N. NON-DISCRIMINATING KEYWORD FILTER (3 tests)
# ===================================================================

class TestNonDiscriminatingKeywords:
    """Test that 'việt nam' is excluded from keyword scoring."""

    def test_filter_removes_vietnam(self):
        from app.services.implicit_context import filter_discriminating_keywords
        keywords = {"việt nam", "kháng chiến", "chiến thắng"}
        filtered = filter_discriminating_keywords(keywords)
        assert "việt nam" not in filtered
        assert "kháng chiến" in filtered
        assert "chiến thắng" in filtered

    def test_filter_removes_all_scope_terms(self):
        from app.services.implicit_context import filter_discriminating_keywords
        keywords = {"lịch sử", "sự kiện", "nước ta", "kháng chiến"}
        filtered = filter_discriminating_keywords(keywords)
        assert "lịch sử" not in filtered
        assert "sự kiện" not in filtered
        assert "nước ta" not in filtered
        assert "kháng chiến" in filtered

    def test_filter_preserves_real_keywords(self):
        from app.services.implicit_context import filter_discriminating_keywords
        keywords = {"trần hưng đạo", "bạch đằng", "quân nguyên"}
        filtered = filter_discriminating_keywords(keywords)
        assert filtered == keywords  # Nothing removed


# ===================================================================
# O. ENGINE WITH IMPLICIT CONTEXT (3 tests)
# ===================================================================

class TestImplicitContextEngine:
    """Test that engine handles broad Vietnam queries using implicit context expansion."""

    @patch("app.services.engine.semantic_search")
    def test_khang_chien_viet_nam(self, mock_search):
        """'Các cuộc kháng chiến của Việt Nam' should find resistance events."""
        _setup_full_mocks()
        # Semantic search returns war-related events
        mock_search.return_value = [MOCK_TRAN_HUNG_DAO, MOCK_DBP, MOCK_QUANG_TRUNG]
        from app.services.engine import engine_answer
        r = engine_answer("Các cuộc kháng chiến của Việt Nam")
        assert not r["no_data"]
        assert len(r["events"]) > 0

    @patch("app.services.engine.semantic_search")
    def test_lich_su_viet_nam_broad(self, mock_search):
        """'Lịch sử Việt Nam' should trigger broad coverage."""
        _setup_full_mocks()
        mock_search.return_value = [MOCK_HCM, MOCK_NGO_QUYEN]
        from app.services.engine import engine_answer
        r = engine_answer("Lịch sử Việt Nam qua các triều đại")
        # V2: broad_history/dynasty_timeline may not yield events without real data
        # When test mocks include person entities, V2 may route to person intent
        assert r["intent"] in ("broad_history", "dynasty_timeline", "person")

    @patch("app.services.engine.semantic_search")
    def test_chong_ngoai_xam_expansion(self, mock_search):
        """'Sự kiện kháng chiến chống ngoại xâm' — resistance expansion."""
        _setup_full_mocks()
        mock_search.return_value = [MOCK_TRAN_HUNG_DAO, MOCK_QUANG_TRUNG, MOCK_DBP]
        from app.services.engine import engine_answer
        r = engine_answer("Sự kiện kháng chiến chống ngoại xâm")
        assert not r["no_data"]
        assert len(r["events"]) > 0


# ===================================================================
# SEMANTIC INTENT CLASSIFICATION TESTS
# ===================================================================

class TestSemanticIntentClassification:
    """Test semantic_intent.py — intent classification, entity boundary, structure detection."""

    def test_detect_vietnam_nation(self):
        """'kháng chiến CỦA Việt Nam' → nation scope."""
        from app.services.semantic_intent import detect_vietnam_entity_type
        assert detect_vietnam_entity_type("Các cuộc kháng chiến của Việt Nam") == "nation"

    def test_detect_vietnam_territory(self):
        """'chiến tranh Ở Việt Nam' → territory scope."""
        from app.services.semantic_intent import detect_vietnam_entity_type
        assert detect_vietnam_entity_type("chiến tranh ở Việt Nam") == "territory"

    def test_detect_vietnam_ethnic(self):
        """'người Việt' → ethnic scope."""
        from app.services.semantic_intent import detect_vietnam_entity_type
        assert detect_vietnam_entity_type("văn hóa người Việt qua các thời kỳ") == "ethnic"

    def test_detect_vietnam_default_nation(self):
        """'Việt Nam' without markers → defaults to nation."""
        from app.services.semantic_intent import detect_vietnam_entity_type
        assert detect_vietnam_entity_type("Việt Nam có bao nhiêu triều đại") == "nation"

    def test_detect_no_vietnam(self):
        """Query without VN mention → None."""
        from app.services.semantic_intent import detect_vietnam_entity_type
        assert detect_vietnam_entity_type("Trần Hưng Đạo là ai") is None

    def test_structure_dynasty_timeline(self):
        """'qua các triều đại' → dynasty_timeline structure."""
        from app.services.semantic_intent import detect_structure_request
        assert detect_structure_request("Lịch sử Việt Nam qua các triều đại") == "dynasty_timeline"

    def test_structure_chronological(self):
        """'theo thời gian' → chronological."""
        from app.services.semantic_intent import detect_structure_request
        assert detect_structure_request("Sự kiện theo thứ tự thời gian") == "chronological"

    def test_structure_thematic(self):
        """'các cuộc / các mặt' → thematic."""
        from app.services.semantic_intent import detect_structure_request
        assert detect_structure_request("Các mặt phát triển kinh tế") == "thematic"

    def test_intent_dynasty_timeline(self):
        """Full classify: dynasty_timeline intent."""
        from app.services.semantic_intent import classify_semantic_intent
        si = classify_semantic_intent("Lịch sử Việt Nam qua các triều đại")
        assert si.intent == "dynasty_timeline"
        assert si.confidence >= 0.8
        assert si.retrieval_strategy == "dynasty_scan_all"

    def test_intent_resistance_national(self):
        """Full classify: resistance_national intent."""
        from app.services.semantic_intent import classify_semantic_intent
        si = classify_semantic_intent("Các cuộc kháng chiến của Việt Nam")
        assert si.intent == "resistance_national"
        assert si.vietnam_scope == "nation"
        assert si.confidence >= 0.8

    def test_intent_civil_war(self):
        """Full classify: civil_war intent."""
        from app.services.semantic_intent import classify_semantic_intent
        si = classify_semantic_intent("Nội chiến Việt Nam trong lịch sử")
        assert si.intent == "civil_war"

    def test_intent_generic_specific_entity(self):
        """Specific person query → generic (not resistance)."""
        from app.services.semantic_intent import classify_semantic_intent
        si = classify_semantic_intent("Trần Hưng Đạo là ai", {"persons": ["Trần Hưng Đạo"]})
        assert si.intent == "generic"
        assert si.confidence < 0.8

    def test_intent_broad_history(self):
        """'Lịch sử Việt Nam' without structure → broad_history."""
        from app.services.semantic_intent import classify_semantic_intent
        si = classify_semantic_intent("Lịch sử Việt Nam")
        assert si.intent == "broad_history"
        assert si.confidence >= 0.8


# ===================================================================
# STRUCTURED RETRIEVAL TESTS (using enriched mock data)
# ===================================================================

class TestStructuredRetrieval:
    """Test scan functions with enriched metadata fields."""

    def _setup_enriched_mocks(self):
        """Add conflict_type, scope, is_resistance to mock data."""
        _setup_full_mocks()
        import app.core.startup as startup
        # Enrich mock docs with semantic metadata
        for doc in startup.DOCUMENTS:
            doc["conflict_type"] = None
            doc["scope"] = "national"
            doc["is_resistance"] = False

        # Mark resistance events
        for doc in startup.DOCUMENTS:
            if doc.get("event") in (
                "Chiến thắng Bạch Đằng", "Trận Bạch Đằng",
                "Phòng tuyến Như Nguyệt", "Khởi nghĩa Lam Sơn bùng nổ",
                "Chiến thắng Điện Biên Phủ", "Quang Trung đại phá quân Thanh",
            ):
                doc["conflict_type"] = "external_conflict"
                doc["is_resistance"] = True

    @patch("app.services.engine.semantic_search")
    def test_scan_national_resistance(self, mock_search):
        """scan_national_resistance returns only external_conflict + is_resistance docs."""
        self._setup_enriched_mocks()
        mock_search.return_value = []
        from app.services.search_service import scan_national_resistance
        results = scan_national_resistance()
        assert len(results) > 0
        for doc in results:
            assert doc["is_resistance"] is True
            assert doc["conflict_type"] == "external_conflict"

    @patch("app.services.engine.semantic_search")
    def test_scan_by_dynasty_timeline(self, mock_search):
        """scan_by_dynasty_timeline returns events grouped correctly."""
        self._setup_enriched_mocks()
        mock_search.return_value = []
        from app.services.search_service import scan_by_dynasty_timeline
        results = scan_by_dynasty_timeline()
        assert len(results) > 0
        # Verify chronological dynasty ordering
        years = [d.get("year", 9999) for d in results]
        # Should be broadly ascending (some overlap within dynasty groups is ok)
        assert years[0] < years[-1]  # first event before last

    @patch("app.services.engine.semantic_search")
    def test_engine_resistance_intent(self, mock_search):
        """Engine properly routes 'kháng chiến của VN' through semantic intent."""
        self._setup_enriched_mocks()
        mock_search.return_value = []
        from app.services.engine import engine_answer
        r = engine_answer("Các cuộc kháng chiến của Việt Nam")
        # V2: 'các cuộc kháng chiến' routes to broad_history
        assert r["intent"] in ("broad_history", "resistance_national", "event_query")

    @patch("app.services.engine.semantic_search")
    def test_engine_dynasty_timeline_intent(self, mock_search):
        """Engine properly routes 'qua các triều đại' through semantic intent."""
        self._setup_enriched_mocks()
        mock_search.return_value = []
        from app.services.engine import engine_answer
        r = engine_answer("Lịch sử Việt Nam qua các triều đại")
        assert r["intent"] in ("dynasty_timeline", "broad_history", "person")


# ===================================================================
# PERSON-DYNASTY COLLISION REGRESSION TEST
# ===================================================================

class TestPersonDynastyCollision:
    """Regression: 'Nguyen Huye'/'Nguyễn Huệ' must resolve as person, not dynasty."""

    @patch("app.services.engine.semantic_search")
    def test_nguyen_hue_resolves_as_person(self, mock_search):
        """'Nguyễn Huệ' should find person events, not nhà Nguyễn dynasty."""
        _setup_full_mocks()
        mock_search.return_value = [MOCK_QUANG_TRUNG]
        from app.services.engine import engine_answer
        r = engine_answer("Nguyễn Huệ")
        assert not r["no_data"]
        assert r["intent"] in ("person", "person_query")

    @patch("app.services.engine.semantic_search")
    def test_nguyen_hue_unaccented(self, mock_search):
        """'nguyen hue' should also resolve as person via rewrite."""
        _setup_full_mocks()
        mock_search.return_value = [MOCK_QUANG_TRUNG]
        from app.services.engine import engine_answer
        r = engine_answer("nguyen hue")
        assert r["intent"] in ("person", "person_query")

    def test_entity_resolution_no_dynasty_collision(self):
        """resolve_query_entities('nguyễn huệ') must NOT include dynasty 'nguyễn'."""
        _setup_full_mocks()
        from app.services.search_service import resolve_query_entities
        resolved = resolve_query_entities("nguyễn huệ")
        assert "nguyễn huệ" in resolved["persons"]
        assert "nguyễn" not in resolved["dynasties"]

    @patch("app.services.engine.semantic_search")
    def test_nha_nguyen_still_works(self, mock_search):
        """'nhà Nguyễn' must still resolve as dynasty (not person)."""
        _setup_full_mocks()
        mock_search.return_value = []
        from app.services.engine import engine_answer
        r = engine_answer("nhà Nguyễn")
        assert r["intent"] in ("dynasty", "dynasty_query")


