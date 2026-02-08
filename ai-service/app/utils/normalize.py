import re
import unicodedata

def remove_accents(input_str: str) -> str:
    s = unicodedata.normalize("NFD", input_str)
    return "".join(c for c in s if unicodedata.category(c) != "Mn")

def normalize_query(query: str) -> str:
    """
    Normalizes query for semantic search.
    - Lowercases.
    - Trims whitespace.
    - Normalizes unicode (NFC preferred for consistency in Python strings).
    """
    q = query.lower()
    q = unicodedata.normalize("NFC", q)
    q = re.sub(r"\s+", " ", q).strip()
    return q

def normalize(text: str) -> str:
    """
    Legacy normalization (removes accents).
    Used for entity matching where aliases are unaccented.
    """
    text = text.lower()
    return remove_accents(text)
