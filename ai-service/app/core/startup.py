import json
import faiss
import os
from sentence_transformers import SentenceTransformer
from app.core.config import *
from collections import defaultdict
from unittest.mock import MagicMock

print("[STARTUP] Loading embedding model & FAISS...")

embedder = SentenceTransformer(EMBED_MODEL)

# Load FAISS index with fallback for testing/missing files
try:
    if os.path.exists(INDEX_PATH):
        index = faiss.read_index(INDEX_PATH)
    else:
        print(f"[WARNING] FAISS index not found at {INDEX_PATH}. Using mock index.")
        index = MagicMock()
except Exception as e:
    print(f"[WARNING] Failed to load FAISS index: {e}. Using mock index.")
    index = MagicMock()

# Load metadata with fallback
try:
    if os.path.exists(META_PATH):
        with open(META_PATH, encoding="utf-8") as f:
            META_RAW = json.load(f)
    else:
        print(f"[WARNING] Metadata not found at {META_PATH}. Using empty documents.")
        META_RAW = {"documents": []}
except Exception as e:
    print(f"[WARNING] Failed to load metadata: {e}. Using empty documents.")
    META_RAW = {"documents": []}

DOCUMENTS = META_RAW.get("documents", [])

# Pre-calculate Year Index for O(1) lookups
DOCUMENTS_BY_YEAR = defaultdict(list)
for doc in DOCUMENTS:
    y = doc.get("year")
    if y is not None:
        DOCUMENTS_BY_YEAR[y].append(doc)
