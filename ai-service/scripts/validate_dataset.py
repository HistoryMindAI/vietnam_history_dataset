"""
validate_dataset.py - Automated validation for the history dataset.
Reports data quality issues including entity, dynasty, text, and keyword problems.
"""
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
META_PATH = SCRIPT_DIR.parent / "faiss_index" / "meta.json"

# Known false positive person names
FALSE_PERSON_KEYWORDS = [
    "việt nam", "giáp thân", "buộc mỹ", "paris hiệp", "nước cộng",
    "tháng tám", "dân chủ", "xã hội", "mông cổ", "chủ nghĩa",
    "cộng hòa", "mặt trận", "việt minh", "đông du", "cần vương",
    "minh thuộc", "bắc thuộc", "đổi mới", "toàn quốc", "đại việt",
    "đại nam", "nhâm tuất", "canh tuất", "campuchia", "trung quốc",
]

FALSE_PLACE_KEYWORDS = ["tháng tám", "dân", "mỹ", "pháp", "quân", "cộng sản"]


def validate():
    """Run full validation and print report."""
    with open(META_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    docs = data["documents"]
    print(f"Dataset Validation Report")
    print(f"   Total documents: {len(docs)}")
    print(f"   Model: {data.get('model', 'unknown')}")
    print(f"   Dimension: {data.get('dimension', 0)}")
    print()

    issues = {
        "bad_persons": [],
        "bad_places": [],
        "bad_dynasty": [],
        "title_eq_event": 0,
        "empty_keywords": 0,
        "text_dup_year": [],
        "text_xay_ra": [],
        "short_story": [],
    }

    for d in docs:
        doc_id = d.get("id", "?")
        year = d.get("year", 0)

        # Check persons
        for p in d.get("persons", []):
            p_low = p.lower()
            if any(fp in p_low for fp in FALSE_PERSON_KEYWORDS) or len(p) < 4:
                issues["bad_persons"].append((doc_id, p))

        # Check places
        for p in d.get("places", []):
            if p.lower() in FALSE_PLACE_KEYWORDS:
                issues["bad_places"].append((doc_id, p))

        # Check dynasty for modern events
        dynasty = d.get("dynasty", "")
        if year >= 1945 and dynasty not in ["Hiện đại", "Modern", "", "Unknown"]:
            issues["bad_dynasty"].append((doc_id, year, dynasty))

        # Check title == event
        if d.get("title", "") == d.get("event", ""):
            issues["title_eq_event"] += 1

        # Check empty keywords
        if not d.get("keywords"):
            issues["empty_keywords"] += 1

        # Check text quality
        story = d.get("story", "")
        if "xảy ra năm" in story or "diễn ra năm" in story:
            issues["text_xay_ra"].append((doc_id, story[:80]))
        yr_str = str(year)
        if f"Năm {yr_str}, Năm {yr_str}" in story:
            issues["text_dup_year"].append((doc_id, story[:80]))
        if len(story) < 20 and story:
            issues["short_story"].append((doc_id, story))

    # Print results
    total_issues = 0

    print("CRITICAL ISSUES")
    print(f"   Bad persons: {len(issues['bad_persons'])}")
    for bp in issues["bad_persons"][:10]:
        print(f"     X {bp[0]}: '{bp[1]}'")
    total_issues += len(issues["bad_persons"])

    print(f"   Bad dynasty: {len(issues['bad_dynasty'])}")
    for bd in issues["bad_dynasty"][:10]:
        print(f"     X {bd[0]}: year={bd[1]}, dynasty='{bd[2]}'")
    total_issues += len(issues["bad_dynasty"])

    print()
    print("MEDIUM ISSUES")
    print(f"   Title == Event: {issues['title_eq_event']}")
    print(f"   Text with xay ra/dien ra nam: {len(issues['text_xay_ra'])}")
    for tx in issues["text_xay_ra"][:5]:
        print(f"     ! {tx[0]}: '{tx[1]}...'")
    print(f"   Text with duplicate year: {len(issues['text_dup_year'])}")
    total_issues += issues["title_eq_event"] + len(issues["text_xay_ra"]) + len(issues["text_dup_year"])

    print()
    print("MINOR ISSUES")
    print(f"   Bad places: {len(issues['bad_places'])}")
    print(f"   Empty keywords: {issues['empty_keywords']}")
    print(f"   Short stories (<20 chars): {len(issues['short_story'])}")
    total_issues += len(issues["bad_places"]) + issues["empty_keywords"] + len(issues["short_story"])

    print()
    print("=" * 50)
    print(f"TOTAL ISSUES: {total_issues}")
    if total_issues == 0:
        print("PASS - Dataset is CLEAN!")
    elif total_issues < 5:
        print("WARN - Minor issues found, mostly acceptable.")
    else:
        print("FAIL - Significant issues found, needs fixing.")

    return total_issues


if __name__ == "__main__":
    issues = validate()
    sys.exit(1 if issues > 5 else 0)
