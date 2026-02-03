import sys
sys.stdout.reconfigure(encoding="utf-8")

import os
import json
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

# ================== CONFIG ==================
DATA_PATH = "data/history_docs_story.txt"
OUT_DIR = "faiss_index"
INDEX_PATH = f"{OUT_DIR}/history.index"
META_PATH = f"{OUT_DIR}/meta.json"

EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MIN_LEN = 30
# ============================================

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    # 📥 Load & clean docs
    with open(DATA_PATH, encoding="utf-8") as f:
        docs = [
            line.strip()
            for line in f
            if len(line.strip()) >= MIN_LEN
        ]

    # ❗ Deduplicate lần cuối (rất quan trọng)
    docs = sorted(set(docs))

    print(f"[INFO] Docs after clean & dedup: {len(docs)}")

    if not docs:
        print("[ERROR] No documents to index.")
        return

    # 🧠 Load embedding model
    embedder = SentenceTransformer(EMBED_MODEL)

    # 🔢 Encode
    embeddings = embedder.encode(
        docs,
        convert_to_numpy=True,
        show_progress_bar=True
    ).astype("float32")

    # 📐 Normalize for cosine similarity
    faiss.normalize_L2(embeddings)

    # 🗂️ Build FAISS index
    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)

    faiss.write_index(index, INDEX_PATH)

    # 🧾 Save metadata
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(
            [{"id": i, "text": docs[i]} for i in range(len(docs))],
            f,
            ensure_ascii=False,
            indent=2
        )

    print("[DONE] FAISS index & metadata built successfully")

if __name__ == "__main__":
    main()
