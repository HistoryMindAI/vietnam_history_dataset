import os
import sys
import re
import json
import datasets

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

YEAR = r"(1[0-9]{3})"

EVENT_YEAR_PATTERN = re.compile(
    rf"(diễn ra|được tổ chức|tổ chức|vào năm)\s*{YEAR}",
    re.IGNORECASE
)

DURATION_PATTERN = re.compile(r"(\d{2,4})\s*năm")

REFERENCE_YEAR_PATTERN = re.compile(r"từ năm\s*(1[0-9]{3})", re.IGNORECASE)

ANNIVERSARY_KEYWORDS = [
    "đại lễ", "kỷ niệm", "thành lập", "ngày thành lập"
]

def classify_event(text: str):
    t = text.lower()
    if any(k in t for k in ANNIVERSARY_KEYWORDS):
        return "anniversary"
    if "chiến tranh" in t or "khởi nghĩa" in t:
        return "war"
    if "triều" in t or "vua" in t:
        return "dynasty"
    return "general"

def normalize_event(text: str):
    text = re.sub(r"\s+", " ", text.strip())
    if len(text) < 30:
        return None

    event_type = classify_event(text)

    event_year = None
    reference_year = None
    duration_years = None

    # 1️⃣ event_year
    m = EVENT_YEAR_PATTERN.search(text)
    if m:
        event_year = int(m.group(2))
    else:
        y = re.search(YEAR, text)
        if y:
            event_year = int(y.group(1))

    if not event_year:
        return None

    # 2️⃣ duration
    d = DURATION_PATTERN.search(text)
    if d:
        duration_years = int(d.group(1))

    # 3️⃣ reference_year (nếu là kỷ niệm)
    if event_type == "anniversary" and duration_years:
        reference_year = event_year - duration_years

    final_text = f"Năm {event_year}, {text}"
    if "." in final_text:
        final_text = final_text.split(".")[0] + "."

    return {
        "event_year": event_year,
        "reference_year": reference_year,
        "duration_years": duration_years,
        "event_type": event_type,
        "text": final_text
    }

# ===================== BUILD DATASET =====================
def prepare_data():
    ds = datasets.load_dataset("vietnam_history_dataset", split="train")
    os.makedirs("data", exist_ok=True)

    out_jsonl = open("data/history_structured.jsonl", "w", encoding="utf-8")
    out_txt = open("data/history_docs.txt", "w", encoding="utf-8")

    seen = set()
    count = 0

    for item in ds:
        for msg in item.get("messages", []):
            content = msg.get("content")
            if not isinstance(content, str):
                continue

            event = normalize_event(content)
            if not event:
                continue

            key = event["text"]
            if key in seen:
                continue
            seen.add(key)

            out_jsonl.write(json.dumps(event, ensure_ascii=False) + "\n")
            out_txt.write(event["text"] + "\n")

            count += 1
            if count >= 3000:
                break
        if count >= 3000:
            break

    out_jsonl.close()
    out_txt.close()
    print(f"[DONE] Chuẩn hoá {count} sự kiện lịch sử (V3)")

if __name__ == "__main__":
    prepare_data()
