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


# ---------- NORMALIZE ----------
def normalize(text: str) -> str:
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


# ---------- CLEAN & NORMALIZE TEXT (🔥 FIX DẤU CÂU TRIỆT ĐỂ) ----------
def clean_text(text: str) -> str:
    t = text.strip()

    # remove markdown
    t = re.sub(r"\*\*(.*?)\*\*", r"\1", t)
    t = re.sub(r"`(.*?)`", r"\1", t)

    # remove redundant year phrases
    t = re.sub(r"xảy ra năm\s*\d{3,4}", "", t, flags=re.IGNORECASE)
    t = re.sub(r"Năm\s*\d{3,4},?\s*", "", t)

    # ===== FIX CORE =====
    # thiếu khoảng trắng sau dấu chấm
    t = re.sub(r"\.(\S)", r". \1", t)

    # nhiều dấu chấm liên tiếp
    t = re.sub(r"\.{2,}", ".", t)

    # khoảng trắng trước dấu câu
    t = re.sub(r"\s+([.,;:])", r"\1", t)

    # normalize spaces
    t = re.sub(r"\s+", " ", t).strip()

    # ensure kết câu
    if not t.endswith("."):
        t += "."

    return t


# ---------- YEAR UTILS ----------
YEAR_RE = r"([1-9][0-9]{2,3})"


def extract_event_year(text: str):
    m = re.search(YEAR_RE, text)
    return int(m.group()) if m else None


def extract_year_range(text: str):
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
    "bac ho": ["nguyen tat thanh", "ho chi minh", "nguyen ai quoc"],
}

BAC_HO_NAMES = {
    "Nguyễn Tất Thành",
    "Hồ Chí Minh",
    "Nguyễn Ái Quốc",
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


# ---------- SEARCH ----------
def semantic_search(query: str):
    q_emb = embedder.encode([query], convert_to_numpy=True).astype("float32")
    faiss.normalize_L2(q_emb)

    scores, ids = index.search(q_emb, TOP_K)
    return [
        META[idx]["text"]
        for score, idx in zip(scores[0], ids[0])
        if idx != -1 and score >= SIM_THRESHOLD
    ]


def scan_by_year(year: int):
    return [it["text"] for it in META if extract_event_year(it["text"]) == year]


def scan_by_year_range(y1: int, y2: int):
    return [
        it["text"]
        for it in META
        if (y := extract_event_year(it["text"])) and y1 <= y <= y2
    ]


def scan_by_entity(entities):
    return [it["text"] for it in META if contains_entity(it["text"], entities)]


# ---------- TIMELINE ----------
def to_timeline(texts):
    timeline = []

    for t in texts:
        year = extract_event_year(t)
        if year:
            clean = clean_text(t)
            timeline.append({
                "year": year,
                "title": clean.split(".")[0].strip(),
                "description": clean
            })

    timeline.sort(key=lambda x: x["year"])

    seen, out = set(), []
    for it in timeline:
        key = f"{it['year']}|{normalize(it['title'])}"
        if key not in seen:
            seen.add(key)
            out.append(it)

    return out


# ---------- CORE ENGINE ----------
def engine_answer(query: str) -> dict:
    query = query.strip()

    single_year = extract_single_year(query)
    year_range = extract_year_range(query)
    entities = extract_entities(query)

    if single_year:
        intent = "year"
        events = to_timeline(scan_by_year(single_year))
    elif year_range:
        intent = "range"
        events = to_timeline(scan_by_year_range(*year_range))
    elif entities:
        intent = "entity"
        events = to_timeline(scan_by_entity(entities))
    else:
        intent = "semantic"
        events = to_timeline(semantic_search(query))

    return {
        "query": query,
        "intent": intent,
        "events": events,
    }


# ---------- HUMAN RENDER (KHÔNG CÒN '..') ----------
def render_human(data: dict) -> str:
    events = data["events"]

    if not events:
        return "Mình chưa tìm thấy sự kiện lịch sử phù hợp."

    def apply_vietnamese_style(text: str) -> str:
        for name in BAC_HO_NAMES:
            text = text.replace(name, "Bác")
        return text

    if len(events) == 1:
        e = events[0]
        desc = apply_vietnamese_style(e["description"])
        return f"Năm {e['year']}, {desc}"

    lines = [f"Mình tìm thấy {len(events)} sự kiện:"]
    for e in events:
        title = apply_vietnamese_style(e["title"])
        lines.append(f"• {e['year']}: {title}")
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
