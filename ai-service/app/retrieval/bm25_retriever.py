"""
bm25_retriever.py — BM25 Sparse Retriever (Production Implementation).

Uses rank-bm25 library (BM25Okapi) for keyword-based document retrieval.
Designed for Vietnamese historical text with appropriate tokenization.

Key features:
  ✅ BM25Okapi with tuned k1/b parameters
  ✅ Vietnamese-aware tokenization (preserves diacritics)
  ✅ Indexes event + story + persons fields
  ✅ get_scores() for full scoring
  ✅ Lazy index building (build on first search)
  ✅ Fail-safe for missing rank-bm25 dependency

Context7 Reference (rank-bm25):
    from rank_bm25 import BM25Okapi
    tokenized_corpus = [doc.split(" ") for doc in corpus]
    bm25 = BM25Okapi(tokenized_corpus, k1=1.5, b=0.75)
    scores = bm25.get_scores(tokenized_query)

Architecture:
    DOCUMENTS → tokenize → BM25Okapi index
    Query → tokenize → get_scores() → top_k results
"""

import re
from typing import Any, Dict, List, Optional

from app.retrieval.base_retriever import BaseRetriever


# ======================================================================
# VIETNAMESE TOKENIZATION
# ======================================================================

# Vietnamese stopwords (minimal — keep historical terms)
_VIET_STOPWORDS = {
    "là", "và", "của", "có", "được", "trong", "với", "để",
    "các", "một", "này", "đã", "cho", "từ", "theo", "về",
    "khi", "của", "bị", "ra", "lên", "vào", "hay", "rằng",
    "thì", "mà", "sẽ", "tại", "do", "nên", "vì", "nếu",
    "the", "a", "an", "is", "are", "was", "were", "in", "on",
    "at", "to", "for", "of", "with", "by",
}

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)


def tokenize_vietnamese(text: str) -> List[str]:
    """
    Tokenize Vietnamese text for BM25 indexing.

    Preserves diacritics (important for Vietnamese).
    Removes punctuation but keeps word boundaries.
    Filters stopwords.

    Args:
        text: Raw text string.

    Returns:
        List of lowercase tokens.
    """
    if not text or not isinstance(text, str):
        return []
    text = text.lower()
    text = _PUNCT_RE.sub(" ", text)
    tokens = text.split()
    return [t for t in tokens if t and t not in _VIET_STOPWORDS]


def build_doc_text(doc: Dict[str, Any]) -> str:
    """
    Build searchable text from document fields.

    Indexes: event + story + persons (joined).
    Weights event field higher by repeating it.
    """
    parts = []

    event = doc.get("event", "")
    if event:
        # Event field gets 2× weight (repeated)
        parts.append(str(event))
        parts.append(str(event))

    story = doc.get("story", "")
    if story:
        parts.append(str(story))

    persons = doc.get("persons", [])
    if isinstance(persons, list):
        parts.append(" ".join(str(p) for p in persons))

    dynasty = doc.get("dynasty", "")
    if dynasty:
        parts.append(str(dynasty))

    return " ".join(parts)


# ======================================================================
# BM25 RETRIEVER
# ======================================================================

class BM25Retriever(BaseRetriever):
    """
    BM25Okapi-based sparse retriever for Vietnamese historical text.

    Lazy initialization: index is built on first search call.
    Requires rank-bm25 package: pip install rank-bm25

    Usage:
        retriever = BM25Retriever(documents=startup.DOCUMENTS)
        results = retriever.search("Hiệp định Genève 1954", top_k=20)

    Args:
        documents: List of document dicts from startup.DOCUMENTS.
        k1:        Term frequency saturation (default=1.5).
        b:         Length normalization (default=0.75).
    """

    def __init__(
        self,
        documents: Optional[List[Dict[str, Any]]] = None,
        k1: float = 1.5,
        b: float = 0.75,
    ):
        self._documents = documents or []
        self._k1 = k1
        self._b = b
        self._bm25 = None
        self._tokenized_corpus: List[List[str]] = []
        self._doc_ids: List[str] = []
        self._built = False

    # ==================================================================
    # INDEX BUILDING
    # ==================================================================

    def build_index(self, documents: Optional[List[Dict[str, Any]]] = None):
        """
        Build BM25 index from documents.

        Can be called explicitly at startup, or lazily on first search.

        Args:
            documents: Optional new documents to index.
                       If None, uses documents from constructor.
        """
        if documents is not None:
            self._documents = documents

        if not self._documents:
            print("[WARN] BM25Retriever: No documents to index")
            self._built = True
            return

        try:
            from rank_bm25 import BM25Okapi
        except ImportError:
            print(
                "[WARN] rank-bm25 not installed. "
                "BM25Retriever will return empty results. "
                "Install with: pip install rank-bm25"
            )
            self._built = True
            return

        # Build tokenized corpus and ID mapping
        self._tokenized_corpus = []
        self._doc_ids = []

        for i, doc in enumerate(self._documents):
            text = build_doc_text(doc)
            tokens = tokenize_vietnamese(text)
            self._tokenized_corpus.append(tokens)
            # Use index as ID if no explicit ID field
            doc_id = str(doc.get("id", i))
            self._doc_ids.append(doc_id)

        # Build BM25 index
        self._bm25 = BM25Okapi(
            self._tokenized_corpus,
            k1=self._k1,
            b=self._b,
        )
        self._built = True

        print(
            f"[BM25] Index built: {len(self._documents)} documents, "
            f"k1={self._k1}, b={self._b}"
        )

    # ==================================================================
    # SEARCH
    # ==================================================================

    def search(self, query: str, top_k: int = 50) -> List[Dict[str, Any]]:
        """
        Search documents using BM25 scoring.

        Lazy-builds index on first call if not already built.

        Args:
            query: User query string.
            top_k: Maximum results to return.

        Returns:
            List of result dicts:
              - "id":       Document ID
              - "score":    BM25 relevance score
              - "metadata": Document metadata
        """
        # Lazy build
        if not self._built:
            self.build_index()

        if self._bm25 is None:
            return []

        # Tokenize query
        query_tokens = tokenize_vietnamese(query)
        if not query_tokens:
            return []

        # Get scores for all documents
        scores = self._bm25.get_scores(query_tokens)

        # Build (score, index) pairs and sort by score descending
        scored_indices = sorted(
            enumerate(scores),
            key=lambda x: x[1],
            reverse=True,
        )

        # Take top_k with score > 0
        results = []
        for idx, score in scored_indices[:top_k]:
            if score <= 0:
                break

            doc = self._documents[idx]
            results.append({
                "id": self._doc_ids[idx],
                "score": float(score),
                "metadata": {
                    "year": doc.get("year"),
                    "event": doc.get("event", ""),
                    "story": doc.get("story", ""),
                    "dynasty": doc.get("dynasty", ""),
                    "persons": doc.get("persons", []),
                    "places": doc.get("places", []),
                    "event_type": doc.get("event_type", ""),
                },
            })

        return results

    # ==================================================================
    # UTILITIES
    # ==================================================================

    @property
    def is_ready(self) -> bool:
        """Check if index is built and ready for search."""
        return self._built and self._bm25 is not None

    @property
    def corpus_size(self) -> int:
        """Number of documents in the index."""
        return len(self._documents)
