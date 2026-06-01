"""
tests/test_retrievers.py — Unit tests for BaseRetriever implementations.

Tests BM25Retriever and SemanticRetriever with mock indexes and documents.
"""
import pytest
import sys
import os
from unittest.mock import MagicMock

# Add ai-service to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'ai-service'))

import app.core.startup as startup
from app.retrieval.semantic_retriever import SemanticRetriever
from app.retrieval.bm25_retriever import BM25Retriever


class TestSemanticRetriever:
    """Unit tests for SemanticRetriever"""

    def test_search_with_mock_index(self, monkeypatch):
        """Should retrieve and format documents from FAISS index correctly"""
        import numpy as np

        # 1. Setup mock documents
        mock_docs = [
            {"id": "doc1", "year": 938, "event": "Trận Bạch Đằng", "story": "Ngô Quyền đánh Nam Hán"},
            {"id": "doc2", "year": 1288, "event": "Trận Bạch Đằng", "story": "Trần Hưng Đạo đánh Nguyên Mông"},
        ]
        monkeypatch.setattr(startup, "DOCUMENTS", mock_docs)

        # 2. Mock FAISS index search
        class MockIndex:
            def search(self, query_vec, k):
                # Return scores and indices
                scores = np.array([[0.95, 0.85]])
                ids = np.array([[0, 1]])
                return scores, ids

        mock_index = MockIndex()

        # 3. Mock encoder to return a vector directly
        mock_encoder = MagicMock(return_value=np.array([0.1] * 384))

        # 4. Instantiate retriever
        retriever = SemanticRetriever(vector_index=mock_index, encoder=mock_encoder)

        # 5. Run search
        results = retriever.search("Bạch Đằng", top_k=2)

        # 6. Verify results
        assert len(results) == 2
        assert results[0]["id"] == "doc1"
        assert results[0]["score"] == 0.95
        assert results[0]["metadata"]["year"] == 938
        assert results[0]["metadata"]["event"] == "Trận Bạch Đằng"

        assert results[1]["id"] == "doc2"
        assert results[1]["score"] == 0.85

        # Verify encoder was called
        mock_encoder.encode.assert_called_once_with(["Bạch Đằng"])

    def test_search_empty_query(self):
        """Should return empty list for empty query"""
        retriever = SemanticRetriever(vector_index=None, encoder=None)
        assert retriever.search("") == []

    def test_search_negative_indices(self, monkeypatch):
        """Should filter out negative/invalid indices returned by FAISS"""
        import numpy as np

        mock_docs = [
            {"id": "doc1", "year": 938, "event": "Trận Bạch Đằng"},
        ]
        monkeypatch.setattr(startup, "DOCUMENTS", mock_docs)

        class MockIndex:
            def search(self, query_vec, k):
                # Returns out-of-bounds and negative indices
                scores = np.array([[0.95, 0.5, 0.4]])
                ids = np.array([[0, -1, 100]])
                return scores, ids

        mock_index = MockIndex()
        mock_encoder = MagicMock(return_value=np.array([0.1] * 384))

        retriever = SemanticRetriever(vector_index=mock_index, encoder=mock_encoder)
        results = retriever.search("Bạch Đằng", top_k=3)

        # Only index 0 is valid and should be kept
        assert len(results) == 1
        assert results[0]["id"] == "doc1"
