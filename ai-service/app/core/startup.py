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
        print(f"[STARTUP] Loaded embedding model: {EMBED_MODEL}")
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
        print("[STARTUP] FAISS index not found. Attempting to build from documents...")
        try:
            from app.services.vector import build_index
            
            if os.path.exists(META_PATH):
                with open(META_PATH, encoding="utf-8") as f:
                   temp_meta = json.load(f)
                temp_docs = temp_meta.get("documents", [])
            else:
                print("[STARTUP] Metadata file not found locally. Attempting to load from HuggingFace...")
                try:
                    from datasets import load_dataset
                    # Load dataset from Hub
                    dataset = load_dataset("minhxthanh/Vietnam-History-1M-Vi", split="train")
                    print(f"[STARTUP] Loaded {len(dataset)} items from HuggingFace.")
                    
                    # Convert to document format expected by engine
                    temp_docs = []
                    for item in dataset:
                        # Adjust fields based on actual dataset structure
                        doc = {
                            "year": item.get("year", 0),
                            "event": item.get("title", "") or item.get("text", "")[:50],
                            "story": item.get("text", ""),
                            "title": item.get("title", ""),
                            "dynasty": item.get("dynasty", ""),
                            "persons": item.get("persons", []),
                            "places": item.get("places", [])
                        }
                        temp_docs.append(doc)
                    
                    # Save metadata for future use
                    os.makedirs(os.path.dirname(META_PATH), exist_ok=True)
                    with open(META_PATH, "w", encoding="utf-8") as f:
                        json.dump({"documents": temp_docs}, f, ensure_ascii=False, indent=2)
                    print(f"[STARTUP] Saved metadata to {META_PATH}")
                    
                except Exception as e:
                    print(f"[ERROR] Failed to load from HuggingFace: {e}")
                    temp_docs = []

            if temp_docs:
                print(f"[STARTUP] Found {len(temp_docs)} documents. Building index...")
                index = build_index(temp_docs, embedder)
                
                # Save the newly built index
                faiss.write_index(index, INDEX_PATH)
                print(f"[STARTUP] Index built and saved to {INDEX_PATH}")
            else:
                print("[WARN] No documents found in metadata. Creating empty index.")
                d = embedder.get_sentence_embedding_dimension()
                index = faiss.IndexFlatL2(d)
                
        except Exception as e:
            print(f"[ERROR] Failed to build index: {e}")
            # Fallback to empty index to ensure app starts
            d = 384
            try:
                d = embedder.get_sentence_embedding_dimension()
            except:
                pass
            index = faiss.IndexFlatL2(d)
            print(f"[STARTUP] Fallback empty index created (dim={d})")

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
