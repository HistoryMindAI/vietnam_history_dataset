import sys
sys.stdout.reconfigure(encoding="utf-8")

import re
from pathlib import Path

# ================== CONFIG ==================
RAW_PATH = "data/history_docs.txt"
OUT_PATH = "data/history_docs_clean.txt"

# hỗ trợ năm < 1000 (938, 968…) đến hiện đại
YEAR_PATTERN = re.compile(r"\b([1-9][0-9]{2,3})\b")

FORBIDDEN_KEYWORDS = [
    "câu hỏi", "hãy cho biết", "trình bày",
    "vì sao", "ai là", "kể tên",
    "readme", "dataset", "json", "train", "config"
]
# ============================================


def normalize_event(text: str):
    # chuẩn hoá khoảng trắng
    text = re.sub(r"\s+", " ", text.strip())

    if len(text) < 40:
        return None

    lower = text.lower()

    # ❌ loại câu hỏi / meta
    for kw in FORBIDDEN_KEYWORDS:
        if kw in lower:
            return None

    # ❌ bỏ markdown
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"`(.*?)`", r"\1", text)

    # ❌ bỏ ngoặc chú thích
    text = re.sub(r"\(.*?\)", "", text)

    # ⭐ lấy năm
    m = YEAR_PATTERN.search(text)
    if not m:
        return None
    year = m.group(1)

    # ❌ bỏ "Năm XXXX" trùng
    text = re.sub(rf"^Năm\s+{year},?\s*", "", text, flags=re.I)

    # ❌ bỏ "xảy ra năm XXXX"
    text = re.sub(rf"xảy ra năm\s*{year}", "", text, flags=re.I)

    # ⭐ chuẩn hoá tên Hồ Chí Minh
    text = re.sub(
        r"\b(Nguyễn Tất Thành|Hồ Chí Minh)\b",
        "Bác Hồ",
        text,
        flags=re.I
    )

    # ❌ lặp tên liên tục → giữ 1 lần
    text = re.sub(r"(Bác Hồ)(.*?)(Bác Hồ)", r"\1\2", text)

    # chuẩn dấu câu
    text = text.strip().rstrip(".")
    text = re.sub(r"\s+\.", ".", text)

    return f"Năm {year}, {text}."


def main():
    src = Path(RAW_PATH)
    dst = Path(OUT_PATH)

    results = []

    with src.open(encoding="utf-8") as f:
        for line in f:
            ev = normalize_event(line)
            if ev:
                results.append(ev)

    # deduplicate + sort
    results = sorted(set(results))

    dst.write_text("\n".join(results), encoding="utf-8")

    print(f"[DONE] Chuẩn hoá {len(results)} sự kiện lịch sử (CANONICAL DATASET)")


if __name__ == "__main__":
    main()
