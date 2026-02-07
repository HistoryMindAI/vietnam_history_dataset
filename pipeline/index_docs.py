import sys
sys.stdout.reconfigure(encoding="utf-8")

import os
import json
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from pipeline.storyteller import (
    storyteller,
    pick_tone,
    classify_tone,
    extract_all_persons,
    extract_all_places,
    extract_keywords,
    get_dynasty
)

# ================== CONFIG ==================
CLEANED_DATA_PATH = "data/history_cleaned.jsonl"
OUT_DIR = "ai-service/faiss_index"
INDEX_PATH = f"{OUT_DIR}/history.index"
META_PATH = f"{OUT_DIR}/meta.json"

EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MIN_LEN = 30
# ============================================


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    print(f"[INFO] Loading cleaned data from {CLEANED_DATA_PATH}...")
    documents = []

    if not os.path.exists(CLEANED_DATA_PATH):
        print(f"[ERROR] Cleaned data file not found: {CLEANED_DATA_PATH}")
        return

    with open(CLEANED_DATA_PATH, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f):
            line = line.strip()
            if not line:
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                print(f"[WARN] Skipping invalid JSON at line {line_num}")
                continue

            year = record.get("year", 0)
            content = record.get("content", "")

            # Skip invalid records
            if not content or len(content) < MIN_LEN:
                continue

            # Enrich metadata
            tone_set = classify_tone(content, str(year))
            tone = pick_tone(tone_set)

            # Use content directly as story since it's already narrative
            story = content

            # Extract entities dynamically
            persons = sorted(list(extract_all_persons(content)))
            places = sorted(list(extract_all_places(content)))
            keywords = extract_keywords(content)
            dynasty = get_dynasty(year)

            documents.append({
                "id": record["id"],
                "subject_type": record["subject_type"],
                "year": year,
                "title": record.get("title", ""),
                "event": content, # Using content as event description
                "story": story,
                "tone": tone,
                "nature": record.get("nature", []),
                "persons": persons,
                "places": places,
                "keywords": keywords,
                "dynasty": dynasty
            })

    print(f"[INFO] Stories collected: {len(documents)}")

    if not documents:
        print("[ERROR] No documents to index.")
        return

    # 🧠 Load embedding model
    print(f"[INFO] Loading embedding model {EMBED_MODEL}...")
    embedder = SentenceTransformer(EMBED_MODEL)

    texts = [d["story"] for d in documents]

    embeddings = embedder.encode(
        texts,
        convert_to_numpy=True,
        show_progress_bar=True,
        batch_size=64
    ).astype("float32")

    # 📐 Normalize cosine
    faiss.normalize_L2(embeddings)

    # 🗂️ Build FAISS index
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)

    faiss.write_index(index, INDEX_PATH)

    # 🧾 Save rich metadata
    # The documents list already contains the full record including 'id'
    meta = {
        "model": EMBED_MODEL,
        "dimension": dim,
        "count": len(documents),
        "documents": documents
    }

    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"[DONE] FAISS index built successfully at {INDEX_PATH}")
    print(f"[DONE] Metadata saved at {META_PATH}")


if __name__ == "__main__":
    main()
