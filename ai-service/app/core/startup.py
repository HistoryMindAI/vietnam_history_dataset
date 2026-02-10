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

# Global resources (initialized in load_resources)
embedder = None
index = None
DOCUMENTS = []
DOCUMENTS_BY_YEAR = defaultdict(list)

def load_resources():
    """
    Load all heavy resources (Embedding model, FAISS index, Metadata).
    This should be called during app startup (lifespan).
    """
    global embedder, index, DOCUMENTS, DOCUMENTS_BY_YEAR
    
    print("[STARTUP] Loading embedding model & FAISS...")

    # ===============================
    # LOAD EMBEDDING MODEL
    # ===============================
    try:
        embedder = SentenceTransformer(EMBED_MODEL)
        
        # OPTIMIZATION: Dynamic Quantization REMOVED to prevent startup OOM.
        # We rely on the system having enough RAM or swap for the base model (~470MB).
        # RAM usage varies around 500MB-600MB.
        # If this crashes on 512MB container, we MUST switch to a smaller model.
        import gc
        gc.collect()
        print(f"[STARTUP] Model loaded into memory. GC collected.")
    except Exception as e:
        print(f"[FATAL] Failed to load embedding model: {e}")
        # We might want to raise here, or allow partial failure? 
        # But engine depends on it.
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
    # AUTO-BUILD INDEX IF MISSING
    # ===============================
    if index is None:
        print("[FATAL] FAISS index not found! We are in READ-ONLY mode.")
        print("[FATAL] You must build 'faiss_index' locally and commit it to Git.")
        # We fail fast here because the user explicitly requested NO server-side building.
        raise RuntimeError("FAISS index missing. Server requires pre-built index.")

    # ===============================
    # LOAD METADATA
    # ===============================
    if os.path.exists(META_PATH):
        try:
            print(f"[DEBUG] Loading metadata from ABS PATH: {os.path.abspath(META_PATH)}")
            with open(META_PATH, encoding="utf-8") as f:
                META_RAW = json.load(f)
            print(f"[STARTUP] Metadata loaded from {META_PATH}")
            print(f"[DEBUG] META_RAW keys: {list(META_RAW.keys())}")
            if "documents" in META_RAW:
                print(f"[DEBUG] Found 'documents' with length: {len(META_RAW['documents'])}")
            else:
                print(f"[ERROR] 'documents' key MISSING in meta.json")
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
