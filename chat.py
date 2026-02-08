import json
import re
import faiss
import unicodedata
from sentence_transformers import SentenceTransformer
from pipeline.storyteller import extract_year

# ================== CONFIG ==================
INDEX_DIR = "faiss_index"
INDEX_PATH = f"{INDEX_DIR}/history.index"
META_PATH = f"{INDEX_DIR}/meta.json"

EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
TOP_K = 15
SIM_THRESHOLD = 0.45
# ============================================

# ---------- QUERY NORMALIZE (NEW) ----------
def normalize_query(query: str) -> str:
    # Keep accents for better semantic search accuracy
    q = query.lower()
    q = unicodedata.normalize("NFC", q)
    q = re.sub(r"\s+", " ", q).strip()

    FUZZY_FIX = {
        "nguyen huye": "nguyen hue",
        "nguyen huee": "nguyen hue",
        "nguyen huej": "nguyen hue",
        "quangtrung": "quang trung",
    }

    for k, v in FUZZY_FIX.items():
        q = q.replace(k, v)

    return q


# ---------- NORMALIZE ----------
def normalize(text: str) -> str:
    # Strip accents for entity matching
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


# ---------- ENTITY ----------
ENTITY_ALIASES = {
    "quang_trung": [
        "quang trung",
        "nguyen hue",
        "bac quang trung",
        "hoang de quang trung"
    ],
    "ho_chi_minh": [
        "ho chi minh",
        "nguyen tat thanh",
        "nguyen ai quoc",
        "bac ho"
    ],
}


BAC_HO_NAMES = {
    "Nguyễn Tất Thành",
    "Hồ Chí Minh",
    "Nguyễn Ái Quốc",
}

ENTITY_ALIASES_NORM = {
    key: [normalize(a) for a in aliases]
    for key, aliases in ENTITY_ALIASES.items()
}


def extract_entities(query: str):
    # Use unaccented normalization for matching against unaccented aliases
    q = normalize(query)
    found = set()

    for key, aliases in ENTITY_ALIASES.items():
        for a in aliases:
            if a in q:
                found.add(key)   # 👈 thêm KEY, không phải alias

    return found


def contains_entity(text: str, entities):
    t = normalize(text)
    return any(e in t for e in entities)


# ---------- LOAD ----------
# Only load if running as main or imported for usage (to avoid import errors in tests if deps missing)
try:
    print("[INFO] Loading model & index...")
    embedder = SentenceTransformer(EMBED_MODEL)
    if faiss:
        try:
            index = faiss.read_index(INDEX_PATH)
        except Exception:
            index = None
    else:
        index = None

    try:
        with open(META_PATH, encoding="utf-8") as f:
            META_RAW = json.load(f)
        DOCUMENTS = META_RAW["documents"]
    except Exception:
        DOCUMENTS = []
except Exception as e:
    print(f"[WARN] Failed to load model/index: {e}")
    embedder = None
    index = None
    DOCUMENTS = []


# ---------- SEARCH ----------
def semantic_search(query: str):
    if not index or not embedder:
        return []

    q_emb = embedder.encode([query], convert_to_numpy=True).astype("float32")
    faiss.normalize_L2(q_emb)

    scores, ids = index.search(q_emb, TOP_K)

    results = []
    for score, idx in zip(scores[0], ids[0]):
        if idx == -1 or score < SIM_THRESHOLD:
            continue
        if idx < len(DOCUMENTS):
            results.append(DOCUMENTS[idx])
    return results

def scan_by_year(year: int):
    return [d for d in DOCUMENTS if d.get("year") == year]

def scan_by_year_range(y1: int, y2: int):
    return [d for d in DOCUMENTS if y1 <= d["year"] <= y2]


def scan_by_entity(entity_keys):
    results = []

    for it in DOCUMENTS:
        text = normalize(it.get("story", "") + " " + it.get("event", ""))

        for key in entity_keys:
            for alias in ENTITY_ALIASES_NORM[key]:
                if alias in text:
                    results.append(it)
                    break

    return results


# ---------- TIMELINE ----------
def to_timeline(items):
    items = sorted(items, key=lambda x: x["year"])

    seen, out = set(), []
    for it in items:
        key = f'{it["year"]}|{normalize(it["event"])}'
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "year": it["year"],
            "title": it["event"],
            "description": it["story"]
        })

    return out


# ---------- YEAR PARSER ----------
def extract_single_year(text: str):
    y = extract_year(text)
    return int(y) if y else None


def extract_year_range(text: str):
    # Tìm tất cả các năm có thể có trong text
    years = sorted(set(map(int, re.findall(r"(?<![\d-])([1-9][0-9]{1,3})(?!\d)", text))))
    # Lọc năm hợp lệ
    years = [y for y in years if 40 <= y <= 2025]
    if len(years) >= 2:
        return years[0], years[-1]
    return None


def engine_answer(query: str) -> dict:
    query_norm = normalize_query(query)

    single_year = extract_single_year(query_norm)
    year_range = extract_year_range(query_norm)
    entities = extract_entities(query) # Pass original query to extract_entities which will normalize internally

    if entities:
        intent = "entity"
        events = scan_by_entity(entities)

    elif single_year:
        intent = "year"
        events = scan_by_year(single_year)

    elif year_range:
        intent = "range"
        events = scan_by_year_range(*year_range)

    else:
        intent = "semantic"
        events = semantic_search(query) # Use original query for semantic search (it normalizes internally in service, but here we do it inside semantic_search?)
        # Wait, semantic_search in chat.py encodes `query` directly.
        # engine_answer passes `query` (original).
        # normalize_query is just used for year extraction here.

    return {
        "query": query,
        "intent": intent,
        "events": events
    }

def render_human(data: dict) -> str:
    events = data["events"]

    if not events:
        return "Mình chưa tìm thấy sự kiện lịch sử phù hợp."

    # Sắp xếp và loại trùng lặp theo story
    seen_stories = set()
    lines = []

    sorted_events = sorted(events, key=lambda x: x.get("year", 0))

    for e in sorted_events:
        story = e.get("story")
        if story and story not in seen_stories:
            seen_stories.add(story)
            lines.append(f"• {story}")

    # Fallback nếu không có story
    if not lines:
        for e in sorted_events:
            lines.append(f"• {e['year']}: {e['event']}")

    return "\n".join(lines)

# ---------- CLI ----------
def main():
    print("👉 Gõ câu hỏi (exit để thoát)\n")
    while True:
        try:
            q = input("🧑 Bạn: ").strip()
        except EOFError:
            break

        if q.lower() in {"exit", "quit"}:
            break

        data = engine_answer(q)

        print("\n🤖 AI (JSON):")
        print(json.dumps(data, ensure_ascii=False, indent=2))

        print("\n🤖 AI (CHAT):")
        print(render_human(data))
        print()


if __name__ == "__main__":
    main()
