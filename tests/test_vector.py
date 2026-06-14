import pytest
import numpy as np
import sys
from unittest.mock import patch, MagicMock

class DummyEmbedder:
    def encode(self, texts, show_progress_bar=False):
        # Return dummy embeddings of dimension 4
        return np.array([[0.1, 0.2, 0.3, 0.4] for _ in texts], dtype=np.float32)

def test_build_index_empty():
    from app.services.vector import build_index
    assert build_index([], None) is None

@patch.dict(sys.modules, {'faiss': MagicMock()})
def test_build_index_success():
    import faiss
    faiss_mock = MagicMock()
    faiss_mock.ntotal = 2
    faiss_mock.d = 4
    faiss.IndexFlatL2.return_value = faiss_mock

    from app.services.vector import build_index
    docs = [{"event": "Test event 1"}, {"event": "Test event 2"}]
    embedder = DummyEmbedder()

    index = build_index(docs, embedder)

    assert index is not None
    assert index.ntotal == 2
    assert index.d == 4

    # Verify mock was called correctly
    faiss.IndexFlatL2.assert_called_once_with(4)
    faiss_mock.add.assert_called_once()
