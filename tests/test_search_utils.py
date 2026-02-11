"""
test_search_utils.py - Tests for search utility functions and startup indexing.

Tests: extract_important_keywords, check_query_relevance,
       deduplicate_and_enrich, _build_inverted_indexes, _load_knowledge_base.
"""
import sys
import os
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
from collections import defaultdict

AI_SERVICE_DIR = Path(__file__).parent.parent / "ai-service"
if str(AI_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_DIR))

sys.modules.setdefault('faiss', MagicMock())
sys.modules.setdefault('sentence_transformers', MagicMock())

# ===================================================================
# MOCK DATA
# ===================================================================

DOC_TRAN = {
    "year": 1288, "event": "Chiến thắng Bạch Đằng", "title": "Trận Bạch Đằng",
    "story": "Trần Hưng Đạo đánh tan quân Nguyên Mông trên sông Bạch Đằng.",
    "tone": "heroic", "persons": ["Trần Hưng Đạo"], "persons_all": ["Trần Hưng Đạo"],
    "places": ["Bạch Đằng"], "dynasty": "Trần",
    "keywords": ["bạch_đằng", "trần_hưng_đạo"], "period": ""
}

DOC_TRAN_SIMILAR = {
    "year": 1288, "event": "Đại thắng Bạch Đằng",
    "story": "Trần Hưng Đạo đại phá quân Nguyên Mông.",
    "tone": "heroic", "persons": ["Trần Hưng Đạo"], "persons_all": [],
    "places": ["Bạch Đằng"], "dynasty": "Trần",
    "keywords": ["bạch_đằng"], "title": ""
}

DOC_LY = {
    "year": 1077, "event": "Phòng tuyến Như Nguyệt", "title": "Phòng tuyến Như Nguyệt",
    "story": "Lý Thường Kiệt chặn quân Tống ở sông Như Nguyệt.",
    "tone": "heroic", "persons": ["Lý Thường Kiệt"], "persons_all": ["Lý Thường Kiệt"],
    "places": ["Như Nguyệt"], "dynasty": "Lý",
    "keywords": ["lý_thường_kiệt"], "period": ""
}

DOC_UNRELATED = {
    "year": 1802, "event": "Gia Long thống nhất", "title": "Thống nhất lãnh thổ",
    "story": "Nguyễn Ánh lên ngôi, đặt quốc hiệu Việt Nam.",
    "tone": "neutral", "persons": ["Nguyễn Ánh"], "persons_all": [],
    "places": [], "dynasty": "Nguyễn",
    "keywords": ["thống_nhất", "việt_nam"], "period": ""
}


# ===================================================================
# A. extract_important_keywords (10 tests)
# ===================================================================

class TestExtractImportantKeywords:
    def setup_method(self):
        from app.services.search_service import extract_important_keywords
        self.extract = extract_important_keywords

    def test_single_word(self):
        result = self.extract("Trần Hưng Đạo")
        assert "trần" in result or "hưng" in result

    def test_multi_word_phrase(self):
        result = self.extract("Cuộc chiến Nguyên Mông")
        assert "nguyên_mông" in result

    def test_remove_stop_words(self):
        result = self.extract("là gì và có những gì")
        # All stop words, should extract nothing meaningful
        assert "là" not in result
        assert "gì" not in result

    def test_empty_string(self):
        assert self.extract("") == set()

    def test_historical_phrase_bach_dang(self):
        result = self.extract("Chiến thắng Bạch Đằng vĩ đại")
        assert "bạch_đằng" in result

    def test_historical_phrase_dien_bien_phu(self):
        result = self.extract("Trận Điện Biên Phủ")
        assert "điện_biên_phủ" in result

    def test_combined_phrases_and_words(self):
        result = self.extract("Nhà Trần chống Nguyên Mông")
        assert "nguyên_mông" in result
        assert "nhà_trần" in result

    def test_special_chars_removed(self):
        result = self.extract("Trần Hưng Đạo (1228-1300)?")
        assert "trần" in result

    def test_short_words_excluded(self):
        """Words <= 2 chars should be ignored."""
        result = self.extract("có ai ở đó")
        assert len(result) == 0

    def test_phrase_independence(self):
        result = self.extract("Khởi nghĩa Lam Sơn")
        assert "khởi_nghĩa" in result


# ===================================================================
# B. check_query_relevance (8 tests)
# ===================================================================

