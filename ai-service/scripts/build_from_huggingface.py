"""
HuggingFace Dataset Loader and FAISS Builder - V2

This script:
1. Downloads Vietnam-History-1M-Vi dataset from HuggingFace
2. Processes with dynamic entity extraction (persons, places, keywords)
3. Builds FAISS index for semantic search

Key improvements over V1:
- Dynamic entity extraction using entity_registry.py
- Smart year extraction (handles "kỷ niệm 1000 năm" edge cases)
- Better dedup with higher threshold
- Full keyword, person, place extraction
- Tone and nature classification

Run locally: python scripts/build_from_huggingface.py
"""
import json
import re
import os
import sys
from pathlib import Path
from collections import defaultdict

# Add parent to path for imports
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from entity_registry import (
    extract_persons,
    extract_places,
    extract_year_smart,
    extract_keywords_smart,
    extract_dynasty,
    classify_tone,
    classify_nature,
    normalize_person,
)

# ========================
# CONFIGURATION
# ========================
DATASET_NAME = "minhxthanh/Vietnam-History-1M-Vi"
MAX_SAMPLES = int(os.getenv("MAX_SAMPLES", 200000))
DEDUP_THRESHOLD = float(os.getenv("DEDUP_THRESHOLD", 0.85))
MIN_ANSWER_LENGTH = int(os.getenv("MIN_ANSWER_LENGTH", 30))
MIN_DOCS_TARGET = 5000

# ========================
# TEXT CLEANING
# ========================

# Patterns that indicate junk/meta content (not actual history)
JUNK_PATTERNS = [
    re.compile(r'^B\d+\.\s*gắn\s+mốc', re.I),
    re.compile(r'^B\d+\.\s*nêu\s+diễn\s+biến', re.I),
    re.compile(r'^Câu\s+hỏi\s+nhắm\s+tới', re.I),
    re.compile(r'^Cốt\s+lõi\.', re.I),
    re.compile(r'^<think>', re.I),
    re.compile(r'^<analysis>', re.I),
    re.compile(r'^\s*$'),
]


def is_junk(text: str) -> bool:
    """Check if text is junk/meta content that should be filtered."""
    if not text or len(text.strip()) < 15:
        return True
    for pattern in JUNK_PATTERNS:
        if pattern.search(text):
            return True
    return False


def clean_text(text: str) -> str:
    """
    Clean text by removing redundant prefixes, meta-content, and formatting artifacts.
    Preserves meaningful historical content.
    """
    if not text:
        return ""

    result = text.strip()

    # Remove AI thinking/analysis tags
    result = re.sub(r'<think>.*?</think>', '', result, flags=re.DOTALL)
    result = re.sub(r'<analysis>.*?</analysis>', '', result, flags=re.DOTALL)

    # Remove markdown bold
    result = re.sub(r'\*\*(.*?)\*\*', r'\1', result)

    # Remove structural prefixes (meta-instructions, not content)
    structural_patterns = [
        r'^Tóm\s+tắt\s+bối\s+cảnh\s*[–-]\s*diễn\s+biến\s*[–-]\s*kết\s+quả\s+(?:của\s+)?',
        r'^Kể\s+về\s+.{5,60}?\s+và\s+đóng\s+góp\s+(?:của\s+)?',
        r'^Giải\s+thích\s+vì\s+sao\s+',
        r'^Bối\s+cảnh\s*:\s*',
        r'^Diễn\s+biến\s*:\s*',
        r'^Kết\s+quả\s*:\s*',
    ]
    for p in structural_patterns:
        result = re.sub(p, '', result, flags=re.I)

    # Remove "gắn mốc XXXX với" pattern
    result = re.sub(r'^gắn\s+mốc\s+\d+\s+với\s*', '', result, flags=re.I)

    # Remove year prefix only at the start (keep in body)
    result = re.sub(r'^(?:Vào\s+)?[Nn]ăm\s+\d{3,4}[,:]?\s*', '', result)

    # Remove trailing year in parentheses if redundant
    result = re.sub(r'\s*\(\d{3,4}\)\s*\.?\s*$', '', result)

    # Clean up whitespace and punctuation
    result = re.sub(r'\s+', ' ', result)
    result = result.strip(' ,.-:;')

    return result


