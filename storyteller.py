# storyteller_ultimate.py
import sys
sys.stdout.reconfigure(encoding="utf-8")

import re
import random
from pathlib import Path
from datasets import load_dataset

# ================== CONFIG ==================
DATASET_DIR = Path(
    "vietnam_history_dataset/default/0.0.0/3fdbbebc92e755190b4eaeb1522d97a753f0f18a"
)

ARROW_FILES = [
    str(DATASET_DIR / "vietnam-history-1_m-vi-train-00000-of-00002.arrow"),
    str(DATASET_DIR / "vietnam-history-1_m-vi-train-00001-of-00002.arrow"),
]

OUT_PATH = "data/history_docs_storyteller_ultimate.txt"

# ================= YEAR =================
YEAR_AT_START = re.compile(r"^Năm\s+([1-9][0-9]{2,3})[,:]?\s*", re.I)
YEAR_INLINE = re.compile(r"\bnăm\s+([1-9][0-9]{2,3})\b", re.I)

# ================= FILTER =================
FORBIDDEN_KEYWORDS = [
    "câu hỏi", "hãy cho biết", "trình bày",
    "dataset", "json", "assistant", "user",
    "ý nghĩa", "cột mốc quan trọng"
]

# ================= EVENT TYPE =================
TRAGIC_HINTS = [
    "bị đô hộ", "mất nước", "bảo hộ",
    "chia cắt", "xâm lược", "đầu hàng"
]

HEROIC_HINTS = [
    "đánh bại", "chiến thắng", "giải phóng",
    "tiêu diệt", "đập tan"
]

# ================= STORY VOICE =================
OPENING_TRAGIC = [
    "Bước sang năm {year}, lịch sử dân tộc rẽ vào một quãng trầm đầy biến động.",
    "Năm {year}, non sông đứng trước thử thách nghiệt ngã của thời cuộc."
]

OPENING_HEROIC = [
    "Gió lửa nổi lên vào năm {year}, khi non sông bước vào giờ phút quyết định.",
    "Năm {year}, ý chí quật cường của dân tộc bừng sáng giữa phong ba."
]

OPENING_FATE = [
    "Giữa dòng chảy lịch sử, năm {year} hiện lên như một dấu mốc định hình vận mệnh dân tộc.",
    "Năm {year}, lịch sử lặng lẽ chuyển mình theo một hướng đi mới."
]

ENDING_TRAGIC = [
    "Từ đây, đất nước bước vào những năm tháng cam go, hun đúc ý chí tồn sinh.",
    "Biến cố ấy để lại vết hằn sâu trong hành trình lịch sử dân tộc."
]

ENDING_HEROIC = [
    "Chiến công ấy khắc sâu vào ký ức lịch sử và hun đúc ý chí quật cường của dân tộc.",
    "Từ thắng lợi này, niềm tin độc lập lan tỏa qua nhiều thế hệ."
]

ENDING_FATE = [
    "Sự kiện ấy đặt nền móng lâu dài cho trật tự quốc gia và con đường phát triển sau này.",
    "Từ dấu mốc ấy, lịch sử lặng lẽ sang trang."
]

# ================= UTILS =================

def extract_year(text):
    m = YEAR_AT_START.search(text) or YEAR_INLINE.search(text)
    return m.group(1) if m else None


def clean_text(text):
    text = re.sub(r"\s+", " ", text.strip())
    if len(text) < 60:
        return None

    lower = text.lower()
    for kw in FORBIDDEN_KEYWORDS:
        if kw in lower:
            return None

    text = re.sub(r"\(.*?\)", "", text)
    text = re.sub(r"`|\*", "", text)
    return text.strip()


def classify_event(text):
    t = text.lower()
    if any(h in t for h in TRAGIC_HINTS):
        return "tragic"
    if any(h in t for h in HEROIC_HINTS):
        return "heroic"
    return "fate"


def normalize_sentence(s, force_cap=False):
    s = s.strip(" ,;-")
    if not s:
        return None

    # hạ hoa sau dấu phẩy nếu là mệnh đề
    s = re.sub(
        r",\s+([A-ZĐ])",
        lambda m: ", " + m.group(1).lower(),
        s
    )

    s = re.sub(
        r"^(kể từ thời điểm ấy,\s*)?(về lâu dài,\s*)([A-ZĐ])",
        lambda m: (m.group(1) or "") + m.group(2) + m.group(3).lower(),
        s,
        flags=re.I
    )
    
    if force_cap:
        return s[0].upper() + s[1:]

    return s


def smart_split(text):
    parts = re.split(r"[.;]\s*", text)
    results = []

    for i, p in enumerate(parts):
        p = normalize_sentence(p, force_cap=(i == 0))
        if p and len(p) > 25:
            results.append(p)

    return results


def storyteller(year, text):
    sentences = smart_split(text)
    if not sentences:
        return None

    opening = f"Trong bối cảnh năm {year}, {sentences[0]}."

    body = ""
    if len(sentences) > 1:
        body = f" Kể từ thời điểm ấy, {sentences[1]}."

    # giữ câu đánh giá cũ, không ép ending
    tail = ""
    if len(sentences) > 2:
        tail = f" {sentences[2]}."

    return opening + body + tail

def normalize_event(text):
    text = clean_text(text)
    if not text:
        return None

    year = extract_year(text)
    if not year:
        return None

    text = re.sub(rf"\b(năm\s*)?{year}\b", "", text, flags=re.I)
    text = re.sub(r"\b(diễn ra|xảy ra|đánh dấu)\b", "", text, flags=re.I)

    return storyteller(year, text)


def iter_raw(dataset):
    for row in dataset:
        msgs = row.get("messages")
        if not isinstance(msgs, list):
            continue
        for m in msgs:
            if m.get("role") == "assistant":
                yield m.get("content", "")


def main():
    print("[INFO] Loading dataset...")
    ds = load_dataset("arrow", data_files=ARROW_FILES, split="train")

    stories = {}

    for line in iter_raw(ds):
        story = normalize_event(line)
        if not story:
            continue

        y = re.search(r"\b(1[0-9]{3})\b", story)
        if not y:
            continue

        year = y.group(1)
        if year not in stories or len(story) > len(stories[year]):
            stories[year] = story

    results = sorted(stories.values())

    Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    Path(OUT_PATH).write_text("\n".join(results), encoding="utf-8")

    print(f"[DONE] Sinh {len(results)} truyện lịch sử – STORYTELLER LEVEL CUỐI")


if __name__ == "__main__":
    main()
