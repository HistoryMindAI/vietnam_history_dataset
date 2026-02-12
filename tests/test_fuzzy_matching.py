"""
Test Fuzzy Matching and Flexible Query Understanding

Kiểm tra khả năng hiểu câu hỏi linh hoạt với typo, từ đồng nghĩa, và các biến thể.
"""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from collections import defaultdict

# Ensure ai-service is in path
AI_SERVICE_DIR = Path(__file__).parent.parent / "ai-service"
if str(AI_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_DIR))

# Mock heavy dependencies before import
sys.modules.setdefault('faiss', MagicMock())
sys.modules.setdefault('sentence_transformers', MagicMock())

import pytest


# Mock data for testing
MOCK_TRAN_HUNG_DAO_EVENT = {
    "year": 1288,
    "event": "Trận Bạch Đằng",
    "story": "Trần Hưng Đạo nhử địch vào bãi cọc ngầm trên sông Bạch Đằng, tiêu diệt thủy quân Nguyên.",
    "tone": "heroic",
    "persons": ["Trần Hưng Đạo"],
    "persons_all": ["Trần Hưng Đạo"],
    "places": ["Bạch Đằng"],
    "dynasty": "Trần",
    "keywords": ["bạch_đằng", "trần_hưng_đạo", "chiến_thắng", "nguyên"],
    "title": "Trận Bạch Đằng"
}

MOCK_NGUYEN_HUE_EVENT = {
    "year": 1789,
    "event": "Trận Đống Đa",
    "story": "Nguyễn Huệ đánh tan quân Thanh ở Đống Đa, giành thắng lợi vang dội.",
    "tone": "heroic",
    "persons": ["Nguyễn Huệ", "Quang Trung"],
    "persons_all": ["Nguyễn Huệ", "Quang Trung"],
    "places": ["Đống Đa"],
    "dynasty": "Tây Sơn",
    "keywords": ["đống_đa", "nguyễn_huệ", "quang_trung", "chiến_thắng"],
    "title": "Trận Đống Đa"
}


def _setup_mocks():
    """Setup mock data for tests."""
    import app.core.startup as startup
    
    startup.DOCUMENTS = [MOCK_TRAN_HUNG_DAO_EVENT, MOCK_NGUYEN_HUE_EVENT]
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
        "nguyễn huệ": "nguyễn huệ",
        "quang trung": "nguyễn huệ",
    }
    startup.DYNASTY_ALIASES = {
        "trần": "trần",
        "nhà trần": "trần",
        "tây sơn": "tây sơn",
    }
    startup.TOPIC_SYNONYMS = {
        "nguyên mông": "nguyên mông",
        "mông cổ": "nguyên mông",
        "thanh": "thanh",
    }


