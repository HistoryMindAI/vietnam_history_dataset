from app.utils.normalize import normalize_query, normalize

ENTITY_ALIASES = {
    "quang_trung": ["quang trung", "nguyen hue"],
    "ho_chi_minh": ["ho chi minh", "nguyen tat thanh"]
}

ENTITY_ALIASES_NORM = {
    k: [normalize(a) for a in v]
    for k, v in ENTITY_ALIASES.items()
}

def extract_entities(query: str):
    q = normalize_query(query)
    found = set()
    for key, aliases in ENTITY_ALIASES.items():
        for a in aliases:
            if a in q:
                found.add(key)
    return found