def extract_event_title(question: str, answer: str) -> str:
    """
    Dynamically extract a short event title from question+answer text.
    Prefers the question text as it's usually more concise.
    """
    # Try from question first (usually more concise)
    source = question if question else answer
    source = clean_text(source)

    if not source:
        return ""

    # Take first meaningful sentence/clause
    parts = re.split(r'[.!?]', source)
    title = parts[0].strip() if parts else source

    # Limit length
    if len(title) > 120:
        # Try splitting by comma
        comma_parts = title.split(',')
        title = comma_parts[0].strip()

    return title[:150]


# ========================
# DEDUPLICATION (Hash-based fingerprint - PER YEAR)
# ========================

def _text_fingerprint(text: str) -> frozenset[str]:
    """
    Create a fingerprint of text using normalized keyword set.
    Much faster than SequenceMatcher for dedup.
    """
    if not text:
        return frozenset()
    # Normalize: lowercase, remove punctuation, split into words
    normalized = re.sub(r'[^\w\s]', ' ', text[:500].lower())
    words = normalized.split()
    # Keep only meaningful words (>2 chars, skip common stopwords)
    stop = {"năm", "của", "và", "trong", "là", "có", "được", "với", "các", "những",
            "này", "đó", "cho", "khi", "đã", "sẽ", "từ", "về", "theo", "tại",
            "một", "hai", "như", "không", "trên", "cũng", "sau", "trước"}
    return frozenset(w for w in words if len(w) > 2 and w not in stop)


def is_duplicate(new_story: str, year_fingerprints: list[frozenset], max_jaccard: float = 0.6) -> bool:
    """
    Check if new_story is a duplicate using per-year fingerprint comparison.
    A doc is duplicate if it shares >60% keywords with an existing doc of same year.
    """
    new_fp = _text_fingerprint(new_story)
    if not new_fp or len(new_fp) < 3:
        return True

    for existing_fp in year_fingerprints:
        if not existing_fp:
            continue
        intersection = new_fp & existing_fp
        union = new_fp | existing_fp
        if not union:
            continue
        jaccard = len(intersection) / len(union)
        if jaccard > max_jaccard:
            return True

    return False


# ========================
# MAIN PIPELINE
# ========================

