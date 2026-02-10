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
    extract_period,
    classify_tone,
    classify_nature,
    normalize_person,
)

# ========================
# CONFIGURATION
# ========================
DATASET_NAME = "minhxthanh/Vietnam-History-1M-Vi"
MAX_SAMPLES = int(os.getenv("MAX_SAMPLES", 500000))
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

    # Remove duplicate year patterns: "Năm 1930, Năm 1930," -> "Năm 1930,"
    result = re.sub(r'(?:Năm\s+(\d{3,4}),?\s*){2,}', r'Năm \1, ', result)

    # Remove redundant "xảy ra năm XXXX" / "diễn ra năm XXXX" anywhere
    result = re.sub(r'\s+(?:xảy ra|diễn ra)\s+(?:vào\s+)?năm\s+\d{3,4}\.?\s*$', '.', result)
    result = re.sub(r'\s+(?:xảy ra|diễn ra)\s+(?:vào\s+)?năm\s+\d{3,4}[;,]\s*', '; ', result)
    # Also handle mid-sentence: "sự kiện xảy ra năm 1930 tại"
    result = re.sub(r'(?:xảy ra|diễn ra)\s+(?:vào\s+)?năm\s+\d{3,4}', '', result)

    # Remove question-style prefixes (meta, not content)
    question_prefixes = [
        r'^Câu\s+hỏi\s+nhắm\s+tới\s+sự\s+kiện\s+',
        r'^Hãy\s+cho\s+biết\s+(?:sự\s+kiện\s+)?(?:tiêu\s+biểu\s+)?(?:của\s+)?(?:Việt\s+Nam\s+)?(?:vào\s+)?',
        r'^Tóm\s+tắt\s+(?:và\s+nêu\s+ý\s+nghĩa\s+lịch\s+sử\s+(?:của\s+)?)?',
        r'^\d{3,4}:\s+',
    ]
    for p in question_prefixes:
        result = re.sub(p, '', result, flags=re.I)

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

    # Remove "Vào năm XXXX, diễn ra" pattern
    result = re.sub(r'^Vào\s+năm\s+\d{3,4},?\s*diễn\s+ra\s*', '', result, flags=re.I)

    # Remove trailing year in parentheses if redundant
    result = re.sub(r'\s*\(\d{3,4}\)\s*\.?\s*$', '', result)

    # Remove ", địa điểm X" trailing metadata
    result = re.sub(r',\s*địa\s+điểm\s+.+$', '.', result)

    # Clean up whitespace and punctuation
    result = re.sub(r'\s+', ' ', result)
    result = result.strip(' ,.-:;')

    return result


# ========================
# HUMANIZE TEXT (Natural Vietnamese prose)
# ========================

# AI template phrases to remove/replace
AI_TEMPLATE_PATTERNS = [
    # "Sự kiện này có ý nghĩa là X" -> "; X" (keep meaning, remove template)
    (re.compile(r'\.\s*Sự kiện này có ý nghĩa là\s*'), ', qua đó '),
    # "Về lâu dài, X" -> "; X"
    (re.compile(r'\.\s*Về lâu dài,?\s*'), ', về lâu dài '),
    # "Đây là cột mốc quan trọng vì X" -> ", X"
    (re.compile(r'\.\s*Đây là cột mốc quan trọng vì\s*'), ', '),
    # "Ý nghĩa: X" -> "; X"
    (re.compile(r'\.\s*Ý nghĩa:\s*'), ', mang ý nghĩa '),
    (re.compile(r';\s*Ý nghĩa:\s*'), ', mang ý nghĩa '),
]

# After these connector phrases, the next word should ALWAYS be lowercase
# (unless it's a proper noun like a person/place name)
CONNECTOR_PHRASES = [
    'qua đó ', 'về lâu dài ', 'mang ý nghĩa ',
    'từ đó ', 'nhờ đó ', 'do đó ',
]

# Vietnamese pronouns to replace repeated names
PRONOUNS_MAP = {
    # (gender_hint, pronoun) — used when we detect repeated person name
    "default": "ông",
    "female": "bà",
}

# Special persons with culturally-specific pronouns
# These override the default ông/bà
SPECIAL_PERSON_PRONOUNS = {
    "hồ chí minh": "Bác",
    "nguyễn tất thành": "Bác",
    "nguyễn ái quốc": "Bác",
    "nguyễn sinh cung": "Bác",
}

# Words that hint female gender
FEMALE_HINTS = {"hoàng hậu", "công chúa", "thái hậu", "hoàng thái hậu", "nữ tướng", "nữ sĩ"}


