"""
enrich_meta.py — Add semantic metadata fields to meta.json

Adds three fields to each document:
  - conflict_type: "external_conflict" | "civil_war" | "colonial_aggression" | null
  - scope: "national" | "territorial" | null
  - is_resistance: true | false

Classification rules are based on historical analysis of each event.
"""
import json
import os

META_PATH = os.path.join(os.path.dirname(__file__), "..", "faiss_index", "meta.json")

# --- CLASSIFICATION RULES ---

# Events that are NATIONAL RESISTANCE against foreign invaders
EXTERNAL_RESISTANCE_IDS = {
    # Bạch Đằng 938 — Ngô Quyền vs Nam Hán → end of 1000 years Bắc thuộc
    "hf_000281",
    # Dương Đình Nghệ vs Nam Hán 931
    "hf_000099",
    # Kháng Tống 981 — Lê Hoàn
    "hf_000074",
    # Lý Thường Kiệt vs Tống 1075
    "hf_000081",
    # Phòng tuyến Như Nguyệt 1077
    "hf_000004",
    # Kháng chiến lần 1 chống Mông Cổ 1258
    "hf_000180",
    # Hịch tướng sĩ 1284 (military mobilization vs Mongol)
    "hf_000003",
    # Kháng chiến lần 2 chống Nguyên 1285
    "hf_000620",
    # Trận Bạch Đằng 1288 — Trần Hưng Đạo vs Nguyên
    "hf_000349",
    # Khởi nghĩa Lam Sơn 1418 — Lê Lợi vs Minh
    "hf_000041",
    # Toàn thắng chống Minh 1427
    "hf_000245",
    # Rạch Gầm – Xoài Mút 1785 — Nguyễn Huệ vs Xiêm
    "hf_000259",
    # Ngọc Hồi – Đống Đa 1789 — Quang Trung vs Thanh
    "hf_000126",
    # Phong trào Cần Vương 1885 — chống Pháp
    "hf_000173",
    # Khởi nghĩa Yên Bái 1930 — chống Pháp
    "hf_000207",
    # Toàn quốc kháng chiến 1946
    "hf_000091",
    # Chiến thắng Điện Biên Phủ 1954
    "hf_000059",
    # Chiến dịch 'Điện Biên Phủ trên không' 1972
    "hf_000013",
    # Chiến dịch Hồ Chí Minh 1975
    "hf_000028",
    # Chiến tranh biên giới phía Bắc 1979
    "hf_000121",
}

# Events that are CIVIL WARS (internal conflicts)
CIVIL_WAR_IDS = {
    # Trịnh–Nguyễn phân tranh 1627
    "hf_000078",
    # Tạm đình chiến Trịnh–Nguyễn 1672
    "hf_000061",
    # Duplicate Trịnh–Nguyễn (year=150, data error)
    "hf_000512",
}

# Events that are COLONIAL AGGRESSION (foreign powers attacking/colonizing)
COLONIAL_AGGRESSION_IDS = {
    # Pháp – Tây Ban Nha tấn công Đà Nẵng 1858
    "hf_000011",
    # Hòa ước Nhâm Tuất 1862
    "hf_000215",
    # Pháp chiếm Nam Kỳ 1867
    "hf_000225",
    # Hòa ước Patenôtre 1884
    "hf_000000",
    # Nhà Minh xâm lược 1407
    "hf_000358",
    # Sự kiện Vịnh Bắc Bộ 1964 (Mỹ leo thang)
    "hf_000064",
    # Việt Nam đưa quân vào Campuchia 1978
    "hf_000005",
}

