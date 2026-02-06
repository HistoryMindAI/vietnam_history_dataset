import json
import faiss
import os
from sentence_transformers import SentenceTransformer
from app.core.config import *
from collections import defaultdict

print("[STARTUP] Loading embedding model & FAISS...")

embedder = SentenceTransformer(EMBED_MODEL)

# Load FAISS index
if os.path.exists(INDEX_PATH):
    try:
        index = faiss.read_index(INDEX_PATH)
    except Exception as e:
        print(f"[ERROR] Failed to read FAISS index: {e}")
        index = None
else:
    print(f"[ERROR] FAISS index not found at {INDEX_PATH}.")
    index = None

# Fallback for index if it failed to load or is missing (mostly for tests)
if index is None:
    try:
        # Try to get dimension from embedder
        d = embedder.get_sentence_embedding_dimension()
        # If embedder is a mock, d will be a mock. IndexFlatL2 needs an int.
        if not isinstance(d, int):
            d = 384 # Default dimension for paraphrase-multilingual-MiniLM-L12-v2
        index = faiss.IndexFlatL2(d)
    except:
        index = faiss.IndexFlatL2(384)

# Load metadata
if os.path.exists(META_PATH):
    try:
        with open(META_PATH, encoding="utf-8") as f:
            META_RAW = json.load(f)
    except Exception as e:
        print(f"[ERROR] Failed to read metadata: {e}")
        META_RAW = {"documents": []}
else:
    print(f"[ERROR] Metadata not found at {META_PATH}.")
    META_RAW = {"documents": []}

DOCUMENTS = META_RAW.get("documents", [])

# Pre-calculate Year Index for O(1) lookups
DOCUMENTS_BY_YEAR = defaultdict(list)
for doc in DOCUMENTS:
    y = doc.get("year")
    if y is not None:
        DOCUMENTS_BY_YEAR[y].append(doc)