def _detect_repeated_subject(sentences: list[str]) -> list[tuple[int, str, str]]:
    """
    Detect sentences where the same proper noun (person/place) is the subject
    of consecutive sentences. Returns list of (sentence_index, repeated_name, pronoun).
    """
    replacements = []
    
    for i in range(1, len(sentences)):
        prev = sentences[i - 1].strip()
        curr = sentences[i].strip()
        
        if not prev or not curr:
            continue
        
        # Find multi-word proper nouns at start of current sentence
        # Pattern: 2+ capitalized Vietnamese words at beginning
        m = re.match(
            r'^([A-ZĐÂÊÔƯÀÁẢÃẠÈÉẺẼẸÌÍỈĨỊÒÓỎÕỌÙÚỦŨỤỲÝỶỸỴ]'
            r'[a-zà-ỹ]*'
            r'(?:\s+[A-ZĐÂÊÔƯÀÁẢÃẠÈÉẺẼẸÌÍỈĨỊÒÓỎÕỌÙÚỦŨỤỲÝỶỸỴ]'
            r'[a-zà-ỹ]*){1,4})',
            curr
        )
        if not m:
            continue
        
        name = m.group(1).strip()
        
        # Check if exact same name appears in previous sentence
        if name in prev and len(name) > 3:
            # Check special persons first (e.g. HCM → 'Bác')
            name_lower = name.lower()
            if name_lower in SPECIAL_PERSON_PRONOUNS:
                pronoun = SPECIAL_PERSON_PRONOUNS[name_lower]
            else:
                # Determine pronoun based on gender context
                context_low = (prev + ' ' + curr).lower()
                if any(hint in context_low for hint in FEMALE_HINTS):
                    pronoun = PRONOUNS_MAP["female"]
                else:
                    pronoun = PRONOUNS_MAP["default"]
            
            replacements.append((i, name, pronoun))
    
    return replacements


def _fix_capitalization(text: str) -> str:
    """
    Fix capitalization rules:
    - After '.' -> capitalize
    - After ',' or ';' -> lowercase (unless proper noun)
    - Proper nouns (Vietnamese names, place names) -> keep capitalized
    """
    if not text:
        return text
    
    # Split into sentences by period
    parts = text.split('. ')
    result_parts = []
    
    for part in parts:
        if not part:
            continue
        
        # Capitalize first char of each sentence
        part = part.strip()
        if part and part[0].islower():
            part = part[0].upper() + part[1:]
        
        # Fix internal capitalization after comma/semicolon
        # Only lowercase if it's not a proper noun
        segments = re.split(r'([,;]\s+)', part)
        fixed_segments = [segments[0]]
        
        for j in range(1, len(segments)):
            seg = segments[j]
            if not seg:
                continue
                
            # If this is a separator, keep as-is
            if re.match(r'^[,;]\s+$', seg):
                fixed_segments.append(seg)
                continue
            
            # Check if starts with uppercase but shouldn't
            if seg and seg[0].isupper():
                # Keep capitalized if it's a proper noun (followed by another capitalized word)
                words = seg.split()
                if len(words) >= 2 and words[1] and words[1][0].isupper():
                    # Likely a proper noun - keep
                    fixed_segments.append(seg)
                else:
                    # Check if first word looks like a common word (not proper noun)
                    first_word_lower = words[0].lower() if words else ""
                    common_starts = [
                        "mở", "bảo", "khẳng", "chấm", "củng", "tạo", "giải",
                        "đánh", "nâng", "làm", "thể", "ngăn", "đặt", "mang",
                        "hình", "khởi", "thử", "giảm", "chuẩn", "ổn", "ban",
                        "bước", "buộc", "tạm", "dẫn", "chính", "xây", "phá",
                        "đẩy", "hoàn", "khai", "tiếp", "về", "qua", "từ",
                    ]
                    if first_word_lower in common_starts:
                        seg = seg[0].lower() + seg[1:]
                    fixed_segments.append(seg)
            else:
                fixed_segments.append(seg)
        
        result_parts.append(''.join(fixed_segments))
    
    return '. '.join(result_parts)


def _remove_redundant_year_parens(text: str, year: int) -> str:
    """Remove (YYYY) when it matches the document's year — redundant info."""
    if not year:
        return text
    pattern = re.compile(rf'\s*\({year}\)\s*')
    return pattern.sub(' ', text).strip()


def _clean_leading_artifacts(text: str) -> str:
    """Remove leading 'diễn ra', 'ông trong', etc. that are remnants of question text."""
    patterns = [
        (re.compile(r'^diễn ra\s+', re.I), ''),
        (re.compile(r'^ông trong\s+', re.I), ''),
        (re.compile(r'^đó là\s+', re.I), ''),
    ]
    for p, repl in patterns:
        text = p.sub(repl, text)
    return text


