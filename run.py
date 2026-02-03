import sys
sys.stdout.reconfigure(encoding="utf-8")

import re
from pathlib import Path

# ================== CONFIG ==================
RAW_PATH = "data/history_docs.txt"
OUT_PATH = "data/history_docs_clean.txt"

# năm ở đầu câu (ưu tiên tuyệt đối)
YEAR_AT_START = re.compile(
    r"^(?:Năm\s*)?([1-9][0-9]{2,3})(?:\s*[:,-])",
    flags=re.I
)

# fallback – cực hạn chế
YEAR_GENERAL = re.compile(r"\b([1-9][0-9]{2,3})\b")

FORBIDDEN_KEYWORDS = [
    "câu hỏi", "hãy cho biết", "trình bày",
    "vì sao", "ai là", "kể tên",
    "readme", "dataset", "json", "train", "config"
]
# ============================================


def extract_year(text: str):
    """
    Chỉ lấy NĂM SỰ KIỆN.
    TUYỆT ĐỐI loại:
    - 1000 năm / 2000 năm
    - kỷ niệm XXX năm
    """

    text_lower = text.lower()

    # ❌ chặn sớm dòng kỷ niệm
    if "kỷ niệm" in text_lower:
        return None

    # 1️⃣ năm ở đầu câu
    m = YEAR_AT_START.search(text)
    if m:
        return m.group(1)

    # 2️⃣ "năm XXXX"
    m = re.search(r"\bnăm\s+([1-9][0-9]{2,3})\b", text, flags=re.I)
    if m:
        return m.group(1)

    # 3️⃣ fallback – rất hạn chế
    for m in YEAR_GENERAL.finditer(text):
        year = m.group(1)
        start = m.start()

        # ❌ "1000 năm", "1000 năm Thăng Long"
        if re.match(rf"{year}\s*năm", text[start:start + 12], flags=re.I):
            continue

        if re.search(rf"{year}\s*năm", text_lower):
            continue

        return year

    return None


def normalize_event(text: str):
    # ================== BASIC CLEAN ==================
    text = re.sub(r"\s+", " ", text.strip())

    if len(text) < 40:
        return None

    lower = text.lower()

    for kw in FORBIDDEN_KEYWORDS:
        if kw in lower:
            return None

    # bỏ markdown + chú thích
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"`(.*?)`", r"\1", text)
    text = re.sub(r"\(.*?\)", "", text)

    # ================== YEAR ==================
    year = extract_year(text)
    if not year:
        return None

    text = re.sub(rf"^Năm\s+{year}[,:]?\s*", "", text, flags=re.I)
    text = re.sub(rf"xảy ra năm\s*{year}", "", text, flags=re.I)

    # ================== ENTITY NORMALIZE ==================
    text = re.sub(
        r"\b(Nguyễn Tất Thành|Hồ Chí Minh)\b",
        "Bác Hồ",
        text,
        flags=re.I
    )

    text = re.sub(r"(Bác Hồ)(.*?)(Bác Hồ)", r"\1\2", text)

    # ================== POLISH NGỮ NGHĨA ==================
    text = re.sub(r"\.\s*rời bến", ", Bác rời bến", text, flags=re.I)
    text = re.sub(r"\.\s*bắt đầu", " và bắt đầu", text, flags=re.I)

    # xoá AI-mùi
    text = re.sub(
        r"Đây là cột mốc quan trọng vì\s*",
        "",
        text,
        flags=re.I
    )

    # đảm bảo có space sau dấu chấm nếu là chữ hoa
    text = re.sub(r"\.(?=[A-ZĐ])", ". ", text)

    # hạ chữ hoa sau "Về lâu dài,"
    text = re.sub(
        r"(Về lâu dài,\s*)([A-ZĐ])",
        lambda m: m.group(1) + m.group(2).lower(),
        text
    )

    text = re.sub(r"của Bác Hồ\b", "của Bác", text)

    # ================== FINAL CLEAN (ANTI '..') ==================
    text = text.strip()

    # gom nhiều dấu chấm liên tiếp → 1 dấu chấm
    text = re.sub(r"\.{2,}", ".", text)

    # xoá dấu chấm cuối (để format lại)
    text = text.rstrip(".")

    return f"Năm {year}, {text}."


def main():
    src = Path(RAW_PATH)
    dst = Path(OUT_PATH)

    raw_results = []

    with src.open(encoding="utf-8") as f:
        for line in f:
            ev = normalize_event(line)
            if ev:
                raw_results.append(ev)

    # ===== DEDUP + ƯU TIÊN BẢN CHUẨN =====
    unique = {}

    for r in raw_results:
        year_key = r.split(",")[0]  # "Năm XXXX"

        score = 2 if "Về lâu dài" in r else 1

        if year_key not in unique or score > unique[year_key][0]:
            unique[year_key] = (score, r)

    results = sorted(v[1] for v in unique.values())

    dst.write_text("\n".join(results), encoding="utf-8")

    print(f"[DONE] Chuẩn hoá {len(results)} sự kiện lịch sử (CANONICAL DATASET)")


if __name__ == "__main__":
    main()
