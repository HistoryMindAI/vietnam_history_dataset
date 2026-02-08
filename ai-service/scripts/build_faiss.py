"""
FAISS Index Builder

This script rebuilds the FAISS index from the history_timeline.json data.
Run this script when the source data changes:
    python scripts/build_faiss.py

The script will:
1. Load history_timeline.json
2. Generate embeddings for each event  
3. Save the FAISS index and metadata
"""
import json
import sys
from pathlib import Path

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def build_faiss_index():
    """Build FAISS index from source data."""
    import faiss
    import numpy as np
    from sentence_transformers import SentenceTransformer
    
    # Paths
    AI_SERVICE_DIR = Path(__file__).resolve().parent.parent
    DATA_FILE = AI_SERVICE_DIR.parent / "data" / "history_timeline.json"
    INDEX_DIR = AI_SERVICE_DIR / "faiss_index"
    INDEX_DIR.mkdir(exist_ok=True)
    
    print(f"📂 Loading data from: {DATA_FILE}")
    
    # Load timeline data
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        timeline = json.load(f)
    
    # Flatten all events
    documents = []
    for year, data in timeline.items():
        if isinstance(data, dict) and "events" in data:
            for event in data["events"]:
                doc = {
                    "year": int(year),
                    "event": event.get("event", ""),
                    "story": event.get("story", ""),
                    "persons": event.get("persons", []),
                    "places": event.get("places", []),
                }
                documents.append(doc)
    
    print(f"📊 Found {len(documents)} events")
    
    # Generate embeddings
    print("🔧 Loading sentence transformer model...")
    model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    
    print("🧠 Generating embeddings...")
    texts = [f"{d['event']} {d['story']}" for d in documents]
    embeddings = model.encode(texts, show_progress_bar=True)
    
    # Build FAISS index
    print("🔨 Building FAISS index...")
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)  # Inner product for cosine similarity
    
    # Normalize embeddings for cosine similarity
    faiss.normalize_L2(embeddings)
    index.add(embeddings.astype(np.float32))
    
    # Save index and metadata
    faiss.write_index(index, str(INDEX_DIR / "history.index"))
    with open(INDEX_DIR / "meta.json", "w", encoding="utf-8") as f:
        json.dump(documents, f, ensure_ascii=False, indent=2)
    
    print(f"✅ FAISS index saved to: {INDEX_DIR}")
    print(f"   - history.index: {index.ntotal} vectors")
    print(f"   - meta.json: {len(documents)} documents")


if __name__ == "__main__":
    build_faiss_index()
