import os
import json
import faiss
from collections import defaultdict
from sentence_transformers import SentenceTransformer

# Robust import strategy
try:
    from app.core import config
    EMBED_MODEL = config.EMBED_MODEL
    INDEX_PATH = config.INDEX_PATH
    META_PATH = config.META_PATH
    print(f"[DEBUG] Loaded config successfully. EMBED_MODEL={EMBED_MODEL}")
except ImportError as e:
    print(f"[ERROR] Import app.core.config failed: {e}. Falling back to defaults.")
    EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    INDEX_PATH = "faiss_index/history.index"
    META_PATH = "faiss_index/meta.json"

print("[STARTUP] Loading embedding model & FAISS...")

# ===============================
# LOAD EMBEDDING MODEL
# ===============================
try:
    embedder = SentenceTransformer(EMBED_MODEL)
    print(f"[STARTUP] Loaded embedding model: {EMBED_MODEL}")
except Exception as e:
    print(f"[FATAL] Failed to load embedding model: {e}")
    # Instead of raising immediately, maybe define a dummy? No, service is useless without it.
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
