"""
semantic_retriever.py — FAISS-based vector similarity retriever.

Wraps the existing FAISS index to conform to BaseRetriever interface.
Returns top-k results by cosine/L2 similarity.
"""

from typing import Any, Dict, List

from app.retrieval.base_retriever import BaseRetriever


class SemanticRetriever(BaseRetriever):
    """
    Vector similarity retriever using FAISS index.

    Wraps the project's existing FAISS infrastructure
    (faiss_index/index.bin + meta.json) into the BaseRetriever interface.
    """

    def __init__(self, vector_index, encoder=None):
        """
        Args:
            vector_index: FAISS index object (faiss.IndexFlatIP or similar).
            encoder:      Sentence encoder for query embedding.
                          If None, caller must pre-encode queries.
        """
        self.vector_index = vector_index
        self.encoder = encoder

    def search(self, query: str, top_k: int = 50) -> List[Dict[str, Any]]:
        """
        Encode query → search FAISS → return standardized results.

        Integration note:
            Currently the project uses `semantic_search()` in search_service.py.
            This class provides an alternative interface for hybrid fusion.
        """
        import numpy as np
        import app.core.startup as startup
        from app.services.search_service import get_cached_embedding

        if not query:
            return []

        # 1. Encode query
        if self.encoder is not None:
            if hasattr(self.encoder, "encode"):
                query_vec = self.encoder.encode([query])
            elif callable(self.encoder):
                query_vec = self.encoder(query)
            else:
                query_vec = get_cached_embedding(query)
        else:
            query_vec = get_cached_embedding(query)

        # Ensure query_vec is a 2D numpy array for FAISS
        if isinstance(query_vec, list):
            query_vec = np.array(query_vec)
        if len(query_vec.shape) == 1:
            query_vec = np.expand_dims(query_vec, axis=0)

        # 2. Search FAISS index
        vector_index = self.vector_index if self.vector_index is not None else startup.index
        if vector_index is None:
            print("[WARN] SemanticRetriever: FAISS index is not initialized")
            return []

        scores, ids = vector_index.search(query_vec, top_k)

        # 3. Format results
        results = []
        for dist, idx in zip(scores[0], ids[0]):
            # Reject negative or out-of-bounds indices
            if idx < 0 or idx >= len(startup.DOCUMENTS):
                continue

            doc = startup.DOCUMENTS[idx]
            results.append({
                "id": str(doc.get("id", idx)),
                "score": float(dist),
                "metadata": {
                    "year": doc.get("year"),
                    "event": doc.get("event", ""),
                    "story": doc.get("story", ""),
                    "dynasty": doc.get("dynasty", ""),
                    "persons": doc.get("persons", []),
                    "places": doc.get("places", []),
                    "event_type": doc.get("event_type", ""),
                }
            })

        return results

