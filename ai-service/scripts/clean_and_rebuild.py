"""
Data Cleaner and FAISS Rebuilder

This script:
1. Cleans the history_timeline.json by removing junk entries
2. Deduplicates events per year, keeping the most complete one
3. Rebuilds the FAISS index with clean data

Run: python scripts/clean_and_rebuild.py
"""
import json
import re
import sys
from pathlib import Path
from collections import defaultdict

# Patterns that indicate junk/meta entries (not actual historical content)
JUNK_PATTERNS = [
    r'^B1\.\s*gắn\s+mốc',           # "B1. gắn mốc 905 với..."
    r'^B2\.\s*nêu\s+diễn\s+biến',   # "B2. nêu diễn biến trọng tâm..."
    r'^Câu\s+hỏi\s+nhắm\s+tới',      # "Câu hỏi nhắm tới sự kiện..."
    r'^Cốt\s+lõi\.',                  # "Cốt lõi. ..."
    r'^Tóm\s+tắt\s+bối\s+cảnh',       # "Tóm tắt bối cảnh..."
    r'^Kể\s+về\s+.+\s+và\s+đóng\s+góp', # "Kể về X và đóng góp..."
    r'^gắn\s+mốc\s+\d+\s+với',        # "gắn mốc 1911 với..."
    r'^Giải\s+thích\s+vì\s+sao',      # "Giải thích vì sao..."
    r'^Bối\s+cảnh:',                   # "Bối cảnh: ..."
]

# Compiled patterns for performance
JUNK_REGEX = [re.compile(p, re.IGNORECASE) for p in JUNK_PATTERNS]


def is_junk_event(text: str) -> bool:
    """Check if event text is a junk/meta entry."""
    if not text:
        return True
    for pattern in JUNK_REGEX:
        if pattern.search(text):
            return True
    return False


def clean_event_text(text: str) -> str:
    """Clean up event text by removing redundant prefixes."""
    if not text:
        return ""
    
    result = text.strip()
    
    # Remove redundant year prefixes
    result = re.sub(r'^Năm\s+\d+[,:]?\s*', '', result)
    result = re.sub(r'^Vào\s+năm\s+\d+[,:]?\s*', '', result, flags=re.IGNORECASE)
    result = re.sub(r'diễn\s+ra\s+năm\s+\d+[.;]?\s*', '', result, flags=re.IGNORECASE)
    result = re.sub(r'xảy\s+ra\s+năm\s+\d+[.;]?\s*', '', result, flags=re.IGNORECASE)
    
    # Remove trailing (year).
    result = re.sub(r'\s*\(\d{4}\)[.:,]?\s*$', '', result)
    
    return result.strip()


def extract_keywords(text: str) -> set:
    """Extract keywords for deduplication."""
    if not text:
        return set()
    
    stop_words = {
        "năm", "của", "và", "trong", "là", "có", "được", "với", "các", "những",
        "diễn", "ra", "vào", "xảy", "kể", "về", "tóm", "tắt", "gì", "nào",
    }
    
    normalized = re.sub(r'[^\w\s]', ' ', text.lower())
    words = normalized.split()
    return {w for w in words if len(w) > 2 and w not in stop_words}


def deduplicate_events(events: list) -> list:
    """Deduplicate events, keeping the most complete version."""
    if not events:
        return []
    
    # Group by similar content
    groups = []
    used = set()
    
    for i, event in enumerate(events):
        if i in used:
            continue
        
        event_text = event.get("event", "")
        event_keywords = extract_keywords(event_text)
        
        # Start a new group with this event
        group = [event]
        used.add(i)
        
        # Find similar events
        for j, other in enumerate(events):
            if j <= i or j in used:
                continue
            
            other_text = other.get("event", "")
            other_keywords = extract_keywords(other_text)
            
            # Calculate Jaccard similarity
            if event_keywords and other_keywords:
                intersection = len(event_keywords & other_keywords)
                union = len(event_keywords | other_keywords)
                similarity = intersection / union if union > 0 else 0
                
                if similarity > 0.4:
                    group.append(other)
                    used.add(j)
        
        groups.append(group)
    
    # Keep the best (longest, most complete) event from each group
    result = []
    for group in groups:
        best = max(group, key=lambda e: len(e.get("event", "") or ""))
        
        # Merge persons and places from all versions
        all_persons = set()
        all_places = set()
        for e in group:
            all_persons.update(e.get("persons", []) + e.get("persons_all", []))
            all_places.update(e.get("places", []))
        
        best["persons"] = list(all_persons)
        best["places"] = list(all_places)
        result.append(best)
    
    return result