def humanize_story(text: str, year: int = 0, persons: list[str] = None) -> str:
    """
    Transform AI-generated telegraphic text into natural Vietnamese prose.
    
    Applies:
    1. Remove AI template phrases
    2. Merge sentences repeating same subject
    3. Fix capitalization
    4. Remove redundant year parentheses
    5. Clean leading artifacts
    6. Add year context prefix
    """
    if not text or len(text.strip()) < 10:
        return text
    
    result = text.strip()
    
    # Step 1: Clean leading artifacts
    result = _clean_leading_artifacts(result)
    
    # Step 2: Remove redundant year in parentheses
    if year:
        result = _remove_redundant_year_parens(result, year)
    
    # Step 3: Replace AI template phrases with natural connectors
    for pattern, replacement in AI_TEMPLATE_PATTERNS:
        result = pattern.sub(replacement, result)

    # Step 3b: Lowercase the word immediately after connector phrases
    # (unless it's a proper noun: 2+ consecutive capitalized words)
    for connector in CONNECTOR_PHRASES:
        idx = 0
        while True:
            pos = result.lower().find(connector, idx)
            if pos < 0:
                break
            after_pos = pos + len(connector)
            if after_pos < len(result) and result[after_pos].isupper():
                # Check if it's a proper noun (next word also capitalized)
                rest = result[after_pos:]
                words = rest.split(None, 2)
                if len(words) >= 2 and words[1] and words[1][0].isupper():
                    # Proper noun, keep capitalized
                    idx = after_pos + 1
                else:
                    result = result[:after_pos] + result[after_pos].lower() + result[after_pos + 1:]
                    idx = after_pos + 1
            else:
                idx = after_pos + 1
    
    # Step 4: Split into sentences and merge repeated subjects
    # Split by '. ' AND ': ' to catch patterns like "X : Nhân vật X..."
    # First handle ': ' by replacing with '. ' for uniform processing
    result = re.sub(r'\s*:\s+', '. ', result)
    
    sentences = [s.strip() for s in result.split('. ') if s.strip()]
    
    if len(sentences) > 1:
        replacements = _detect_repeated_subject(sentences)
        
        # Apply replacements in reverse order to keep indices valid
        for idx, name, pronoun in reversed(replacements):
            old = sentences[idx]
            # Replace the name at start of sentence with pronoun
            # But keep the name if it's part of a compound phrase
            new = old.replace(name, pronoun.capitalize(), 1)
            sentences[idx] = new
        
        # Try to join short fragmented sentences into natural flow
        merged = []
        i = 0
        while i < len(sentences):
            current = sentences[i]
            
            # If next sentence starts with lowercase or connector, merge
            if i + 1 < len(sentences):
                next_s = sentences[i + 1].strip()
                if next_s and (
                    next_s[0].islower() or 
                    next_s.startswith('và ') or
                    next_s.startswith('cũng ') or
                    next_s.startswith('từ đó ')
                ):
                    current = current.rstrip('.') + ', ' + next_s[0].lower() + next_s[1:]
                    i += 2
                    merged.append(current)
                    continue
            
            merged.append(current)
            i += 1
        
        sentences = merged
    
    result = '. '.join(sentences)
    
    # Step 5: Fix capitalization
    result = _fix_capitalization(result)
    
    # Step 5b: Replace "Hồ Chí Minh" with "Bác" when the main subject
    # is an alias (Nguyễn Tất Thành, Nguyễn Ái Quốc, etc.)
    result_low = result.lower()
    hcm_aliases = ["nguyễn tất thành", "nguyễn ái quốc", "nguyễn sinh cung"]
    if any(alias in result_low for alias in hcm_aliases):
        # Replace "Hồ Chí Minh" (not as subject start) with "Bác"
        result = re.sub(r'(?<!^)(?<!\. )Hồ Chí Minh', 'Bác', result)
        result = re.sub(r'Bác Hồ', 'Bác', result)

    # Step 6: Ensure proper ending
    result = result.strip()
    if result and not result.endswith(('.', '!', '?')):
        result += '.'
    
    # Step 7: Clean double spaces and extra punctuation
    result = re.sub(r'\s+', ' ', result)
    result = re.sub(r'\.\s*\.', '.', result)
    result = re.sub(r',\s*,', ',', result)
    result = re.sub(r';\s*;', ';', result)
    result = re.sub(r'\s+\.', '.', result)
    result = re.sub(r'\s+,', ',', result)
    
    return result.strip()


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
        period = extract_period(year)
        title = extract_event_title(clean_q, clean_a)

        # Ensure event is different from title
        event_text = clean_q[:200]
        if event_text == title:
            event_text = clean_a[:200]

        # Humanize text — make it read like natural Vietnamese prose
        humanized_story = humanize_story(clean_a, year, persons)
        humanized_event = humanize_story(event_text, year, persons)

        doc = {
            "id": f"hf_{i:06d}",
            "year": year,
            "title": title,
            "event": humanized_event,
            "story": humanized_story,
            "tone": tone,
            "nature": nature,
            "persons": persons,
            "places": places,
            "keywords": keywords,
            "dynasty": dynasty,
            "period": period,
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
