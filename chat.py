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


# ---------- NORMALIZE (CHỈ DÙNG CHO SO KHỚP) ----------
def normalize(text: str) -> str:
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


# ---------- YEAR UTILS ----------
YEAR_RE = r"(1[0-9]{3}|20[0-2][0-9])"


def extract_event_year(text: str):
    m = re.search(YEAR_RE, text)
    return int(m.group()) if m else None


def extract_year_range(text: str):
    """
    Ưu tiên:
    1. Regex có từ khóa (từ năm X đến năm Y)
    2. Nếu có >= 2 năm → coi là khoảng
    """
    t = normalize(text)

    patterns = [
        rf"tu nam\s*{YEAR_RE}\s*(den|toi)\s*nam\s*{YEAR_RE}",
        rf"{YEAR_RE}\s*(den|toi|-)\s*{YEAR_RE}",
    ]

    for p in patterns:
        m = re.search(p, t)
        if m:
            y1, y2 = int(m.group(1)), int(m.group(3))
            return min(y1, y2), max(y1, y2)

    years = sorted(set(map(int, re.findall(YEAR_RE, t))))
    if len(years) >= 2:
        return years[0], years[-1]

    return None


def extract_single_year(text: str):
    years = re.findall(YEAR_RE, text)
    return int(years[0]) if len(years) == 1 else None


# ---------- ENTITY ----------
ENTITY_ALIASES = {
    "quang trung": ["quang trung", "nguyen hue"],
    "nguyen tat thanh": ["nguyen tat thanh", "ho chi minh"],
}


def extract_entities(query: str):
    q = normalize(query)
    found = set()
    for aliases in ENTITY_ALIASES.values():
        if any(a in q for a in aliases):
            found.update(aliases)
    return found


def contains_entity(text: str, entities):
    t = normalize(text)
    return any(e in t for e in entities)


# ---------- LOAD ----------
print("[INFO] Loading model & index...")
embedder = SentenceTransformer(EMBED_MODEL)
index = faiss.read_index(INDEX_PATH)

with open(META_PATH, encoding="utf-8") as f:
    META = json.load(f)


# ---------- SEMANTIC SEARCH ----------
def semantic_search(query: str):
    q_emb = embedder.encode([query], convert_to_numpy=True).astype("float32")
    faiss.normalize_L2(q_emb)

    scores, ids = index.search(q_emb, TOP_K)
    results = []

    for score, idx in zip(scores[0], ids[0]):
        if idx != -1 and score >= SIM_THRESHOLD:
            results.append(META[idx]["text"])

    return results


# ---------- SCAN ----------
def scan_by_year(year: int):
    return [
        it["text"] for it in META
        if extract_event_year(it["text"]) == year
    ]


def scan_by_year_range(y1: int, y2: int):
    out = []
    for it in META:
        y = extract_event_year(it["text"])
        if y and y1 <= y <= y2:
            out.append(it["text"])
    return out


def scan_by_entity(entities):
    return [
        it["text"] for it in META
        if contains_entity(it["text"], entities)
    ]


# ---------- TIMELINE ----------
def clean_title(text: str):
    """
    TẠO TITLE ĐẸP – GIỮ NGUYÊN TIẾNG VIỆT
    """
    t = text

    t = t.replace("**", "")
    t = re.sub(r"Năm\s*\d{4},?\s*", "", t)
    t = re.sub(r"xảy ra năm\s*\d{4}", "", t, flags=re.IGNORECASE)

    t = t.split(".")[0]
    return t.strip()


def to_timeline(texts):
    timeline = []

    for t in texts:
        year = extract_event_year(t)
        if not year:
            continue

        timeline.append({
            "year": year,
            "title": clean_title(t),
            "description": t
        })

    timeline.sort(key=lambda x: x["year"])

    # dedup mạnh (theo year + title normalize)
    seen = set()
    clean = []
    for it in timeline:
        key = f"{it['year']}|{normalize(it['title'])}"
        if key not in seen:
            seen.add(key)
            clean.append(it)

    return clean


# ---------- ANSWER ----------
def answer(query: str):
    query = query.strip()

    year_range = extract_year_range(query)
    single_year = extract_single_year(query)
    entities = extract_entities(query)

    # 1️⃣ RANGE YEAR
    if year_range:
        return to_timeline(scan_by_year_range(*year_range))

    # 2️⃣ SINGLE YEAR
    if single_year:
        return to_timeline(scan_by_year(single_year))

    # 3️⃣ ENTITY ONLY
    if entities and len(query.split()) <= 3:
        return to_timeline(scan_by_entity(entities))

    # 4️⃣ SEMANTIC
    results = semantic_search(query)
    if entities:
        results = [r for r in results if contains_entity(r, entities)]

    return to_timeline(results)


# ---------- CLI ----------
def main():
    print("👉 Gõ câu hỏi (exit để thoát)\n")
    while True:
        q = input("🧑 Bạn: ").strip()
        if q.lower() in {"exit", "quit"}:
            break

        result = answer(q)

        if not result:
            print("\n🤖 AI: Không có thông tin phù hợp\n")
        else:
            print("\n🤖 AI (TIMELINE JSON):")
            print(json.dumps(result, ensure_ascii=False, indent=2))
            print()


if __name__ == "__main__":
    main()
