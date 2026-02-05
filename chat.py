import json
import re
import faiss
import unicodedata
from sentence_transformers import SentenceTransformer

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
    q = query.lower()
    q = unicodedata.normalize("NFD", q)
    q = "".join(c for c in q if unicodedata.category(c) != "Mn")
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
    q = normalize_query(query)
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
print("[INFO] Loading model & index...")
embedder = SentenceTransformer(EMBED_MODEL)
index = faiss.read_index(INDEX_PATH)

with open(META_PATH, encoding="utf-8") as f:
    META_RAW = json.load(f)

DOCUMENTS = META_RAW["documents"]


# ---------- SEARCH ----------
def semantic_search(query: str):
    q_emb = embedder.encode([query], convert_to_numpy=True).astype("float32")
    faiss.normalize_L2(q_emb)

    scores, ids = index.search(q_emb, TOP_K)

    results = []
    for score, idx in zip(scores[0], ids[0]):
        if idx == -1 or score < SIM_THRESHOLD:
            continue
        results.append(DOCUMENTS[idx])   # ⚠️ dùng DOCUMENTS
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
YEAR_RE = r"(?:nam\s*)?([1-9][0-9]{2,3})"


def extract_single_year(text: str):
    years = list(dict.fromkeys(map(int, re.findall(YEAR_RE, text))))
    return years[0] if len(years) == 1 else None


def extract_year_range(text: str):
    years = sorted(set(map(int, re.findall(YEAR_RE, text))))
    if len(years) >= 2:
        return years[0], years[-1]
    return None


def engine_answer(query: str) -> dict:
    query_norm = normalize_query(query)

    single_year = extract_single_year(query_norm)
    year_range = extract_year_range(query_norm)
    entities = extract_entities(query_norm)

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
        events = semantic_search(query)

    return {
        "query": query,
        "intent": intent,
        "events": events
    }

def render_human(data: dict) -> str:
    events = data["events"]

    if not events:
        return "Mình chưa tìm thấy sự kiện lịch sử phù hợp."

    lines = []
    for e in events:
        lines.append(f"• {e['year']}: {e['event']}")

    return "\n".join(lines)

# ---------- CLI ----------
def main():
    print("👉 Gõ câu hỏi (exit để thoát)\n")
    while True:
        q = input("🧑 Bạn: ").strip()
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
