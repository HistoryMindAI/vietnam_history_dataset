"""
test_bug_fixes.py — Critical Bug Tests

Tests for the 7 bugs identified in bug analysis report:
- Bug #1: Empty string capitalization crash
- Bug #2: Empty list max() crash
- Bug #4: Null/undefined in _format_event_text()
- Bug #5: Negative FAISS indices

Priority: CRITICAL crashes
"""
import pytest
import sys
import os

# Add ai-service to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'ai-service'))

from app.services.engine import (
    clean_story_text,
    _format_event_text,
    deduplicate_and_enrich,
)
from app.services.answer_synthesis import (
    _handle_data_scope,
    _build_when_answer,
)
import app.core.startup as startup


class TestBug1EmptyStringCapitalization:
    """
    Bug #1: Empty string capitalization crash in _format_event_text()

    Location: engine.py line 510
    Issue: clean_story[0].upper() when clean_story is empty string
    Root cause: clean_story_text() can return empty string
    """

    def test_format_event_with_empty_story(self):
        """Should handle event with empty story gracefully"""
        event = {"story": "", "event": "", "year": 1945}
        result = _format_event_text(event, year=1945, seen_texts=set())
        assert result is None  # Should return None, not crash

    def test_format_event_with_whitespace_only_story(self):
        """Should handle event with whitespace-only story"""
        event = {"story": "   ", "event": "\n\t", "year": 1945}
        result = _format_event_text(event, year=1945, seen_texts=set())
        assert result is None

    def test_format_event_with_only_metadata(self):
        """Should handle event that becomes empty after cleaning metadata"""
        # Story that's only metadata prefixes
        event = {
            "story": "Năm 1945, gắn mốc 1945 với",
            "event": "",
            "year": 1945
        }
        result = _format_event_text(event, year=1945, seen_texts=set())
        # Should either return None or handle gracefully without crash
        assert result is None or isinstance(result, str)

    def test_clean_story_text_empty_input(self):
        """clean_story_text should handle empty input"""
        assert clean_story_text("") == ""
        assert clean_story_text(None) == ""
        assert clean_story_text("   ") == ""


class TestBug2EmptyListMax:
    """
    Bug #2: Empty list max() crash in answer_synthesis.py

    Location: answer_synthesis.py line 71
    Issue: min(years) when years = []
    Root cause: Filtering can result in empty years list
    """

    def test_handle_data_scope_with_empty_documents(self, monkeypatch):
        """Should handle empty DOCUMENTS list"""
        monkeypatch.setattr(startup, "DOCUMENTS", [])
        result = _handle_data_scope()
        assert isinstance(result, str)
        assert "năm 40" in result.lower()  # Should have fallback message

    def test_handle_data_scope_with_no_year_field(self, monkeypatch):
        """Should handle documents without year field"""
        monkeypatch.setattr(startup, "DOCUMENTS", [
            {"story": "Event 1", "event": "Test"},
            {"story": "Event 2", "event": "Test", "year": None},
        ])
        result = _handle_data_scope()
        assert isinstance(result, str)
        # Should not crash, should provide graceful fallback

    def test_build_when_answer_with_events_missing_year(self):
        """_build_when_answer should handle events without year"""
        from app.services.answer_synthesis import _build_when_answer
        from app.services.intent_classifier import QueryAnalysis

        events = [
            {"story": "Event happened", "event": "Test event"},  # No year
            {"story": "Another event", "year": None},  # Null year
        ]
        analysis = QueryAnalysis(
            intent="when",
            confidence=0.9,
            question_type="when",
            year=None,
        )

        result = _build_when_answer(events, analysis)
        # Should not crash, should handle gracefully
        assert result is None or isinstance(result, str)


class TestBug4NullUndefinedInFormatEvent:
    """
    Bug #4: Null/undefined handling in _format_event_text()

    Location: engine.py line 494-510
    Issue: e.get("story", "") or e.get("event", "") when both are None
    Root cause: "None or None" = None, not ""
    """

    def test_format_event_with_null_story_and_event(self):
        """Should handle event with null story and event fields"""
        event = {"story": None, "event": None, "year": 1945}
        result = _format_event_text(event, year=1945, seen_texts=set())
        assert result is None  # Should return None gracefully

    def test_format_event_with_missing_fields(self):
        """Should handle event with missing story/event fields"""
        event = {"year": 1945}  # No story or event field
        result = _format_event_text(event, year=1945, seen_texts=set())
        assert result is None

    def test_format_event_with_null_title(self):
        """Should handle event with null title field"""
        event = {
            "story": "Valid story text",
            "event": "",
            "title": None,
            "year": 1945
        }
        result = _format_event_text(event, year=1945, seen_texts=set())
        assert isinstance(result, str)
        assert "valid story" in result.lower()

    def test_deduplicate_with_null_story_fields(self):
        """deduplicate_and_enrich should filter out events with null story"""
        raw_events = [
            {"story": None, "event": None, "year": 1945},
            {"story": "Đây là một sự kiện lịch sử quan trọng", "event": "", "year": 1945},
            {"story": "", "event": "Một sự kiện khác cũng rất đáng nhớ", "year": 1946},
        ]
        result = deduplicate_and_enrich(raw_events, max_events=10)
        # Should only keep events with valid content (longer than MIN_CLEAN_TEXT_LENGTH)
        assert len(result) == 2
        assert all(e.get("story") or e.get("event") for e in result)


