import faiss
import numpy as np

def build_index(documents, embedder):
    """
    Build FAISS index from documents.
    Args:
        documents: List of document dicts
        embedder: SentenceTransformer instance
    """
    if not documents:
        return None

    print(f"[VECTOR_DB] Building index for {len(documents)} documents...")
    
    # 1. Extract text to embed
    texts = [doc.get("event", "") for doc in documents]
    
    # 2. Generate embeddings
    embeddings = embedder.encode(texts, show_progress_bar=True)
    
    # 3. Create FAISS index
    d = embeddings.shape[1]
    index = faiss.IndexFlatL2(d)
    index.add(embeddings.astype(np.float32))
    
    print(f"[VECTOR_DB] Index built with {index.ntotal} vectors.")
    return index
