import json
import faiss
from sentence_transformers import SentenceTransformer
from app.core.config import *

print("[STARTUP] Loading embedding model & FAISS...")

embedder = SentenceTransformer(EMBED_MODEL)
index = faiss.read_index(INDEX_PATH)

with open(META_PATH, encoding="utf-8") as f:
    META_RAW = json.load(f)

DOCUMENTS = META_RAW["documents"]
