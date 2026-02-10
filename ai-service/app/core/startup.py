import os
import json
import gc
from collections import defaultdict

# ===============================
# IMPORTS: MOVED HEAVY LIBS TO load_resources
# ===============================
# import faiss  <-- LAZY LOADED
# from sentence_transformers import SentenceTransformer <-- LAZY LOADED

from .config import (
    EMBED_MODEL,
    INDEX_PATH,
    META_PATH,
    EMBED_MODEL_PATH,
    TOKENIZER_PATH,
)

# Global resources (initialized in load_resources)
session = None
tokenizer = None
index = None
DOCUMENTS = []
DOCUMENTS_BY_YEAR = defaultdict(list)
LOADING_ERROR = None

def load_resources():
    """
    Load all heavy resources (Embedding model, FAISS index, Metadata).
    This should be called during app startup (lifespan) in a background thread.
    """
    global session, tokenizer, index, DOCUMENTS, DOCUMENTS_BY_YEAR, LOADING_ERROR
    
    print("[STARTUP] Loading embedding model & FAISS...", flush=True)

    try:
        # ONNX Imports
        import onnxruntime as ort
        from transformers import AutoTokenizer
        import numpy as np

        # ===============================
        # LOAD ONNX MODEL & TOKENIZER
        # ===============================
        try:
            print(f"[STARTUP] Loading ONNX model from {EMBED_MODEL_PATH}...", flush=True)
            
            # 1. Load Tokenizer (Slow/Fast agnostic)
            # Use local path (onnx_model folder)
            tokenizer = AutoTokenizer.from_pretrained(TOKENIZER_PATH)
            
            print("[STARTUP] Tokenizer loaded.", flush=True)

            # 2. Load ONNX Session
            sess_options = ort.SessionOptions()
            # Optimize for single-core/low-memory envs
            sess_options.intra_op_num_threads = 1 
            sess_options.inter_op_num_threads = 1
            sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            
            session = ort.InferenceSession(EMBED_MODEL_PATH, sess_options)
            print("[STARTUP] ONNX Session loaded successfully.", flush=True)
            
            gc.collect()

        except Exception as e:
            print(f"[FATAL] Failed to load ONNX model: {e}", flush=True)
            raise e

        # ===============================
        # LOAD FAISS INDEX
        # ===============================
        index = None

        if os.path.exists(INDEX_PATH):
            try:
                import faiss
                index = faiss.read_index(INDEX_PATH)
                print(f"[STARTUP] FAISS index loaded from {INDEX_PATH}", flush=True)
            except Exception as e:
                print(f"[ERROR] Failed to read FAISS index: {e}", flush=True)
        else:
            print(f"[WARN] FAISS index not found at {INDEX_PATH}", flush=True)

        # ===============================
        # AUTO-BUILD INDEX IF MISSING
        # ===============================
        if index is None:
            print("[FATAL] FAISS index not found! We are in READ-ONLY mode.", flush=True)
            print("[FATAL] You must build 'faiss_index' locally and commit it to Git.", flush=True)
            # We fail fast here because the user explicitly requested NO server-side building.
            raise RuntimeError("FAISS index missing. Server requires pre-built index.")

        # ===============================
        # LOAD METADATA
        # ===============================
        if os.path.exists(META_PATH):
            try:
                with open(META_PATH, encoding="utf-8") as f:
                    META_RAW = json.load(f)
                print(f"[STARTUP] Metadata loaded from {META_PATH}", flush=True)
            except Exception as e:
                print(f"[ERROR] Failed to read metadata: {e}", flush=True)
                META_RAW = {"documents": []}
        else:
            print(f"[WARN] Metadata not found at {META_PATH}", flush=True)
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
            f"[STARTUP] Ready | docs={len(DOCUMENTS)} | years={len(DOCUMENTS_BY_YEAR)}",
            flush=True
        )

    except Exception as e:
        print(f"❌ [STARTUP] Critical failure in load_resources: {e}", flush=True)
        LOADING_ERROR = str(e)
        # We catch everything so the thread doesn't crash silently without setting the flag.
