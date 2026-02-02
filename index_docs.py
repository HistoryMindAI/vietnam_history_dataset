import os
import json
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

DATA_PATH = "data/history_docs.txt"
OUT_DIR = "faiss_index"
INDEX_PATH = f"{OUT_DIR}/history.index"
META_PATH = f"{OUT_DIR}/meta.json"

EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    with open(DATA_PATH, encoding="utf-8") as f:
        docs = [line.strip() for line in f if len(line.strip()) > 30]

    print(f"[INFO] Docs: {len(docs)}")

    embedder = SentenceTransformer(EMBED_MODEL)

    embeddings = embedder.encode(
        docs,
        convert_to_numpy=True,
        show_progress_bar=True
    ).astype("float32")

    faiss.normalize_L2(embeddings)

    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)

    faiss.write_index(index, INDEX_PATH)

    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(
            [{"id": i, "text": docs[i]} for i in range(len(docs))],
            f,
            ensure_ascii=False,
            indent=2
        )

    print("[DONE] FAISS built")

if __name__ == "__main__":
    main()