class TestCheckQueryRelevance:
    def setup_method(self):
        from app.services.search_service import check_query_relevance
        self.check = check_query_relevance

    def test_relevant_person_match(self):
        assert self.check("Trần Hưng Đạo", DOC_TRAN) is True

    def test_relevant_place_match(self):
        assert self.check("Bạch Đằng", DOC_TRAN) is True

    def test_relevant_keyword_match(self):
        assert self.check("trần_hưng_đạo", DOC_TRAN) is True

    def test_irrelevant_doc(self):
        assert self.check("Điện Biên Phủ", DOC_TRAN) is False

    def test_dynasty_filter_match(self):
        """Dynasty filter should accept any doc from same dynasty."""
        assert self.check("Bất kỳ câu hỏi nào", DOC_TRAN, "Trần") is True

    def test_dynasty_filter_partial_match(self):
        """'Lê' should match 'Lê sơ' or 'Lê trung hưng'."""
        doc = {**DOC_LY, "dynasty": "Lê sơ"}
        assert self.check("Thời Lê", doc, "Lê") is True

    def test_dynasty_filter_mismatch(self):
        assert self.check("Thời Lý", DOC_TRAN, "Lý") is False

    def test_empty_keywords_accepts_all(self):
        """If no important keywords found, accept the doc."""
        assert self.check("và có là gì", DOC_TRAN) is True


# ===================================================================
# C. deduplicate_and_enrich (8 tests)
# ===================================================================

class TestDeduplicateAndEnrich:
    def setup_method(self):
        from app.services.engine import deduplicate_and_enrich
        self.dedup = deduplicate_and_enrich

    def test_empty_list(self):
        assert self.dedup([]) == []

    def test_single_event(self):
        result = self.dedup([DOC_TRAN])
        assert len(result) == 1

    def test_duplicate_events_merged(self):
        """Two similar events about Bạch Đằng 1288 should merge into one."""
        result = self.dedup([DOC_TRAN, DOC_TRAN_SIMILAR])
        assert len(result) == 1

    def test_different_events_kept(self):
        """Events from different years should all be kept."""
        result = self.dedup([DOC_TRAN, DOC_LY, DOC_UNRELATED])
        assert len(result) == 3

    def test_max_events_limit(self):
        result = self.dedup([DOC_TRAN, DOC_LY, DOC_UNRELATED], max_events=2)
        assert len(result) <= 2

    def test_sorted_by_year(self):
        result = self.dedup([DOC_UNRELATED, DOC_TRAN, DOC_LY])
        years = [e.get("year") for e in result]
        assert years == sorted(years)

    def test_merged_persons_combined(self):
        """Merged events should combine persons from both."""
        doc1 = {**DOC_TRAN, "persons": ["Trần Hưng Đạo"]}
        doc2 = {**DOC_TRAN_SIMILAR, "persons": ["Trần Khánh Dư"]}
        result = self.dedup([doc1, doc2])
        all_persons = result[0].get("persons", [])
        assert "Trần Hưng Đạo" in all_persons

    def test_longer_story_preserved(self):
        """The longer story text should be preserved after merge."""
        short = {**DOC_TRAN_SIMILAR, "story": "Ngắn."}
        long = {**DOC_TRAN, "story": "Trần Hưng Đạo đánh tan quân Nguyên Mông trên sông Bạch Đằng."}
        result = self.dedup([short, long])
        assert len(result[0].get("story", "")) > 10


# ===================================================================
# D. Startup: _build_inverted_indexes (6 tests)
# ===================================================================

class TestBuildInvertedIndexes:
    def setup_method(self):
        import app.core.startup as startup
        self.startup = startup

    def test_persons_indexed(self):
        self.startup.DOCUMENTS = [DOC_TRAN, DOC_LY]
        self.startup._build_inverted_indexes()
        assert "trần hưng đạo" in self.startup.PERSONS_INDEX
        assert "lý thường kiệt" in self.startup.PERSONS_INDEX

    def test_dynasty_indexed(self):
        self.startup.DOCUMENTS = [DOC_TRAN, DOC_LY]
        self.startup._build_inverted_indexes()
        assert "trần" in self.startup.DYNASTY_INDEX
        assert "lý" in self.startup.DYNASTY_INDEX

    def test_keywords_indexed(self):
        self.startup.DOCUMENTS = [DOC_TRAN]
        self.startup._build_inverted_indexes()
        assert "bạch đằng" in self.startup.KEYWORD_INDEX

    def test_places_indexed(self):
        self.startup.DOCUMENTS = [DOC_TRAN]
        self.startup._build_inverted_indexes()
        assert "bạch đằng" in self.startup.PLACES_INDEX

    def test_empty_documents(self):
        self.startup.DOCUMENTS = []
        self.startup._build_inverted_indexes()
        assert len(self.startup.PERSONS_INDEX) == 0

    def test_index_points_to_correct_doc(self):
        self.startup.DOCUMENTS = [DOC_TRAN, DOC_LY]
        self.startup._build_inverted_indexes()
        indices = self.startup.PERSONS_INDEX["trần hưng đạo"]
        assert 0 in indices  # DOC_TRAN is at index 0


# ===================================================================
# E. Startup: _load_knowledge_base (6 tests)
# ===================================================================

