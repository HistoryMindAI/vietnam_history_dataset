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
        
        # OPTIMIZATION: Apply Dynamic Quantization to reduce RAM usage by ~60%
        # This keeps the L12 model quality but fits it into Free Tier memory.
        import torch
        print(f"[STARTUP] Quantizing model {EMBED_MODEL} to int8...")
        embedder[0].auto_model = torch.quantization.quantize_dynamic(
            embedder[0].auto_model, {torch.nn.Linear}, dtype=torch.qint8
        )
        print(f"[STARTUP] Model quantized successfully.")
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
