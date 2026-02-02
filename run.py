import sys
sys.stdout.reconfigure(encoding="utf-8")

import re
from pathlib import Path

# ================== CONFIG ==================
RAW_PATH = "data/history_docs.txt"
OUT_PATH = "data/history_docs_clean.txt"

YEAR_PATTERN = re.compile(r"\b(1[0-9]{3})\b")

FORBIDDEN_KEYWORDS = [
    "câu hỏi", "hãy cho biết", "trình bày",
    "vì sao", "ai là", "kể tên"
]
# ============================================

def normalize_event(text: str):
    # chuẩn hoá khoảng trắng
    text = re.sub(r"\s+", " ", text.strip())
    lower = text.lower()

    # quá ngắn → loại
    if len(text) < 30:
        return None

    # câu hỏi / meta → loại
    for kw in FORBIDDEN_KEYWORDS:
        if kw in lower:
            return None

    # ❌ CHẶN TUYỆT ĐỐI "năm 1000"
    if "năm 1000" in lower:
        return None

    # ⭐ CASE ĐẶC BIỆT: 1000 năm Thăng Long → 2010
    if "1000 năm" in lower and "thăng long" in lower:
        year = "2010"
    else:
        m = YEAR_PATTERN.search(text)
        if not m:
            return None
        year = m.group(1)

    # ❌ bỏ "Năm XXXX" nếu đã tồn tại
    clean = re.sub(r"^Năm\s+\d{4},?\s*", "", text, flags=re.I)

    # ❌ bỏ ngoặc
    clean = re.sub(r"\(.*?\)", "", clean)

    clean = clean.strip().rstrip(".")

    return f"Năm {year}, {clean}."

def main():
    src = Path(RAW_PATH)
    dst = Path(OUT_PATH)

    results = []

    with src.open(encoding="utf-8") as f:
        for line in f:
            ev = normalize_event(line)
            if ev:
                results.append(ev)

    # ❗ deduplicate + sort
    results = sorted(set(results))

    dst.write_text("\n".join(results), encoding="utf-8")

    print(f"[DONE] Chuẩn hoá {len(results)} sự kiện lịch sử (CANONICAL)")

if __name__ == "__main__":
    main()