class TestLoadKnowledgeBase:
    def setup_method(self):
        import app.core.startup as startup
        self.startup = startup

    def test_load_real_knowledge_base(self):
        """Test loading the actual knowledge_base.json file."""
        kb_path = AI_SERVICE_DIR / "knowledge_base.json"
        if not kb_path.exists():
            return  # Skip if file doesn't exist
        with patch.object(self.startup, 'KNOWLEDGE_BASE_PATH', str(kb_path)):
            # Patch the config value used inside the function
            from app.core.config import KNOWLEDGE_BASE_PATH
            with patch('app.core.startup.KNOWLEDGE_BASE_PATH', str(kb_path)):
                self.startup._load_knowledge_base()
        assert len(self.startup.PERSON_ALIASES) > 0
        assert len(self.startup.DYNASTY_ALIASES) > 0
        assert len(self.startup.TOPIC_SYNONYMS) > 0

    def test_missing_file_no_crash(self):
        """Missing file should not crash, just warn."""
        with patch('app.core.startup.KNOWLEDGE_BASE_PATH', '/nonexistent/path.json'):
            self.startup._load_knowledge_base()
        assert len(self.startup.PERSON_ALIASES) == 0

    def test_alias_maps_to_canonical(self):
        """Verify alias → canonical mapping structure."""
        kb = {
            "person_aliases": {"nguyễn huệ": ["quang trung"]},
            "topic_synonyms": {},
            "dynasty_aliases": {}
        }
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump(kb, f)
            tmp_path = f.name
        try:
            with patch('app.core.startup.KNOWLEDGE_BASE_PATH', tmp_path):
                self.startup._load_knowledge_base()
            assert self.startup.PERSON_ALIASES.get("quang trung") == "nguyễn huệ"
            assert self.startup.PERSON_ALIASES.get("nguyễn huệ") == "nguyễn huệ"
        finally:
            os.unlink(tmp_path)

    def test_dynasty_alias_mapping(self):
        kb = {
            "person_aliases": {},
            "topic_synonyms": {},
            "dynasty_aliases": {"trần": ["nhà trần", "triều trần"]}
        }
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump(kb, f)
            tmp_path = f.name
        try:
            with patch('app.core.startup.KNOWLEDGE_BASE_PATH', tmp_path):
                self.startup._load_knowledge_base()
            assert self.startup.DYNASTY_ALIASES.get("nhà trần") == "trần"
            assert self.startup.DYNASTY_ALIASES.get("triều trần") == "trần"
        finally:
            os.unlink(tmp_path)

    def test_topic_synonym_mapping(self):
        kb = {
            "person_aliases": {},
            "topic_synonyms": {"nguyên mông": ["mông cổ", "mông nguyên"]},
            "dynasty_aliases": {}
        }
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump(kb, f)
            tmp_path = f.name
        try:
            with patch('app.core.startup.KNOWLEDGE_BASE_PATH', tmp_path):
                self.startup._load_knowledge_base()
            assert self.startup.TOPIC_SYNONYMS.get("mông cổ") == "nguyên mông"
        finally:
            os.unlink(tmp_path)

    def test_invalid_json_no_crash(self):
        """Corrupt JSON should not crash."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{invalid json!!!")
            tmp_path = f.name
        try:
            with patch('app.core.startup.KNOWLEDGE_BASE_PATH', tmp_path):
                self.startup._load_knowledge_base()
            # Should not crash, aliases reset to empty
            assert len(self.startup.PERSON_ALIASES) == 0
        finally:
            os.unlink(tmp_path)


# ===================================================================
# F. detect_dynasty_from_query wrapper (4 tests)
# ===================================================================

class TestDetectDynastyWrapper:
    def setup_method(self):
        import app.core.startup as startup
        startup.DYNASTY_ALIASES = {
            "trần": "trần", "nhà trần": "trần",
            "lý": "lý", "nhà lý": "lý",
        }
        startup.DYNASTY_INDEX = defaultdict(list, {"trần": [0], "lý": [1]})
        startup.PERSONS_INDEX = defaultdict(list)
        startup.KEYWORD_INDEX = defaultdict(list)
        startup.PLACES_INDEX = defaultdict(list)
        startup.PERSON_ALIASES = {}
        startup.TOPIC_SYNONYMS = {}

    def test_detect_nha_tran(self):
        from app.services.search_service import detect_dynasty_from_query
        assert detect_dynasty_from_query("Nhà Trần có mấy đời vua?") == "trần"

    def test_detect_no_dynasty(self):
        from app.services.search_service import detect_dynasty_from_query
        assert detect_dynasty_from_query("Bài thơ nào hay nhất?") is None

    def test_detect_nha_ly(self):
        from app.services.search_service import detect_dynasty_from_query
        assert detect_dynasty_from_query("Nhà Lý dời đô") == "lý"

    def test_detect_place_wrapper(self):
        import app.core.startup as startup
        startup.PLACES_INDEX = defaultdict(list, {"bạch đằng": [0]})
        from app.services.search_service import detect_place_from_query
        assert detect_place_from_query("Trận Bạch Đằng") == "bạch đằng"