def load_from_huggingface() -> list[dict]:
    """
    Load and process dataset from HuggingFace.
    Uses dynamic extraction for all entity types.
    """
    from datasets import load_dataset

    print(f"📥 Loading dataset: {DATASET_NAME}")
    print(f"   Max samples: {MAX_SAMPLES}")
    print(f"   Dedup threshold: {DEDUP_THRESHOLD}")

    dataset = load_dataset(DATASET_NAME, split="train", streaming=True)

    documents: list[dict] = []
    year_fingerprints: dict[int, list[frozenset]] = defaultdict(list)
    stats = {"total": 0, "no_year": 0, "junk": 0, "dup": 0, "short": 0, "kept": 0}

    for i, sample in enumerate(dataset):
        if i >= MAX_SAMPLES:
            break

        if i % 20000 == 0:
            print(f"   Processing: {i:,}/{MAX_SAMPLES:,} | Kept: {stats['kept']:,}")

        stats["total"] += 1

        # Extract content from messages
        messages = sample.get("messages", [])
        question = ""
        answer = ""

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")

            if role == "user":
                question = content
            elif role == "assistant" and not content.startswith("<think"):
                answer = content

        # Filter junk
        if is_junk(answer):
            stats["junk"] += 1
            continue

        # Clean text
        clean_q = clean_text(question)
        clean_a = clean_text(answer)

        if not clean_a or len(clean_a) < MIN_ANSWER_LENGTH:
            stats["short"] += 1
            continue

        # === DYNAMIC EXTRACTION ===

        # Year (smart extraction with anniversary handling)
        combined_text = f"{clean_q} {clean_a}"
        year = extract_year_smart(clean_q) or extract_year_smart(clean_a)
        if not year:
            stats["no_year"] += 1
            continue

        # Per-year dedup by fingerprint
        if is_duplicate(clean_a, year_fingerprints[year]):
            stats["dup"] += 1
            continue

        # Add fingerprint for future dedup checks
        fp = _text_fingerprint(clean_a)
        year_fingerprints[year].append(fp)

        # Dynamic entity extraction
        persons = extract_persons(combined_text)
        places = extract_places(combined_text)
        keywords = extract_keywords_smart(combined_text, persons, places)
        tone = classify_tone(combined_text)
        nature = classify_nature(combined_text)
        dynasty = extract_dynasty(combined_text, year)
        title = extract_event_title(clean_q, clean_a)

        doc = {
            "id": f"hf_{i:06d}",
            "year": year,
            "title": title,
            "event": clean_q[:200],
            "story": clean_a,
            "tone": tone,
            "nature": nature,
            "persons": persons,
            "places": places,
            "keywords": keywords,
            "dynasty": dynasty,
        }

        documents.append(doc)
        stats["kept"] += 1

    print(f"\n📊 Pipeline Statistics:")
    print(f"   Total processed: {stats['total']:,}")
    print(f"   Junk filtered:   {stats['junk']:,}")
    print(f"   Short filtered:  {stats['short']:,}")
    print(f"   No year found:   {stats['no_year']:,}")
    print(f"   Duplicates:      {stats['dup']:,}")
    print(f"   ✅ Kept:          {stats['kept']:,}")

    unique_years = len(set(d["year"] for d in documents))
    print(f"   Unique years:    {unique_years}")

    if stats["kept"] < MIN_DOCS_TARGET:
        print(f"\n⚠️  Only {stats['kept']} docs (target: {MIN_DOCS_TARGET})")
        print("   Consider increasing MAX_SAMPLES or decreasing DEDUP_THRESHOLD")

    return documents


def build_faiss_index(documents: list[dict], output_dir: Path):
    """Build FAISS index from documents."""
    import faiss
    import numpy as np
    from sentence_transformers import SentenceTransformer

    print(f"\n📚 Building FAISS from {len(documents)} documents")

    # Load model
    print("🔧 Loading sentence transformer...")
    model = SentenceTransformer("keepitreal/vietnamese-sbert")

    # Generate embeddings from combined text for better search
    print("🧠 Generating embeddings...")
    texts = []
    for d in documents:
        # Combine event + story + keywords for richer embeddings
        kw_text = " ".join(d.get("keywords", []))
        person_text = " ".join(d.get("persons", []))
        combined = f"{d['event']} {d['story'][:500]} {kw_text} {person_text}"
        texts.append(combined)

    embeddings = model.encode(texts, show_progress_bar=True, batch_size=64)

    # Build index
    print("🔨 Building FAISS index...")
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)

    faiss.normalize_L2(embeddings)
    index.add(embeddings.astype(np.float32))

    # Save
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save index as both names for compatibility
    faiss.write_index(index, str(output_dir / "index.bin"))
    faiss.write_index(index, str(output_dir / "history.index"))

    # Save metadata
    meta = {
        "model": "keepitreal/vietnamese-sbert",
        "dimension": dimension,
        "count": len(documents),
        "source": DATASET_NAME,
        "documents": documents,
    }

    with open(output_dir / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"\n✅ FAISS index saved: {output_dir}")
    print(f"   - Vectors: {index.ntotal}")
    print(f"   - Documents: {len(documents)}")
    print(f"   - Index files: index.bin, history.index")


def main():
    AI_SERVICE_DIR = Path(__file__).resolve().parent.parent
    INDEX_DIR = AI_SERVICE_DIR / "faiss_index"

    # Load from HuggingFace with dynamic extraction
    documents = load_from_huggingface()

    if not documents:
        print("❌ No documents loaded!")
        sys.exit(1)

    # Build FAISS
    build_faiss_index(documents, INDEX_DIR)

    print("\n🎉 Done! FAISS index is ready.")
    print(f"   Documents: {len(documents)}")
    print(f"   Index: {INDEX_DIR}")


if __name__ == "__main__":
    main()
