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
            To integrate, replace direct FAISS calls with this retriever.
        """
        import app.core.startup as startup
        import numpy as np

        if self.encoder:
            query_vec = self.encoder.encode([query])
            emb_2d = np.expand_dims(query_vec[0], axis=0).astype("float32")
        else:
            # Assuming caller provided string, but wait, if no encoder, we can't embed.
            # So encoder is required.
            if not isinstance(query, str):
                emb_2d = np.expand_dims(query, axis=0).astype("float32")
            else:
                raise ValueError("Encoder is required to embed string query")

        distances, indices = self.vector_index.search(emb_2d, top_k)

        results = []
        for rank, (dist, idx) in enumerate(zip(distances[0], indices[0])):
            if idx == -1:
                continue
            doc = startup.DOCUMENTS[idx]
            results.append({
                "id": str(idx),
                "score": float(dist),
                "metadata": {
                    "year": doc.get("year"),
                    "event": doc.get("event"),
                    "persons": doc.get("persons", []),
                    "dynasty": doc.get("dynasty"),
                }
            })
        return results
