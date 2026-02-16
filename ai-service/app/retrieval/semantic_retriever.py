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
        # TODO: integrate with existing FAISS search infrastructure
        # Pseudocode:
        #
        # if self.encoder:
        #     query_vec = self.encoder.encode([query])
        # distances, indices = self.vector_index.search(query_vec, top_k)
        #
        # results = []
        # for rank, (dist, idx) in enumerate(zip(distances[0], indices[0])):
        #     if idx == -1:
        #         continue
        #     doc = DOCUMENTS[idx]
        #     results.append({
        #         "id": str(idx),
        #         "score": float(dist),
        #         "metadata": {
        #             "year": doc.get("year"),
        #             "event": doc.get("event"),
        #             "persons": doc.get("persons", []),
        #             "dynasty": doc.get("dynasty"),
        #         }
        #     })
        # return results

        raise NotImplementedError(
            "SemanticRetriever.search() is a skeleton — "
            "integrate with existing FAISS infrastructure to activate."
        )
