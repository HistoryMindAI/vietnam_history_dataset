"""
HuggingFace Dataset Loader and FAISS Builder

This script:
1. Downloads Vietnam-History-1M-Vi dataset from HuggingFace
2. Processes and cleans the data
3. Builds FAISS index for semantic search

Run locally: python scripts/build_from_huggingface.py
Run in Railway: automatically via build.sh
"""
import json
import re
import os
import sys
from pathlib import Path
from collections import defaultdict

# ========================
# CONFIGURATION
# ========================
DATASET_NAME = "minhxthanh/Vietnam-History-1M-Vi"
MAX_SAMPLES = int(os.getenv("MAX_SAMPLES", 50000))  # Limit for faster builds
SIMILARITY_THRESHOLD = 0.4

# Junk patterns to filter out
JUNK_PATTERNS = [
    r'^B1\.\s*gắn\s+mốc',
    r'^B2\.\s*nêu\s+diễn\s+biến',
    r'^Câu\s+hỏi\s+nhắm\s+tới',
    r'^Cốt\s+lõi\.',
    r'^Tóm\s+tắt\s+bối\s+cảnh',
    r'^Kể\s+về\s+.+\s+và\s+đóng\s+góp',
    r'^gắn\s+mốc\s+\d+\s+với',
    r'^Giải\s+thích\s+vì\s+sao',
    r'^<think>',
    r'^<analysis>',
]
JUNK_REGEX = [re.compile(p, re.IGNORECASE) for p in JUNK_PATTERNS]


def is_junk(text: str) -> bool:
    """Check if text is junk/meta content."""
    if not text or len(text) < 20:
        return True
    for pattern in JUNK_REGEX:
        if pattern.search(text):
            return True
    return False


def clean_text(text: str) -> str:
    """Clean up text by removing redundant prefixes."""
    if not text:
        return ""
    
    result = text.strip()
    
    # Remove thinking/analysis tags
    result = re.sub(r'<think>.*?</think>', '', result, flags=re.DOTALL)
    result = re.sub(r'<analysis>.*?</analysis>', '', result, flags=re.DOTALL)
    
    # Remove year prefixes
    result = re.sub(r'^Năm\s+\d+[,:]?\s*', '', result)
    result = re.sub(r'^Vào\s+năm\s+\d+[,:]?\s*', '', result, flags=re.IGNORECASE)
    result = re.sub(r'diễn\s+ra\s+năm\s+\d+[.;]?\s*', '', result, flags=re.IGNORECASE)
    
    return result.strip()


def extract_year(text: str) -> int:
    """Extract year from text."""
    match = re.search(r'(?<!\d)([1-2][0-9]{3}|[3-9][0-9]{2})(?!\d)', text)
    if match:
        year = int(match.group(1))
        if 40 <= year <= 2025:
            return year
    return 0


def extract_keywords(text: str) -> set:
    """Extract keywords for deduplication."""
    if not text:
        return set()
    
    stop_words = {
        "năm", "của", "và", "trong", "là", "có", "được", "với", "các", "những",
        "diễn", "ra", "vào", "xảy", "kể", "về", "tóm", "tắt", "gì", "nào",
        "sự", "kiện", "lịch", "sử", "việt", "nam"
    }
    
    normalized = re.sub(r'[^\w\s]', ' ', text.lower())
    words = normalized.split()
    return {w for w in words if len(w) > 2 and w not in stop_words}


def load_from_huggingface():
    """Load dataset from HuggingFace."""
    from datasets import load_dataset
    
    print(f"📥 Loading dataset: {DATASET_NAME}")
    print(f"   Max samples: {MAX_SAMPLES}")
    
    # Load dataset (streaming for memory efficiency)
    dataset = load_dataset(DATASET_NAME, split="train", streaming=True)
    
    documents = []
    seen_keywords = {}  # For deduplication
    
    for i, sample in enumerate(dataset):
        if i >= MAX_SAMPLES:
            break
        
        if i % 10000 == 0:
            print(f"   Processing: {i}/{MAX_SAMPLES}")
        
        # Extract content from messages
        messages = sample.get("messages", [])
        
        # Find user question and assistant answer
        question = ""
        answer = ""
        
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            
            if role == "user":
                question = content
            elif role == "assistant" and not content.startswith("<think"):
                answer = content
        
        # Skip if junk
        if is_junk(question) or is_junk(answer):
            continue
        
        # Clean text
        clean_q = clean_text(question)
        clean_a = clean_text(answer)
        
        if not clean_q or not clean_a or len(clean_a) < 50:
            continue
        
        # Extract year
        year = extract_year(clean_q) or extract_year(clean_a)
        if not year:
            continue
        
        # Deduplicate by keywords
        keywords = extract_keywords(clean_a)
        keyword_key = tuple(sorted(list(keywords)[:10]))  # Use first 10 keywords
        
        if keyword_key in seen_keywords:
            # Keep longer answer
            existing_idx = seen_keywords[keyword_key]
            if len(clean_a) > len(documents[existing_idx].get("story", "")):
                documents[existing_idx]["story"] = clean_a
            continue
        
        doc = {
            "id": f"hf_{i:06d}",
            "year": year,
            "event": clean_q[:200],
            "story": clean_a,
            "persons": [],
            "places": [],
            "keywords": list(keywords)[:5],
        }
        
        seen_keywords[keyword_key] = len(documents)
        documents.append(doc)
    
    print(f"✅ Loaded {len(documents)} unique documents")
    return documents


def build_faiss_index(documents: list, output_dir: Path):
    """Build FAISS index from documents."""
    import faiss
    import numpy as np
    from sentence_transformers import SentenceTransformer
    
    print(f"\n📚 Building FAISS from {len(documents)} documents")
    
    # Load model
    print("🔧 Loading sentence transformer...")
    model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    
    # Generate embeddings
    print("🧠 Generating embeddings...")
    texts = [f"{d['event']} {d['story'][:500]}" for d in documents]
    embeddings = model.encode(texts, show_progress_bar=True, batch_size=64)
    
    # Build index
    print("🔨 Building FAISS index...")
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)
    
    faiss.normalize_L2(embeddings)
    index.add(embeddings.astype(np.float32))
    
    # Save
    output_dir.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(output_dir / "history.index"))
    
    # Save metadata
    meta = {
        "model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        "dimension": dimension,
        "count": len(documents),
        "source": DATASET_NAME,
        "documents": documents
    }
    
    with open(output_dir / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ FAISS index saved: {output_dir}")
    print(f"   - Vectors: {index.ntotal}")
    print(f"   - Documents: {len(documents)}")


def main():
    AI_SERVICE_DIR = Path(__file__).resolve().parent.parent
    INDEX_DIR = AI_SERVICE_DIR / "faiss_index"
    
    # Load from HuggingFace
    documents = load_from_huggingface()
    
    if not documents:
        print("❌ No documents loaded!")
        sys.exit(1)
    
    # Build FAISS
    build_faiss_index(documents, INDEX_DIR)
    
    print("\n🎉 Done! FAISS index is ready.")


if __name__ == "__main__":
    main()
