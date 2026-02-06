import sys
sys.stdout.reconfigure(encoding="utf-8")

import os
import json
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
import random

# ================== CONFIG ==================
TIMELINE_PATH = "data/history_timeline.json"
OUT_DIR = "faiss_index"
INDEX_PATH = f"{OUT_DIR}/history.index"
META_PATH = f"{OUT_DIR}/meta.json"

EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MIN_LEN = 30
# ============================================


# 🔁 copy đúng storyteller
HEROIC_ENDINGS = [
    "Sự kiện này mở ra một chương sử hào hùng của dân tộc.",
    "Chiến công ấy khẳng định ý chí tự chủ và sức sống bền bỉ của người Việt.",
    "Đây là dấu mốc thể hiện bản lĩnh và khát vọng làm chủ vận mệnh dân tộc.",
]

TRAGIC_ENDINGS = [
    "Đó là giai đoạn bi thương, khi đất nước rơi vào thử thách khắc nghiệt.",
    "Biến cố này để lại những mất mát sâu sắc cho vận mệnh dân tộc.",
    "Thời kỳ ấy ghi dấu nỗi đau và những tổn thất nặng nề của đất nước.",
]

def storyteller(year, tone, content):
    content = content.rstrip(".")
    if tone == "heroic":
        return f"Năm {year}, {content}. {random.choice(HEROIC_ENDINGS)}"
    if tone == "tragic":
        return f"Năm {year}, {content}. {random.choice(TRAGIC_ENDINGS)}"
    return f"Năm {year}, {content}."


def pick_tone(tones: list[str]) -> str:
    if "heroic" in tones:
        return "heroic"
    if "tragic" in tones:
        return "tragic"
    return "neutral"


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    # 📥 Load timeline
    with open(TIMELINE_PATH, encoding="utf-8") as f:
        timeline = json.load(f)

    documents = []

    # 🔄 Build stories from canonical events
    for year, block in timeline.items():
        for e in block["events"]:
            tone = pick_tone(e.get("tone", []))
            story = storyteller(int(year), tone, e["event"])

            if len(story) < MIN_LEN:
                continue

            documents.append({
                "year": int(year),
                "event": e["event"],
                "tone": tone,
                "story": story
            })

    print(f"[INFO] Stories collected: {len(documents)}")

    if not documents:
        print("[ERROR] No documents to index.")
        return

    # 🧠 Load embedding model
    embedder = SentenceTransformer(EMBED_MODEL)

    texts = [d["story"] for d in documents]

    embeddings = embedder.encode(
        texts,
        convert_to_numpy=True,
        show_progress_bar=True
    ).astype("float32")

    # 📐 Normalize cosine
    faiss.normalize_L2(embeddings)

    # 🗂️ Build FAISS index
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)

    faiss.write_index(index, INDEX_PATH)

    # 🧾 Save rich metadata
    meta = {
        "model": EMBED_MODEL,
        "dimension": dim,
        "count": len(documents),
        "documents": [
            {
                "id": i,
                **documents[i]
            }
            for i in range(len(documents))
        ]
    }

    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print("[DONE] FAISS index built from timeline successfully")


if __name__ == "__main__":
    main()
