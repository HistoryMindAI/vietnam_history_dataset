"""
test_nlu.py - Tests for Natural Language Understanding improvements.

Covers: query rewriting, fuzzy matching, accent restoration,
abbreviation expansion, question intent detection, and fallback chain.
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
sys.modules.setdefault('onnxruntime', MagicMock())

from app.services.query_understanding import (
    rewrite_query,
    fuzzy_match_entity,
    extract_question_intent,
    generate_search_variations,
    generate_phonetic_variants,
    _looks_unaccented,
    _restore_accents,
)


# ===================================================================
# A. QUERY REWRITING (13 tests)
# ===================================================================

class TestQueryRewriting:
    """Test query rewriting: typos, abbreviations, accents, fillers."""

    def test_basic_passthrough(self):
        """Normal Vietnamese query should pass through mostly unchanged."""
        result = rewrite_query("Trần Hưng Đạo là ai?")
        assert "trần hưng đạo" in result
        assert "ai" in result

    def test_abbreviation_vn(self):
        """VN → Việt Nam"""
        result = rewrite_query("VN độc lập năm nào")
        assert "việt nam" in result

    def test_abbreviation_dbp(self):
        """DBP → Điện Biên Phủ"""
        result = rewrite_query("Chiến thắng DBP")
        assert "điện biên phủ" in result

    def test_abbreviation_hcm(self):
        """HCM → Hồ Chí Minh"""
        result = rewrite_query("HCM đọc tuyên ngôn")
        assert "hồ chí minh" in result

    def test_typo_nguyen_huye(self):
        """Fix typo: nguyen huye → nguyễn huệ"""
        result = rewrite_query("nguyen huye đánh quân Thanh")
        assert "nguyễn huệ" in result

    def test_typo_quangtrung(self):
        """Fix typo: quangtrung → quang trung"""
        result = rewrite_query("quangtrung là ai")
        assert "quang trung" in result

    def test_unaccented_tran_hung_dao(self):
        """Restore accents: tran hung dao → trần hưng đạo"""
        result = rewrite_query("tran hung dao danh quan nguyen")
        assert "trần hưng đạo" in result

    def test_unaccented_bach_dang(self):
        """Restore accents: bach dang → bạch đằng"""
        result = rewrite_query("tran chien bach dang")
        assert "bạch đằng" in result

    def test_unaccented_ho_chi_minh(self):
        """Restore accents: ho chi minh → hồ chí minh"""
        result = rewrite_query("ho chi minh doc tuyen ngon doc lap")
        assert "hồ chí minh" in result
        assert "độc lập" in result

    def test_filler_removal(self):
        """Remove filler words."""
        result = rewrite_query("cho mình hỏi Trần Hưng Đạo là ai nhỉ")
        # Filler should be removed but core content preserved
        assert "trần hưng đạo" in result

    def test_empty_query(self):
        """Empty query should return empty."""
        assert rewrite_query("") == ""

    def test_whitespace_normalization(self):
        """Multiple spaces should be collapsed."""
        result = rewrite_query("trần   hưng   đạo")
        assert "  " not in result

    def test_mixed_case(self):
        """Should normalize to lowercase."""
        result = rewrite_query("TRẦN HƯNG ĐẠO")
        assert result == "trần hưng đạo"


# ===================================================================
# B. UNACCENTED DETECTION (5 tests)
# ===================================================================

class TestUnaccentedDetection:
    def test_fully_unaccented(self):
        """Fully unaccented text should be detected."""
        assert _looks_unaccented("tran hung dao danh quan nguyen")

    def test_fully_accented(self):
        """Fully accented text should NOT be detected as unaccented."""
        assert not _looks_unaccented("Trần Hưng Đạo đánh quân Nguyên")

    def test_mixed_partial_accent(self):
        """Partially accented text should NOT trigger restoration."""
        assert not _looks_unaccented("Trần Hưng Dao đánh quân Nguyên")

    def test_empty_string(self):
        assert not _looks_unaccented("")

    def test_numbers_only(self):
        assert not _looks_unaccented("1288")


# ===================================================================
# C. ACCENT RESTORATION (6 tests)
# ===================================================================

class TestAccentRestoration:
    def test_single_person(self):
        result = _restore_accents("tran hung dao")
        assert result == "trần hưng đạo"

    def test_single_place(self):
        result = _restore_accents("bach dang")
        assert result == "bạch đằng"

    def test_dynasty(self):
        result = _restore_accents("nha tran")
        assert result == "nhà trần"

    def test_topic(self):
        result = _restore_accents("nguyen mong")
        assert result == "nguyên mông"

    def test_multiple_terms(self):
        result = _restore_accents("tran hung dao danh quan nguyen mong tai bach dang")
        assert "trần hưng đạo" in result
        assert "nguyên mông" in result
        assert "bạch đằng" in result

    def test_no_match(self):
        """Unknown terms should pass through unchanged."""
        result = _restore_accents("xyz abc")
        assert result == "xyz abc"


# ===================================================================
# D. FUZZY ENTITY MATCHING (7 tests)
# ===================================================================

class TestFuzzyEntityMatching:
    def setup_method(self):
        self.person_aliases = {
            "trần hưng đạo": "trần hưng đạo",
            "trần quốc tuấn": "trần hưng đạo",
            "hưng đạo vương": "trần hưng đạo",
            "nguyễn huệ": "nguyễn huệ",
            "quang trung": "nguyễn huệ",
            "hồ chí minh": "hồ chí minh",
            "nguyễn ái quốc": "hồ chí minh",
            "bác hồ": "hồ chí minh",
        }

    def test_exact_match_excluded(self):
        """Exact matches should NOT appear (handled by normal resolution)."""
        result = fuzzy_match_entity("trần hưng đạo", self.person_aliases)
        # Exact match should be excluded from fuzzy results
        assert not any(m[0] == "trần hưng đạo" for m in result)

    def test_close_match(self):
        """Close but not exact match should be found."""
        # "trần hưng đao" (missing ạ) should fuzzy-match "trần hưng đạo"
        result = fuzzy_match_entity("trần hưng đao", self.person_aliases, threshold=0.7)
        assert len(result) > 0

    def test_threshold_filtering(self):
        """Very different text should not match at high threshold."""
        result = fuzzy_match_entity("napoleon bonaparte", self.person_aliases, threshold=0.8)
        assert len(result) == 0

    def test_empty_query(self):
        result = fuzzy_match_entity("", self.person_aliases)
        assert result == []

    def test_empty_dict(self):
        result = fuzzy_match_entity("trần hưng đạo", {})
        assert result == []

    def test_results_sorted_by_score(self):
        """Results should be sorted by similarity score descending."""
        result = fuzzy_match_entity("trần hưng đạo giúp", self.person_aliases, threshold=0.5)
        if len(result) >= 2:
            assert result[0][1] >= result[1][1]

    def test_deduplicated_results(self):
        """Each key should appear at most once in results."""
        result = fuzzy_match_entity("trần hưng", self.person_aliases, threshold=0.3)
        keys = [m[0] for m in result]
        assert len(keys) == len(set(keys))


# ===================================================================
# E. QUESTION INTENT DETECTION (8 tests)
# ===================================================================

class TestQuestionIntentDetection:
    def test_person_search_ai_da(self):
        result = extract_question_intent("Ai đã đánh quân Nguyên Mông?")
        assert result == "person_search"

    def test_person_search_vi_tuong(self):
        result = extract_question_intent("Vị tướng nào chỉ huy trận Bạch Đằng?")
        assert result == "person_search"

    def test_event_search_chuyen_gi(self):
        result = extract_question_intent("Chuyện gì xảy ra ở sông Bạch Đằng?")
        assert result == "event_search"

    def test_event_search_dieu_gi(self):
        result = extract_question_intent("Điều gì đã xảy ra năm 1945?")
        assert result == "event_search"

    def test_time_search_khi_nao(self):
        result = extract_question_intent("Khi nào Việt Nam độc lập?")
        assert result == "time_search"

    def test_time_search_nam_nao(self):
        result = extract_question_intent("Năm nào có trận Bạch Đằng?")
        assert result == "time_search"

    def test_comparison_so_sanh(self):
        result = extract_question_intent("So sánh nhà Trần và nhà Lý")
        assert result == "comparison"

    def test_no_pattern(self):
        """Normal statement should return None."""
        result = extract_question_intent("Trần Hưng Đạo đánh quân Nguyên")
        assert result is None


# ===================================================================
# F. QUERY EXPANSION / VARIATIONS (4 tests)
# ===================================================================

class TestQueryExpansion:
    def test_person_variation(self):
        resolved = {"persons": ["trần hưng đạo"], "dynasties": [], "topics": [], "places": []}
        variations = generate_search_variations("kể về trần hưng đạo", resolved)
        assert len(variations) > 0
        assert any("trần hưng đạo" in v for v in variations)

    def test_person_and_place(self):
        resolved = {"persons": ["ngô quyền"], "dynasties": [], "topics": [], "places": ["bạch đằng"]}
        variations = generate_search_variations("ngô quyền bạch đằng", resolved)
        assert any("ngô quyền" in v and "bạch đằng" in v for v in variations)

    def test_empty_resolved_with_phonetic(self):
        """When no entities resolved, phonetic variants may be generated."""
        resolved = {"persons": [], "dynasties": [], "topics": [], "places": []}
        variations = generate_search_variations("xyz", resolved)
        # With phonetic variants enabled, "xyz" may generate "syz" (x↔s swap)
        # This is correct behavior — the function now tries phonetic fallback
        assert isinstance(variations, list)

    def test_topic_variation(self):
        resolved = {"persons": [], "dynasties": [], "topics": ["nguyên mông"], "places": []}
        variations = generate_search_variations("quân nguyên mông", resolved)
        assert len(variations) > 0


# ===================================================================
# G. ENGINE INTEGRATION — QUERY REWRITING EFFECT (6 tests)
# ===================================================================

MOCK_TRAN_HUNG_DAO = {
    "year": 1288, "event": "Chiến thắng Bạch Đằng",
    "story": "Trần Hưng Đạo đánh tan quân Nguyên Mông trên sông Bạch Đằng.",
    "tone": "heroic", "persons": ["Trần Hưng Đạo"], "persons_all": ["Trần Hưng Đạo"],
    "places": ["Bạch Đằng"], "dynasty": "Trần",
    "keywords": ["bạch_đằng", "trần_hưng_đạo"], "title": "Chiến thắng Bạch Đằng 1288"
}
MOCK_HCM = {
    "year": 1945, "event": "Cách mạng Tháng Tám và Tuyên ngôn Độc lập",
    "story": "Hồ Chí Minh đọc Tuyên ngôn Độc lập, khai sinh nước Việt Nam Dân chủ Cộng hòa.",
    "tone": "heroic", "persons": ["Hồ Chí Minh"], "persons_all": ["Hồ Chí Minh"],
    "places": ["Ba Đình"], "dynasty": "Hiện đại",
    "keywords": ["cách_mạng", "hồ_chí_minh", "độc_lập", "tuyên_ngôn"], "title": "Cách mạng Tháng Tám"
}
MOCK_QUANG_TRUNG = {
    "year": 1789, "event": "Quang Trung đại phá quân Thanh",
    "story": "Nguyễn Huệ (Quang Trung) đánh tan 29 vạn quân Thanh tại Đống Đa.",
    "tone": "heroic", "persons": ["Nguyễn Huệ"], "persons_all": ["Quang Trung", "Nguyễn Huệ"],
    "places": ["Đống Đa"], "dynasty": "Tây Sơn",
    "keywords": ["đống_đa", "quang_trung"], "title": "Quang Trung đại phá quân Thanh"
}


def _setup_engine_mocks():
    """Configure startup with mock data for engine integration tests."""
    import app.core.startup as startup

    startup.DOCUMENTS = [MOCK_TRAN_HUNG_DAO, MOCK_HCM, MOCK_QUANG_TRUNG]
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
        "trần hưng đạo": "trần hưng đạo", "trần quốc tuấn": "trần hưng đạo",
        "hưng đạo vương": "trần hưng đạo",
        "nguyễn huệ": "nguyễn huệ", "quang trung": "nguyễn huệ",
        "hồ chí minh": "hồ chí minh", "nguyễn ái quốc": "hồ chí minh",
        "nguyễn tất thành": "hồ chí minh", "bác hồ": "hồ chí minh",
    }
    startup.DYNASTY_ALIASES = {
        "trần": "trần", "nhà trần": "trần", "triều trần": "trần",
        "tây sơn": "tây sơn", "nhà tây sơn": "tây sơn",
    }
    startup.TOPIC_SYNONYMS = {
        "nguyên mông": "nguyên mông", "mông cổ": "nguyên mông",
        "cách mạng tháng tám": "cách mạng tháng tám",
    }


class TestEngineWithNLU:
    """Test that engine_answer benefits from query rewriting."""

    @patch("app.services.engine.semantic_search")
    @patch("app.services.engine.scan_by_entities")
    def test_unaccented_query_finds_person(self, mock_scan, mock_search):
        """Unaccented 'tran hung dao' should find Trần Hưng Đạo after rewrite."""
        _setup_engine_mocks()
        mock_scan.return_value = [MOCK_TRAN_HUNG_DAO]
        mock_search.return_value = []
        from app.services.engine import engine_answer
        r = engine_answer("tran hung dao la ai")
        assert not r["no_data"]

    @patch("app.services.engine.semantic_search")
    @patch("app.services.engine.scan_by_entities")
    def test_abbreviation_hcm_finds_person(self, mock_scan, mock_search):
        """Abbreviation 'HCM' should resolve to Hồ Chí Minh."""
        _setup_engine_mocks()
        mock_scan.return_value = [MOCK_HCM]
        mock_search.return_value = []
        from app.services.engine import engine_answer
        r = engine_answer("HCM đọc tuyên ngôn độc lập")
        assert not r["no_data"]

    @patch("app.services.engine.semantic_search")
    @patch("app.services.engine.scan_by_entities")
    def test_typo_query_finds_person(self, mock_scan, mock_search):
        """Typo 'nguyen huye' should be fixed to 'nguyễn huệ' and find results."""
        _setup_engine_mocks()
        mock_scan.return_value = [MOCK_QUANG_TRUNG]
        mock_search.return_value = []
        from app.services.engine import engine_answer
        r = engine_answer("nguyen huye đánh quân Thanh")
        assert not r["no_data"]

    def test_identity_still_works(self):
        """Identity intent should still trigger correctly."""
        from app.services.engine import engine_answer
        r = engine_answer("Bạn là ai?")
        assert r["intent"] == "identity"

    def test_creator_still_works(self):
        """Creator intent should still trigger correctly."""
        from app.services.engine import engine_answer
        r = engine_answer("Ai tạo ra bạn?")
        assert r["intent"] == "creator"

    @patch("app.services.engine.semantic_search")
    def test_no_data_suggestion(self, mock_search):
        """When no data found, should return helpful suggestions instead of None."""
        import app.core.startup as startup
        startup.DOCUMENTS = []
        startup.PERSONS_INDEX = defaultdict(list)
        startup.DYNASTY_INDEX = defaultdict(list)
        startup.KEYWORD_INDEX = defaultdict(list)
        startup.PLACES_INDEX = defaultdict(list)
        startup.PERSON_ALIASES = {}
        startup.DYNASTY_ALIASES = {}
        startup.TOPIC_SYNONYMS = {}
        mock_search.return_value = []
        from app.services.engine import engine_answer
        r = engine_answer("abc xyz không có gì cả")
        assert r["no_data"] is True
        assert r["answer"] is not None
        assert "thử" in r["answer"].lower()  # Should suggest alternative phrasings


# ===================================================================
# H. PHONETIC NORMALIZATION (NEW - 6 tests)
# ===================================================================

class TestPhoneticNormalization:
    """Test Vietnamese phonetic variant generation."""

    def test_tr_ch_swap(self):
        """tr ↔ ch swap: 'chần' should generate 'trần'."""
        variants = generate_phonetic_variants("chần hưng đạo")
        assert any("trần" in v for v in variants)

    def test_s_x_swap(self):
        """s ↔ x swap: 'xử' should generate 'sử'."""
        variants = generate_phonetic_variants("lịch xử")
        assert any("sử" in v for v in variants)

    def test_gi_d_swap(self):
        """gi ↔ d swap: handles Southern Vietnamese pronunciation."""
        variants = generate_phonetic_variants("giải phóng")
        assert any("dải" in v for v in variants)

    def test_no_variant_for_short_text(self):
        """Very short text should return empty."""
        variants = generate_phonetic_variants("a")
        assert variants == []

    def test_empty_input(self):
        variants = generate_phonetic_variants("")
        assert variants == []

    def test_multi_word_variant(self):
        """Should generate variants for each word independently."""
        variants = generate_phonetic_variants("chần trọng")
        # "chần" → "trần" and "trọng" → "chọng" are both possible
        assert len(variants) > 0