def clean_timeline(timeline: dict) -> dict:
    """Clean the entire timeline, removing junk and deduplicating."""
    cleaned = {}
    stats = {"years": 0, "events_before": 0, "events_after": 0, "junk_removed": 0}
    
    for year, data in timeline.items():
        if not isinstance(data, dict) or "events" not in data:
            continue
        
        events = data.get("events", [])
        stats["events_before"] += len(events)
        
        # Step 1: Filter out junk events
        clean_events = []
        for event in events:
            event_text = event.get("event", "")
            if is_junk_event(event_text):
                stats["junk_removed"] += 1
                continue
            
            # Clean the text
            event["event"] = clean_event_text(event_text)
            if event.get("story"):
                event["story"] = clean_event_text(event["story"])
            
            if event["event"]:  # Only keep if there's still content
                clean_events.append(event)
        
        # Step 2: Deduplicate similar events
        deduped = deduplicate_events(clean_events)
        
        if deduped:
            cleaned[year] = {
                "summary": data.get("summary", ""),
                "events": deduped
            }
            stats["years"] += 1
            stats["events_after"] += len(deduped)
    
    print(f"📊 Cleaning Stats:")
    print(f"   Years: {stats['years']}")
    print(f"   Events before: {stats['events_before']}")
    print(f"   Events after:  {stats['events_after']}")
    print(f"   Junk removed:  {stats['junk_removed']}")
    print(f"   Dedup savings: {stats['events_before'] - stats['junk_removed'] - stats['events_after']}")
    
    return cleaned


def build_faiss_from_clean_data(timeline: dict, output_dir: Path):
    """Build FAISS index from cleaned timeline data."""
    import faiss
    import numpy as np
    from sentence_transformers import SentenceTransformer
    
    # Flatten events
    documents = []
    for year, data in timeline.items():
        for event in data.get("events", []):
            doc = {
                "id": f"hm_{year}_{len(documents):03d}",
                "year": int(year),
                "title": event.get("event", "")[:100],
                "event": event.get("event", ""),
                "story": event.get("story", "") or event.get("event", ""),
                "persons": event.get("persons", []),
                "places": event.get("places", []),
                "keywords": event.get("keywords", []),
                "dynasty": event.get("dynasty", ""),
                "tone": event.get("tone", ["neutral"])[0] if isinstance(event.get("tone"), list) else event.get("tone", "neutral"),
                "nature": event.get("nature", ["general"])
            }
            documents.append(doc)
    
    print(f"\n📚 Total documents: {len(documents)}")
    
    # Generate embeddings
    print("🔧 Loading sentence transformer model...")
    model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    
    print("🧠 Generating embeddings...")
    texts = [f"{d['event']} {d.get('story', '')}" for d in documents]
    embeddings = model.encode(texts, show_progress_bar=True)
    
    # Build FAISS index
    print("🔨 Building FAISS index...")
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)
    
    faiss.normalize_L2(embeddings)
    index.add(embeddings.astype(np.float32))
    
    # Save
    output_dir.mkdir(exist_ok=True)
    faiss.write_index(index, str(output_dir / "history.index"))
    
    meta = {
        "model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        "dimension": dimension,
        "count": len(documents),
        "documents": documents
    }
    with open(output_dir / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ FAISS index saved to: {output_dir}")
    print(f"   - history.index: {index.ntotal} vectors")
    print(f"   - meta.json: {len(documents)} documents")
    
    # Also save cleaned timeline
    cleaned_path = output_dir.parent.parent / "data" / "history_timeline_clean.json"
    with open(cleaned_path, "w", encoding="utf-8") as f:
        json.dump(timeline, f, ensure_ascii=False, indent=2)
    print(f"   - Cleaned timeline: {cleaned_path}")


def main():
    # Paths
    AI_SERVICE_DIR = Path(__file__).resolve().parent.parent
    DATA_FILE = AI_SERVICE_DIR.parent / "data" / "history_timeline.json"
    INDEX_DIR = AI_SERVICE_DIR / "faiss_index"
    
    print(f"📂 Loading data from: {DATA_FILE}")
    
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        timeline = json.load(f)
    
    print(f"\n🧹 Cleaning data...")
    cleaned = clean_timeline(timeline)
    
    print(f"\n🔨 Building FAISS index...")
    build_faiss_from_clean_data(cleaned, INDEX_DIR)


if __name__ == "__main__":
    main()
