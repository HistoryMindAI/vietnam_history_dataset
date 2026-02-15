"""
test_edge_cases.py — Edge Case Coverage Tests

Tests for edge cases not covered by existing tests:
- Empty query handling
- Special characters only queries
- Year out of bounds
- Events with missing required fields
- FAISS returns no results
- Knowledge base entity not found
- Empty document store
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'ai-service'))

from app.services.engine import engine_answer, extract_single_year, extract_year_range
from app.services.search_service import semantic_search, scan_by_entities, resolve_query_entities
from app.services.answer_synthesis import synthesize_answer
from app.services.intent_classifier import classify_intent, QueryAnalysis
import app.core.startup as startup


class TestEmptyQueryHandling:
    """Test handling of empty/whitespace queries"""

    def test_engine_answer_empty_string(self):
        """Should handle empty query string"""
        result = engine_answer("")
        assert isinstance(result, dict)
        assert result["no_data"] is True or result["answer"]

    def test_engine_answer_whitespace_only(self):
        """Should handle whitespace-only query"""
        result = engine_answer("   \n\t   ")
        assert isinstance(result, dict)
        assert result["no_data"] is True or result["answer"]

    def test_semantic_search_empty_query(self, monkeypatch):
        """semantic_search should handle empty query"""
        monkeypatch.setattr(startup, "index", object())
        monkeypatch.setattr(startup, "session", object())
        monkeypatch.setattr(startup, "DOCUMENTS", [])

        result = semantic_search("")
        assert isinstance(result, list)

    def test_resolve_entities_empty_query(self):
        """resolve_query_entities should handle empty query"""
        result = resolve_query_entities("")
        assert result == {
            "persons": [],
            "dynasties": [],
            "topics": [],
            "places": []
        }


class TestSpecialCharactersQuery:
    """Test queries with only special characters"""

    def test_query_with_only_punctuation(self):
        """Should handle query with only punctuation"""
        result = engine_answer("!@#$%^&*()")
        assert isinstance(result, dict)
        assert result["no_data"] is True or result["answer"]

    def test_query_with_unicode_symbols(self):
        """Should handle query with Unicode symbols"""
        result = engine_answer("😀🎉🔥")
        assert isinstance(result, dict)

    def test_query_with_mixed_special_chars(self):
        """Should handle query with mixed special characters"""
        result = engine_answer("???...!!!---")
        assert isinstance(result, dict)

    def test_query_with_sql_injection_attempt(self):
        """Should handle SQL injection attempt safely"""
        result = engine_answer("'; DROP TABLE events; --")
        assert isinstance(result, dict)
        # Should not crash or execute anything malicious


class TestYearOutOfBounds:
    """Test year extraction and queries with invalid years"""

    def test_negative_year_extraction(self):
        """Should not extract negative years"""
        result = extract_single_year("năm -500")
        assert result is None

    def test_year_too_large(self):
        """Should not extract years > 2025"""
        result = extract_single_year("năm 3000")
        assert result is None

    def test_year_too_small(self):
        """Should not extract years < 40"""
        result = extract_single_year("năm 10")
        assert result is None

    def test_year_range_with_negative_start(self):
        """Should reject year range with negative start"""
        result = extract_year_range("từ năm -100 đến năm 500")
        assert result is None

    def test_year_range_with_invalid_end(self):
        """Should reject year range with end > 2025"""
        result = extract_year_range("từ năm 1945 đến năm 3000")
        assert result is None

    def test_year_range_backwards(self):
        """Should reject year range where start > end"""
        result = extract_year_range("từ năm 1945 đến năm 1000")
        assert result is None

    def test_query_with_year_zero(self):
        """Should handle query with year 0"""
        result = engine_answer("năm 0")
        assert isinstance(result, dict)
        # Year 0 should be rejected (< 40)
        assert result["intent"] != "year"

    def test_query_with_year_boundary_39(self):
        """Should reject year 39 (just below threshold)"""
        result = extract_single_year("năm 39")
        assert result is None

    def test_query_with_year_boundary_40(self):
        """Should accept year 40 (minimum valid)"""
        result = extract_single_year("năm 40")
        assert result == 40

    def test_query_with_year_boundary_2025(self):
        """Should accept year 2025 (maximum valid)"""
        result = extract_single_year("năm 2025")
        assert result == 2025

    def test_query_with_year_boundary_2026(self):
        """Should reject year 2026 (just above threshold)"""
        result = extract_single_year("năm 2026")
        assert result is None


class TestEventsMissingRequiredFields:
    """Test handling of events with missing required fields"""

    def test_synthesize_with_events_missing_all_fields(self):
        """Should handle events missing all fields"""
        events = [
            {},  # Empty event
            {"id": 1},  # Only id
            {"year": None, "story": None},  # Null fields
        ]
        analysis = QueryAnalysis(
            intent="what",
            confidence=0.8,
            question_type="what",
            year=None,
        )
        result = synthesize_answer(analysis, events)
        # Should return None or empty, not crash
        assert result is None or result == ""

    def test_deduplicate_events_with_missing_year(self):
        """deduplicate_and_enrich should handle events without year"""
        from app.services.engine import deduplicate_and_enrich

        events = [
            {"story": "Event 1"},  # No year
            {"story": "Event 2", "year": None},  # Null year
            {"story": "Event 3", "year": 1945},  # Valid
        ]
        result = deduplicate_and_enrich(events, max_events=10)
        assert isinstance(result, list)
        # Should handle gracefully

    def test_format_complete_answer_with_mixed_years(self):
        """format_complete_answer should handle None/missing years"""
        from app.services.engine import format_complete_answer

        events = [
            {"story": "Event with year", "year": 1945},
            {"story": "Event without year"},
            {"story": "Event with null year", "year": None},
        ]
        result = format_complete_answer(events, group_by="year")
        assert isinstance(result, str) or result is None


class TestFAISSReturnsNoResults:
    """Test handling when FAISS returns empty results"""

    def test_semantic_search_no_results_threshold(self, monkeypatch):
        """Should handle when all FAISS scores below threshold"""
        import numpy as np
        from app.services.search_service import semantic_search

        class MockIndex:
            def search(self, query, k):
                # All scores below SIM_THRESHOLD
                scores = np.array([[0.01, 0.02, 0.03]])
                ids = np.array([[0, 1, 2]])
                return scores, ids

        monkeypatch.setattr(startup, "index", MockIndex())
        monkeypatch.setattr(startup, "session", object())
        monkeypatch.setattr(startup, "DOCUMENTS", [
            {"story": "Event 0", "year": 1945},
            {"story": "Event 1", "year": 1946},
            {"story": "Event 2", "year": 1947},
        ])

        result = semantic_search("unrelated query")
        # Should return empty or very few results
        assert isinstance(result, list)

    def test_engine_answer_with_no_faiss_results(self, monkeypatch):
        """engine_answer should handle when FAISS returns nothing"""
        import numpy as np

        class MockIndex:
            def search(self, query, k):
                # Empty results
                scores = np.array([[]])
                ids = np.array([[]])
                return scores, ids

        monkeypatch.setattr(startup, "index", MockIndex())
        monkeypatch.setattr(startup, "session", object())
        monkeypatch.setattr(startup, "DOCUMENTS", [])

        result = engine_answer("test query")
        assert isinstance(result, dict)
        assert result["no_data"] is True


class TestKnowledgeBaseEntityNotFound:
    """Test handling when entity not found in knowledge base"""

    def test_resolve_unknown_person(self):
        """Should handle query for person not in knowledge base"""
        result = resolve_query_entities("ai là random person xyz not in db")
        # Should return empty or handle gracefully
        assert isinstance(result, dict)

    def test_resolve_unknown_dynasty(self):
        """Should handle query for dynasty not in knowledge base"""
        result = resolve_query_entities("nhà random dynasty xyz")
        assert isinstance(result, dict)

    def test_resolve_unknown_place(self):
        """Should handle query for place not in knowledge base"""
        result = resolve_query_entities("địa điểm random place xyz")
        assert isinstance(result, dict)

    def test_scan_by_entities_with_unresolved_entities(self, monkeypatch):
        """scan_by_entities should handle entities not in inverted index"""
        monkeypatch.setattr(startup, "PERSONS_INDEX", {})  # Empty
        monkeypatch.setattr(startup, "DYNASTY_INDEX", {})
        monkeypatch.setattr(startup, "KEYWORD_INDEX", {})
        monkeypatch.setattr(startup, "PLACES_INDEX", {})
        monkeypatch.setattr(startup, "DOCUMENTS", [])

        resolved = {
            "persons": ["unknown person"],
            "dynasties": ["unknown dynasty"],
            "topics": ["unknown topic"],
            "places": ["unknown place"],
        }
        result = scan_by_entities(resolved)
        assert isinstance(result, list)


class TestEmptyDocumentStore:
    """Test handling when document store is empty"""

    def test_semantic_search_empty_documents(self, monkeypatch):
        """Should handle empty DOCUMENTS list"""
        import numpy as np

        class MockIndex:
            def search(self, query, k):
                scores = np.array([[0.9, 0.8]])
                ids = np.array([[0, 1]])
                return scores, ids

        monkeypatch.setattr(startup, "index", MockIndex())
        monkeypatch.setattr(startup, "session", object())
        monkeypatch.setattr(startup, "DOCUMENTS", [])  # Empty

        result = semantic_search("test query")
        # Indices 0, 1 don't exist in DOCUMENTS
        assert isinstance(result, list)
        assert len(result) == 0

    def test_engine_answer_empty_documents(self, monkeypatch):
        """engine_answer should handle empty document store"""
        monkeypatch.setattr(startup, "DOCUMENTS", [])
        monkeypatch.setattr(startup, "index", None)
        monkeypatch.setattr(startup, "session", None)

        result = engine_answer("test query")
        assert isinstance(result, dict)
        assert result["no_data"] is True

    def test_scan_by_entities_empty_documents(self, monkeypatch):
        """scan_by_entities should handle empty document store"""
        monkeypatch.setattr(startup, "PERSONS_INDEX", {"trần hưng đạo": [0, 1]})
        monkeypatch.setattr(startup, "DYNASTY_INDEX", {})
        monkeypatch.setattr(startup, "KEYWORD_INDEX", {})
        monkeypatch.setattr(startup, "PLACES_INDEX", {})
        monkeypatch.setattr(startup, "DOCUMENTS", [])  # Empty

        resolved = {"persons": ["trần hưng đạo"], "dynasties": [], "topics": [], "places": []}
        result = scan_by_entities(resolved)
        # Indices exist but documents don't
        assert isinstance(result, list)
        assert len(result) == 0


class TestVeryLongQueries:
    """Test handling of extremely long queries"""

    def test_query_with_1000_chars(self):
        """Should handle query with 1000 characters"""
        long_query = "năm 1945 " * 100  # 900 chars
        result = engine_answer(long_query)
        assert isinstance(result, dict)

    def test_query_with_10000_chars(self):
        """Should handle query with 10000 characters"""
        very_long_query = "kể về lịch sử việt nam " * 400  # ~9600 chars
        result = engine_answer(very_long_query)
        assert isinstance(result, dict)


class TestMalformedEventData:
    """Test handling of malformed event data structures"""

    def test_event_with_invalid_year_type(self):
        """Should handle event with non-integer year"""
        from app.services.engine import deduplicate_and_enrich

        events = [
            {"story": "Event 1", "year": "1945"},  # String year
            {"story": "Event 2", "year": 1945.5},  # Float year
            {"story": "Event 3", "year": [1945]},  # Array year
        ]
        result = deduplicate_and_enrich(events, max_events=10)
        # Should handle gracefully, convert or skip

    def test_event_with_non_string_story(self):
        """Should handle event with non-string story"""
        from app.services.engine import deduplicate_and_enrich

        events = [
            {"story": 12345, "year": 1945},  # Integer story
            {"story": ["list", "story"], "year": 1946},  # List story
            {"story": {"nested": "dict"}, "year": 1947},  # Dict story
        ]
        result = deduplicate_and_enrich(events, max_events=10)
        # Should handle gracefully


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
