import os
import json
import faiss
from collections import defaultdict
from sentence_transformers import SentenceTransformer

from .config import (
    EMBED_MODEL,
    INDEX_PATH,
    META_PATH,
)

print("[STARTUP] Loading embedding model & FAISS...")

# ===============================
# LOAD EMBEDDING MODEL
# ===============================
try:
    embedder = SentenceTransformer(EMBED_MODEL)
    print(f"[STARTUP] Loaded embedding model: {EMBED_MODEL}")
except Exception as e:
    print(f"[FATAL] Failed to load embedding model: {e}")
    raise e

# ===============================
# LOAD FAISS INDEX
# ===============================
index = None

if os.path.exists(INDEX_PATH):
    try:
        index = faiss.read_index(INDEX_PATH)
        print(f"[STARTUP] FAISS index loaded from {INDEX_PATH}")
    except Exception as e:
        print(f"[ERROR] Failed to read FAISS index: {e}")
else:
    print(f"[WARN] FAISS index not found at {INDEX_PATH}")

# ===============================
# FALLBACK INDEX (ANTI-CRASH)
# ===============================
if index is None:
    try:
        d = embedder.get_sentence_embedding_dimension()
        if not isinstance(d, int):
            d = 384
        index = faiss.IndexFlatL2(d)
        print(f"[STARTUP] Fallback FAISS index created (dim={d})")
    except Exception:
        index = faiss.IndexFlatL2(384)
        print("[STARTUP] Fallback FAISS index created (dim=384)")

# ===============================
# LOAD METADATA
# ===============================
if os.path.exists(META_PATH):
    try:
        with open(META_PATH, encoding="utf-8") as f:
            META_RAW = json.load(f)
        print(f"[STARTUP] Metadata loaded from {META_PATH}")
    except Exception as e:
        print(f"[ERROR] Failed to read metadata: {e}")
        META_RAW = {"documents": []}
else:
    print(f"[WARN] Metadata not found at {META_PATH}")
    META_RAW = {"documents": []}

DOCUMENTS = META_RAW.get("documents", [])

# ===============================
# PRE-CALCULATE YEAR INDEX
# ===============================
DOCUMENTS_BY_YEAR = defaultdict(list)
for doc in DOCUMENTS:
    y = doc.get("year")
    if y is not None:
        DOCUMENTS_BY_YEAR[y].append(doc)

print(
    f"[STARTUP] Ready | docs={len(DOCUMENTS)} | years={len(DOCUMENTS_BY_YEAR)}"
)
