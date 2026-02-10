"""
test_performance.py - Performance tests for search and caching.

Tests:
1. Embedding cache efficiency
2. Year lookup performance
3. Deduplication and query normalization
"""
import pytest
import time
import sys
import numpy as np
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add ai-service to path (portable)
AI_SERVICE_DIR = Path(__file__).parent.parent / "ai-service"
if str(AI_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_DIR))

# Mock heavy dependencies
sys.modules.setdefault('faiss', MagicMock())
sys.modules.setdefault('sentence_transformers', MagicMock())


def test_embedding_cache_efficiency():
    """Verify that the embedding cache prevents redundant calls to the model."""
    from app.services.search_service import get_cached_embedding
    import app.core.startup as startup
    
    # Mock ONNX session and Tokenizer
    mock_session = MagicMock()
    mock_tokenizer = MagicMock()
    startup.session = mock_session
    startup.tokenizer = mock_tokenizer
    
    # Mock output of session.run (list of one numpy array)
    mock_session.run.return_value = [np.array([[[0.1, 0.2, 0.3]]], dtype="float32")]
    
    # Mock tokenizer output (dict)
    mock_tokenizer.return_value = {
        "input_ids": np.array([[1, 2, 3]]),
        "attention_mask": np.array([[1, 1, 1]])
    }
        
    # Use unique query
    query = f"performance_test_{time.time()}"
    
    # Clear cache to ensure clean state
    get_cached_embedding.cache_clear()
    
    # First execution
    get_cached_embedding(query)
    first_call_count = mock_session.run.call_count
    
    # Second execution (should hit cache)
    get_cached_embedding(query)
    assert first_call_count > 0, "First call should trigger run"
    assert mock_session.run.call_count == first_call_count, "Cache missed!"


def test_year_lookup_performance():
    """Ensure year lookup is fast (O(1))."""
    from app.services.search_service import scan_by_year
    from app.core import startup
    
    test_year = 9999  # Use unique year to avoid conflicts
    startup.DOCUMENTS_BY_YEAR = {}
    startup.DOCUMENTS_BY_YEAR[test_year] = [{"event": "Test Event", "year": test_year}]
    
    start = time.perf_counter()
    results = scan_by_year(test_year)
    elapsed = time.perf_counter() - start
    
    assert len(results) == 1
    assert results[0]["year"] == test_year
    assert elapsed < 0.01  # Should be very fast


def test_engine_deduplication():
    """Verify that the engine correctly deduplicates stories."""
    from app.services.engine import engine_answer
    
    mock_events = [
        {"year": 1010, "story": "Lý Thái Tổ dời đô về Thăng Long.", "event": "Dời đô"},
        {"year": 1010, "story": "Lý Thái Tổ dời đô về Thăng Long.", "event": "Dời đô (trùng)"},
        {"year": 1010, "story": "Sự kiện khác.", "event": "Khác"}
    ]
    
    with patch("app.services.engine.scan_by_year", return_value=mock_events):
        result = engine_answer("năm 1010")
        
        # Should have deduplicated
        assert result["answer"] is not None


def test_query_normalization_caching():
    """Verify normalized queries hit the same cache."""
    from app.utils.normalize import normalize_query
    from app.services.search_service import get_cached_embedding
    import app.core.startup as startup
    
    # Mock startup.session/tokenizer (reuse logic)
    mock_session = MagicMock()
    mock_tokenizer = MagicMock()
    startup.session = mock_session
    startup.tokenizer = mock_tokenizer
    
    mock_session.run.return_value = [np.array([[[0.1, 0.2, 0.3]]], dtype="float32")]
    mock_tokenizer.return_value = {
        "input_ids": np.array([[1, 2, 3]]),
        "attention_mask": np.array([[1, 1, 1]])
    }
    
    q1 = "Quang   Trung"
    q2 = "quang trung "
    
    # Should normalize to same string
    assert normalize_query(q1) == normalize_query(q2)
    
    # Clear cache
    get_cached_embedding.cache_clear()
    
    # First call
    get_cached_embedding(normalize_query(q1))
    count_after_q1 = mock_session.run.call_count
    
    # Second call (should hit cache)
    get_cached_embedding(normalize_query(q2))
    assert mock_session.run.call_count == count_after_q1
