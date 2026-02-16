"""
base_retriever.py — Abstract base class for all retrievers.

All retrievers (Semantic, BM25, Hybrid) implement this interface.
Ensures uniform output format across retrieval strategies.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class BaseRetriever(ABC):
    """Abstract retriever with uniform search interface."""

    @abstractmethod
    def search(self, query: str, top_k: int = 50) -> List[Dict[str, Any]]:
        """
        Search for documents matching the query.

        Args:
            query: User query string.
            top_k: Maximum number of results to return.

        Returns:
            List of result dicts, each containing:
                - "id":       str   — unique document identifier
                - "score":    float — relevance score (higher = better)
                - "metadata": dict  — document metadata (year, event, persons, etc.)
        """
        pass
