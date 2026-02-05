import re
import unicodedata

def normalize_query(query: str) -> str:
    q = query.lower()
    q = unicodedata.normalize("NFD", q)
    q = "".join(c for c in q if unicodedata.category(c) != "Mn")
    q = re.sub(r"\s+", " ", q).strip()
    return q

def normalize(text: str) -> str:
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn")