class TestFuzzyMatching:
    """Test fuzzy matching and flexible query understanding."""

    def setup_method(self):
        _setup_mocks()

    @patch("app.services.engine.semantic_search")
    @patch("app.services.engine.scan_by_entities")
    def test_typo_in_person_name(self, mock_scan, mock_search):
        """Test handling typo in person name: 'Tran Hung Dao' (missing accents)."""
        mock_scan.return_value = [MOCK_TRAN_HUNG_DAO_EVENT]
        mock_search.return_value = []
        
        from app.services.engine import engine_answer
        
        # Query with typo (missing accents)
        result = engine_answer("Tran Hung Dao la ai?")
        
        # Should still find the correct person
        assert not result["no_data"]
        events = result["events"]
        assert len(events) > 0
        
        # Should have Trần Hưng Đạo event
        years = [e.get("year") for e in events]
        assert 1288 in years

    @patch("app.services.engine.semantic_search")
    @patch("app.services.engine.scan_by_entities")
    def test_synonym_person_name(self, mock_scan, mock_search):
        """Test handling synonym: 'Quang Trung' = 'Nguyễn Huệ'."""
        mock_scan.return_value = [MOCK_NGUYEN_HUE_EVENT]
        mock_search.return_value = []
        
        from app.services.engine import engine_answer
        
        # Query with synonym
        result = engine_answer("Quang Trung đánh ai?")
        
        assert not result["no_data"]
        events = result["events"]
        assert len(events) > 0
        
        # Should have Nguyễn Huệ event
        years = [e.get("year") for e in events]
        assert 1789 in years

    @patch("app.services.engine.semantic_search")
    @patch("app.services.engine.scan_by_entities")
    def test_partial_match_person_name(self, mock_scan, mock_search):
        """Test partial match: 'Trần Hưng' should match 'Trần Hưng Đạo'."""
        mock_scan.return_value = [MOCK_TRAN_HUNG_DAO_EVENT]
        mock_search.return_value = []
        
        from app.services.engine import engine_answer
        
        result = engine_answer("Trần Hưng chiến thắng")
        
        assert not result["no_data"]
        events = result["events"]
        assert len(events) > 0

    @patch("app.services.engine.semantic_search")
    @patch("app.services.engine.scan_by_entities")
    def test_different_word_order(self, mock_scan, mock_search):
        """Test different word order: 'chiến thắng Trần Hưng Đạo' vs 'Trần Hưng Đạo chiến thắng'."""
        mock_scan.return_value = [MOCK_TRAN_HUNG_DAO_EVENT]
        mock_search.return_value = []
        
        from app.services.engine import engine_answer
        
        result1 = engine_answer("chiến thắng của Trần Hưng Đạo")
        result2 = engine_answer("Trần Hưng Đạo chiến thắng")
        
        # Both should return results
        assert not result1["no_data"]
        assert not result2["no_data"]
        
        # Both should have events
        assert len(result1["events"]) > 0
        assert len(result2["events"]) > 0

    @patch("app.services.engine.semantic_search")
    @patch("app.services.engine.scan_by_entities")
    def test_extra_filler_words(self, mock_scan, mock_search):
        """Test query with extra filler words."""
        mock_scan.return_value = [MOCK_TRAN_HUNG_DAO_EVENT]
        mock_search.return_value = []
        
        from app.services.engine import engine_answer
        
        result = engine_answer("Ơi bạn ơi, cho mình hỏi là Trần Hưng Đạo là ai vậy nhỉ?")
        
        # Should still understand the core question
        assert not result["no_data"]
        events = result["events"]
        assert len(events) > 0

    @patch("app.services.engine.semantic_search")
    @patch("app.services.engine.scan_by_entities")
    def test_casual_language(self, mock_scan, mock_search):
        """Test casual language: 'kể về' vs 'nói về' vs 'giới thiệu'."""
        mock_scan.return_value = [MOCK_TRAN_HUNG_DAO_EVENT]
        mock_search.return_value = []
        
        from app.services.engine import engine_answer
        
        result1 = engine_answer("kể về Trần Hưng Đạo")
        result2 = engine_answer("nói về Trần Hưng Đạo")
        result3 = engine_answer("giới thiệu Trần Hưng Đạo")
        
        # All should return results
        assert not result1["no_data"]
        assert not result2["no_data"]
        assert not result3["no_data"]

    def test_context7_fuzzy_matching(self):
        """Test Context7 fuzzy matching in calculate_relevance_score."""
        from app.services.context7_service import calculate_relevance_score, extract_query_focus
        
        # Query with slight typo
        query = "Trần Hưng Đao chiến thắng"  # "Đao" instead of "Đạo"
        focus = extract_query_focus(query)
        
        # Should still score high for Trần Hưng Đạo event
        score = calculate_relevance_score(MOCK_TRAN_HUNG_DAO_EVENT, focus, query)
        
        # Score should be > 0 (fuzzy match works)
        assert score > 0

    def test_context7_synonym_matching(self):
        """Test Context7 handles synonyms."""
        from app.services.context7_service import calculate_relevance_score, extract_query_focus
        
        # Query with synonym
        query = "Quang Trung đánh Thanh"
        focus = extract_query_focus(query)
        
        # Should score high for Nguyễn Huệ event (Quang Trung = Nguyễn Huệ)
        score = calculate_relevance_score(MOCK_NGUYEN_HUE_EVENT, focus, query)
        
        assert score > 0

    def test_context7_partial_keyword_match(self):
        """Test Context7 handles partial keyword matches."""
        from app.services.context7_service import calculate_relevance_score, extract_query_focus
        
        # Query with partial keyword
        query = "chiến thắng Bạch Đăng"  # "Đăng" instead of "Đằng"
        focus = extract_query_focus(query)
        
        score = calculate_relevance_score(MOCK_TRAN_HUNG_DAO_EVENT, focus, query)
        
        # Should still score reasonably (fuzzy match)
        assert score > 0

    @patch("app.services.engine.semantic_search")
    @patch("app.services.engine.scan_by_entities")
    def test_multiple_typos(self, mock_scan, mock_search):
        """Test handling multiple typos in one query."""
        mock_scan.return_value = [MOCK_TRAN_HUNG_DAO_EVENT]
        mock_search.return_value = []
        
        from app.services.engine import engine_answer
        
        # Multiple typos: "Tran Hung Dao" (no accents) + "chien thang" (no accents)
        result = engine_answer("Tran Hung Dao chien thang")
        
        # Should still find results
        assert not result["no_data"]
        events = result["events"]
        assert len(events) > 0

    @patch("app.services.engine.semantic_search")
    @patch("app.services.engine.scan_by_entities")
    def test_mixed_vietnamese_english(self, mock_scan, mock_search):
        """Test mixed Vietnamese-English query."""
        mock_scan.return_value = [MOCK_TRAN_HUNG_DAO_EVENT]
        mock_search.return_value = []
        
        from app.services.engine import engine_answer
        
        result = engine_answer("Who is Trần Hưng Đạo?")
        
        # Should understand despite mixed language
        assert not result["no_data"]
        events = result["events"]
        assert len(events) > 0

    def test_context7_filter_and_rank_fuzzy(self):
        """Test filter_and_rank_events with fuzzy matching."""
        from app.services.context7_service import filter_and_rank_events
        
        # Query with typo
        query = "Trần Hưng Đao chiến thắng Nguyên"
        events = [MOCK_TRAN_HUNG_DAO_EVENT, MOCK_NGUYEN_HUE_EVENT]
        
        filtered = filter_and_rank_events(events, query, max_results=10)
        
        # Should keep Trần Hưng Đạo event (fuzzy match)
        assert len(filtered) > 0
        years = [e.get("year") for e in filtered]
        assert 1288 in years
        
        # Trần Hưng Đạo should be ranked FIRST (more relevant)
        assert filtered[0]["year"] == 1288, "Trần Hưng Đạo event should be ranked first"
        
        # If Nguyễn Huệ event is included, it should be ranked LOWER
        if 1789 in years:
            # Find positions
            tran_pos = next(i for i, e in enumerate(filtered) if e["year"] == 1288)
            nguyen_pos = next(i for i, e in enumerate(filtered) if e["year"] == 1789)
            assert tran_pos < nguyen_pos, "Trần Hưng Đạo should rank higher than Nguyễn Huệ"