class TestBug5NegativeFAISSIndices:
    """
    Bug #5: Negative FAISS indices crash

    Location: search_service.py line 518-530
    Issue: FAISS can return -1 for invalid indices
    Root cause: ids array not validated before indexing DOCUMENTS
    """

    def test_semantic_search_with_negative_indices(self, monkeypatch):
        """Should filter out negative FAISS indices"""
        import numpy as np
        from app.services.search_service import semantic_search

        # Mock FAISS index to return negative indices
        class MockIndex:
            def search(self, query, k):
                # Simulate FAISS returning some negative indices
                scores = np.array([[0.9, 0.8, -1.0, 0.7, -1.0]])
                ids = np.array([[0, 1, -1, 3, -1]])  # Some invalid indices
                return scores, ids

        # Mock startup objects
        monkeypatch.setattr(startup, "index", MockIndex())
        monkeypatch.setattr(startup, "session", object())  # Non-None
        monkeypatch.setattr(startup, "DOCUMENTS", [
            {"story": "Event 0", "year": 1945},
            {"story": "Event 1", "year": 1946},
            {"story": "Event 2", "year": 1947},
            {"story": "Event 3", "year": 1948},
        ])

        # Should not crash with negative indices
        result = semantic_search("test query")

        # Should only return valid documents
        assert isinstance(result, list)
        # Should have filtered out the -1 indices
        assert len(result) <= 3  # Only valid indices 0, 1, 3

    def test_semantic_search_with_out_of_bounds_indices(self, monkeypatch):
        """Should filter out indices >= len(DOCUMENTS)"""
        import numpy as np
        from app.services.search_service import semantic_search

        class MockIndex:
            def search(self, query, k):
                # Return some indices beyond DOCUMENTS length
                scores = np.array([[0.9, 0.8, 0.7]])
                ids = np.array([[0, 100, 200]])  # 100, 200 are out of bounds
                return scores, ids

        monkeypatch.setattr(startup, "index", MockIndex())
        monkeypatch.setattr(startup, "session", object())
        monkeypatch.setattr(startup, "DOCUMENTS", [
            {"story": "Event 0", "year": 1945},
        ])

        result = semantic_search("test query")

        # Should only return doc at index 0
        assert len(result) <= 1

    def test_scan_by_entities_with_negative_indices(self, monkeypatch):
        """scan_by_entities should validate indices from inverted index"""
        from app.services.search_service import scan_by_entities

        # Mock inverted index with negative/invalid indices
        monkeypatch.setattr(startup, "PERSONS_INDEX", {
            "nguyễn huệ": [0, -1, 100, 1]  # Mix of valid and invalid
        })
        monkeypatch.setattr(startup, "DYNASTY_INDEX", {})
        monkeypatch.setattr(startup, "KEYWORD_INDEX", {})
        monkeypatch.setattr(startup, "PLACES_INDEX", {})
        monkeypatch.setattr(startup, "DOCUMENTS", [
            {"story": "Event 0", "year": 1789, "persons": ["nguyễn huệ"]},
            {"story": "Event 1", "year": 1790, "persons": ["nguyễn huệ"]},
        ])

        resolved = {"persons": ["nguyễn huệ"], "dynasties": [], "topics": [], "places": []}
        result = scan_by_entities(resolved, max_results=50)

        # Should only return valid documents
        assert len(result) == 2
        assert all(isinstance(doc, dict) for doc in result)


class TestBug5AdditionalEdgeCases:
    """Additional edge cases for FAISS/indexing bugs"""

    def test_empty_embedding_query(self, monkeypatch):
        """Should handle empty query that produces empty embedding"""
        from app.services.search_service import semantic_search

        monkeypatch.setattr(startup, "index", None)  # Not initialized
        monkeypatch.setattr(startup, "session", None)

        result = semantic_search("")
        assert result == []  # Should return empty list, not crash

    def test_semantic_search_with_all_negative_scores(self, monkeypatch):
        """Should handle FAISS returning all negative similarity scores"""
        import numpy as np
        from app.services.search_service import semantic_search

        class MockIndex:
            def search(self, query, k):
                # All scores below threshold
                scores = np.array([[-0.5, -0.6, -0.7]])
                ids = np.array([[0, 1, 2]])
                return scores, ids

        monkeypatch.setattr(startup, "index", MockIndex())
        monkeypatch.setattr(startup, "session", object())
        monkeypatch.setattr(startup, "DOCUMENTS", [
            {"story": "Event 0", "year": 1945},
            {"story": "Event 1", "year": 1946},
            {"story": "Event 2", "year": 1947},
        ])

        result = semantic_search("irrelevant query")
        # Should return empty or minimal results
        assert isinstance(result, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