# Political/founding events (national scope but not resistance)
NATIONAL_SCOPE_IDS = {
    # Khúc Thừa Dụ tự chủ 905
    "hf_000022",
    # Ngô Quyền xưng vương 939
    "hf_000272",
    # Đinh Bộ Lĩnh lập Đại Cồ Việt 968
    "hf_000038",
    # Lê Hoàn lên ngôi 980
    "hf_000017",
    # Lý Công Uẩn lên ngôi 1009
    "hf_000331",
    # Chiếu dời đô 1010 (both entries)
    "hf_000031", "hf_000155",
    # Đổi quốc hiệu Đại Việt 1054
    "hf_000089",
    # Nhà Trần thành lập 1225
    "hf_000178",
    # Hồ Quý Ly lập nhà Hồ 1400
    "hf_000006",
    # Lê Lợi lên ngôi 1428
    "hf_000469",
    # Lê Thánh Tông trị vì 1460
    "hf_000039",
    # Bộ luật Hồng Đức 1483
    "hf_000157",
    # Mạc Đăng Dung lập nhà Mạc 1527
    "hf_000135",
    # Lê trung hưng 1533
    "hf_000086",
    # Khởi nghĩa Tây Sơn 1771
    "hf_000156",
    # Nguyễn Ánh lập nhà Nguyễn 1802
    "hf_000105",
    # Đổi quốc hiệu Đại Nam 1839
    "hf_000206",
    # Phong trào Đông Du 1905
    "hf_000290",
    # Nguyễn Tất Thành ra đi 1911
    "hf_000146",
    # Thành lập ĐCS VN 1930
    "hf_000115",
    # Việt Minh ra đời 1941
    "hf_000487",
    # Cách mạng Tháng Tám 1945
    "hf_000009",
    # Hiệp định Genève 1954
    "hf_000068",
    # VNCH 1955
    "hf_000102",
    # Mặt trận DTGP miền Nam 1960
    "hf_000045",
    # Tết Mậu Thân 1968
    "hf_000148",
    # Hiệp định Paris 1973
    "hf_000021",
    # Nước CHXHCN VN 1976
    "hf_000350",
    # Đổi Mới 1986
    "hf_000149",
    # Rút quân khỏi Campuchia 1989
    "hf_000070",
    # Hiến pháp 1992
    "hf_000098",
    # Bình thường hóa Việt–Mỹ 1995
    "hf_000058",
    # Đại Việt đánh Champa 1471
    "hf_000027",
}


def enrich():
    with open(META_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    for doc in data["documents"]:
        doc_id = doc["id"]

        if doc_id in EXTERNAL_RESISTANCE_IDS:
            doc["conflict_type"] = "external_conflict"
            doc["scope"] = "national"
            doc["is_resistance"] = True
        elif doc_id in CIVIL_WAR_IDS:
            doc["conflict_type"] = "civil_war"
            doc["scope"] = "national"
            doc["is_resistance"] = False
        elif doc_id in COLONIAL_AGGRESSION_IDS:
            doc["conflict_type"] = "colonial_aggression"
            doc["scope"] = "national"
            doc["is_resistance"] = False
        elif doc_id in NATIONAL_SCOPE_IDS:
            doc["conflict_type"] = None
            doc["scope"] = "national"
            doc["is_resistance"] = False
        else:
            # Non-conflict events (cultural, economic, etc.)
            doc["conflict_type"] = None
            doc["scope"] = None
            doc["is_resistance"] = False

    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # Print summary
    counts = {"external_conflict": 0, "civil_war": 0, "colonial_aggression": 0, "national": 0, "resistance": 0}
    for doc in data["documents"]:
        ct = doc.get("conflict_type")
        if ct:
            counts[ct] = counts.get(ct, 0) + 1
        if doc.get("scope") == "national":
            counts["national"] += 1
        if doc.get("is_resistance"):
            counts["resistance"] += 1

    print(f"Total documents: {len(data['documents'])}")
    print(f"External conflicts: {counts['external_conflict']}")
    print(f"Civil wars: {counts['civil_war']}")
    print(f"Colonial aggression: {counts['colonial_aggression']}")
    print(f"National scope: {counts['national']}")
    print(f"Resistance events: {counts['resistance']}")


if __name__ == "__main__":
    enrich()
