import json
import re
from pipeline.storyteller import (
    classify_entity,
    is_valid_person,
    canonical_person,
    extract_all_persons,
    extract_all_places,
    infer_subject,
    extract_year,
    classify_nature
)

INPUT_FILE = "data/history_structured.jsonl"
OUTPUT_FILE = "data/history_cleaned.jsonl"

def clean_content(text):
    if not text:
        return ""

    # 1. Remove "B1:", "B2:", bullets
    text = re.sub(r"\b[bB]\d+:\s*", "", text)
    text = re.sub(r"^\s*[-*•]\s*", "", text)

    # 2. Remove zero-width spaces
    text = text.replace("\u200b", "")

    # 3. Remove markdown bold (after title extraction, handled separately)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)

    # 4. Remove leading "Năm XXXX," if redundant (optional, but keep for now as context)

    return text.strip()

def extract_title_from_text(text):
    # Try to find bold text **...**
    match = re.search(r"\*\*(.*?)\*\*", text)
    if match:
        return match.group(1).strip()

    # Fallback: Use cleaned text logic
    # First remove garbage B1:, B2: etc
    clean = re.sub(r"\b[bB]\d+:\s*", "", text)
    clean = re.sub(r"^\s*[-*•]\s*", "", clean)
    clean = re.sub(r"\*\*", "", clean)

    parts = clean.split(",")
    if len(parts) > 0:
        candidate = parts[0].strip()
        # If "Năm XXXX", take the next part
        if re.match(r"^(?:Năm|Vào năm)\s+\d+", candidate, re.I):
            if len(parts) > 1:
                return parts[1].strip()
            elif len(candidate) > 15: # "Năm 1284, Hịch tướng sĩ" -> "Năm 1284" is bad if it's the only part
                 return candidate

    # Last resort: first 50 chars of cleaned text
    return clean[:50].strip() + "..."

def determine_subject_type(text, year):
    # 1. Check for Person
    persons = extract_all_persons(text)
    valid_persons = [p for p in persons if is_valid_person(p)]
    if valid_persons:
        return "PERSON", valid_persons[0]

    # 2. Check for Document (Check BEFORE Place/Event as documents are specific)
    doc_keywords = [
        "Hiến pháp", "Luật", "Chiếu", "Hòa ước", "Hiệp định", "Tuyên ngôn",
        "Sắc lệnh", "Hịch", "Bình Ngô đại cáo", "Tác phẩm", "Sách", "Thơ", "Văn kiện"
    ]
    if any(k in text for k in doc_keywords):
        return "DOCUMENT", "Văn kiện"

    # 3. Check for Place
    places = extract_all_places(text)
    if places:
        # Heuristic: if place is dominant
        return "LOCATION", list(places)[0]

    # 4. Check for Collective
    if "nhà" in text.lower() or "triều" in text.lower() or "quân" in text.lower():
         return "COLLECTIVE", "Tập thể"

    return "EVENT", "Sự kiện"

def main():
    print(f"Reading from {INPUT_FILE}...")

    with open(INPUT_FILE, "r", encoding="utf-8") as fin, \
         open(OUTPUT_FILE, "w", encoding="utf-8") as fout:

        counters = {} # To track ID counts per year/type

        for line_num, line in enumerate(fin):
            line = line.strip()
            if not line:
                continue

            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                print(f"Skipping invalid JSON on line {line_num}")
                continue

            raw_text = raw.get("text", "")
            raw_year = raw.get("event_year")

            # --- CLEANING ---

            # 1. Year
            if raw_year:
                try:
                    year = int(raw_year)
                except ValueError:
                    # Try extracting from text if year is invalid in field
                    y_str = extract_year(raw_text)
                    year = int(y_str) if y_str else 0
            else:
                y_str = extract_year(raw_text)
                year = int(y_str) if y_str else 0

            if year == 0:
                # Skip records without valid year? Or keep with 0?
                # User said: "year: null -> Fix standard"
                # Let's try to extract from text one last time strictly
                pass

            # 2. Title
            title = extract_title_from_text(raw_text)

            # 3. Content
            content = clean_content(raw_text)
            if len(content) < 20: # Skip short content
                continue

            # 4. Subject Type
            subj_type, subj_name = determine_subject_type(content, year)

            # 5. ID Generation
            # Format: hm_{TYPE}_{YEAR}_{COUNTER}
            # key for counter
            key = f"{subj_type}_{year}"
            count = counters.get(key, 0) + 1
            counters[key] = count

            doc_id = f"hm_{subj_type}_{year}_{count:02d}"

            # 6. Construct new record
            record = {
                "id": doc_id,
                "subject_type": subj_type,
                "year": year,
                "title": title,
                "content": content,
                "tags": [], # TODO: Extract tags?
                "meta": {
                    "original_text": raw_text
                }
            }

            # Add nature/tone from storyteller logic
            nature = classify_nature(content)
            record["nature"] = list(nature)

            fout.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"Cleaning complete. Output written to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
