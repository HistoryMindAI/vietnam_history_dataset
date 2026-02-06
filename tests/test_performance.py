import pytest
import time
from unittest.mock import MagicMock, patch
import sys
import os
import numpy as np

# Add ai-service to path
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(base_dir, "ai-service"))

from app.services.search_service import get_cached_embedding, scan_by_year
from app.services.engine import engine_answer
from app.core.startup import DOCUMENTS_BY_YEAR

def test_embedding_cache_efficiency():
    """
    Verify that the embedding cache prevents redundant calls to the model.
    """
    with patch("app.services.search_service.embedder") as mock_embedder:
        # Mock return value for encode
        mock_embedder.encode.return_value = np.array([[0.1, 0.2, 0.3]], dtype="float32")

        # Clear cache before test if possible, or just use a unique string
        query = f"performance_test_{time.time()}"

        # First execution
        get_cached_embedding(query)
        first_call_count = mock_embedder.encode.call_count

        # Second execution (should hit cache)
        get_cached_embedding(query)
        assert mock_embedder.encode.call_count == first_call_count, "Cache missed on identical query!"

def test_year_lookup_performance():
    """
    Ensure year lookup uses the indexed DOCUMENTS_BY_YEAR.
    """
    test_year = 1234
    DOCUMENTS_BY_YEAR[test_year] = [{"event": "Test Event", "year": test_year}]

    start_time = time.perf_counter()
    results = scan_by_year(test_year)
    end_time = time.perf_counter()

    assert len(results) == 1
    assert results[0]["year"] == test_year
    # In a real environment, this should be extremely fast (O(1))
    assert (end_time - start_time) < 0.01

def test_engine_deduplication():
    """
    Verify that the engine correctly deduplicates stories.
    """
    mock_events = [
        {"year": 1010, "story": "Lý Thái Tổ dời đô về Thăng Long.", "event": "Dời đô"},
        {"year": 1010, "story": "Lý Thái Tổ dời đô về Thăng Long.", "event": "Dời đô (trùng)"},
        {"year": 1010, "story": "Sự kiện khác.", "event": "Khác"}
    ]

    with patch("app.services.engine.scan_by_year", return_value=mock_events):
        result = engine_answer("năm 1010")

        # Should have 2 unique stories joined by \n
        stories = result["answer"].split("\n")
        assert len(stories) == 2
        assert "Lý Thái Tổ dời đô về Thăng Long." in stories
        assert "Sự kiện khác." in stories

def test_query_normalization_caching():
    """
    Verify that different queries that normalize to the same string hit the same cache.
    """
    with patch("app.services.search_service.embedder") as mock_embedder, \
         patch("app.services.search_service.index") as mock_index:

        mock_embedder.encode.return_value = np.array([[0.1, 0.2, 0.3]], dtype="float32")
        mock_index.search.return_value = (np.array([[0.9]]), np.array([[0]]))

        q1 = "Quang   Trung"
        q2 = "quang trung "

        # These should normalize to the same string "quang trung"
        from app.utils.normalize import normalize_query
        assert normalize_query(q1) == normalize_query(q2)

        # Use semantic_search which calls normalize_query + get_cached_embedding
        from app.services.search_service import semantic_search

        # Clear cache for "quang trung" to ensure fresh state
        get_cached_embedding.cache_clear()

        # First call
        semantic_search(q1)
        count_after_q1 = mock_embedder.encode.call_count

        # Second call with different casing/spacing
        semantic_search(q2)
        assert mock_embedder.encode.call_count == count_after_q1, "Cache missed despite same normalized query!"
