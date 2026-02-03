import sys
sys.stdout.reconfigure(encoding="utf-8")

import re
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

OUT_PATH = "data/history_docs_clean.txt"
# ============================================

# ====== CANONICAL RULES (RAW) ======
YEAR_AT_START = re.compile(
    r"^Năm\s+([1-9][0-9]{2,3})[,:]\s*",
    flags=re.I
)

YEAR_INLINE = re.compile(r"\bnăm\s+([1-9][0-9]{2,3})\b", flags=re.I)

FORBIDDEN_KEYWORDS = [
    "câu hỏi", "hãy cho biết", "trình bày",
    "vì sao", "ai là", "kể tên",
    "readme", "dataset", "json",
    "train", "config", "assistant", "user"
]
# ==================================


def extract_year(text: str):
    """
    Ưu tiên năm ở đầu dòng → giống file raw
    """
    if "kỷ niệm" in text.lower():
        return None

    m = YEAR_AT_START.search(text)
    if m:
        return m.group(1)

    m = YEAR_INLINE.search(text)
    if m:
        return m.group(1)

    return None


def normalize_event(text: str):
    # ===== BASIC CLEAN =====
    text = re.sub(r"\s+", " ", text.strip())

    if len(text) < 50:
        return None

    lower = text.lower()
    for kw in FORBIDDEN_KEYWORDS:
        if kw in lower:
            return None

    # bỏ markdown / noise
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"`(.*?)`", r"\1", text)
    text = re.sub(r"\(.*?\)", "", text)

    # ===== YEAR =====
    year = extract_year(text)
    if not year:
        return None

    # bỏ năm đầu
    text = re.sub(rf"^Năm\s+{year}[,:]?\s*", "", text, flags=re.I)
    text = re.sub(rf"(diễn ra|xảy ra)\s+năm\s*{year}", "", text, flags=re.I)

    # ===== ENTITY =====
    text = re.sub(
        r"\b(Nguyễn Tất Thành|Hồ Chí Minh)\b",
        "Bác Hồ",
        text,
        flags=re.I
    )

    # ===== RAW SENTENCE LOGIC (GIỐNG DOC CŨ) =====

    # "Tiêu đề . Nội dung" → giữ nguyên dấu chấm
    text = re.sub(
        r"^([A-ZĐ][^.,]{3,40})\s*:\s*",
        r"\1. ",
        text
    )

    # ". Sau khi" → ". Sau khi" (KHÔNG đổi thành dấu phẩy)
    text = re.sub(r"\.\s+(Sau khi|Sau đó)", r". \1", text)

    # ghép kiểu raw: ", Bác rời bến"
    text = re.sub(r"\.\s*Bác Hồ rời", ", Bác rời", text)

    # ===== POLISH =====

    # hạ chữ hoa sau "Về lâu dài,"
    text = re.sub(
        r"(Về lâu dài,\s*)([A-ZĐ])",
        lambda m: m.group(1) + m.group(2).lower(),
        text
    )

    # xoá space trước dấu
    text = re.sub(r"\s+([.,;])", r"\1", text)

    # đảm bảo space sau dấu chấm
    text = re.sub(r"\.(?=[A-ZĐ])", ". ", text)

    text = re.sub(r"\.{2,}", ".", text)
    text = text.rstrip(".")

    return f"Năm {year}, {text}."

def iter_raw_like_lines(dataset):
    """
    Arrow → từng dòng text giống file raw
    """
    for row in dataset:
        msgs = row.get("messages")
        if not isinstance(msgs, list):
            continue

        for m in msgs:
            if (
                isinstance(m, dict)
                and m.get("role") == "assistant"
                and isinstance(m.get("content"), str)
            ):
                yield m["content"]


def main():
    print("[INFO] Loading Arrow files...")

    ds = load_dataset(
        "arrow",
        data_files=ARROW_FILES,
        split="train"
    )

    collected = []

    for line in iter_raw_like_lines(ds):
        ev = normalize_event(line)
        if ev:
            collected.append(ev)

    # ===== DEDUP: 1 NĂM / 1 SỰ KIỆN =====
    best = {}

    for ev in collected:
        year = ev.split(",")[0]
        score = 2 if "Về lâu dài" in ev else 1

        if year not in best or score > best[year][0]:
            best[year] = (score, ev)

    results = sorted(v[1] for v in best.values())

    Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    Path(OUT_PATH).write_text("\n".join(results), encoding="utf-8")

    print(f"[DONE] Chuẩn hoá {len(results)} sự kiện lịch sử (RAW LOGIC)")


if __name__ == "__main__":
    main()
