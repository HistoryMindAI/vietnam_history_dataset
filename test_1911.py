"""Quick test: năm 1911 output with full startup."""
import sys, os, glob, shutil, json
from collections import defaultdict

sys.path.insert(0, "ai-service")
for d in glob.glob("ai-service/**/__pycache__", recursive=True):
    shutil.rmtree(d, ignore_errors=True)

import app.core.startup as startup

with open("ai-service/faiss_index/meta.json", encoding="utf-8") as f:
    meta = json.load(f)
startup.DOCUMENTS = meta.get("documents", [])
startup.META_RAW = meta
startup.DOCUMENTS_BY_YEAR = defaultdict(list)
for doc in startup.DOCUMENTS:
    y = doc.get("year")
    if y is not None:
        startup.DOCUMENTS_BY_YEAR[y].append(doc)
startup._build_inverted_indexes()

# CRITICAL: Load knowledge base to populate PERSON_ALIASES
startup._load_knowledge_base()

import faiss
startup.FAISS_INDEX = faiss.read_index("ai-service/faiss_index/index.bin")
startup.INDEX_READY = True

from sentence_transformers import SentenceTransformer
startup.EMBED_MODEL = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

from app.services.engine import engine_answer

print(f"PERSON_ALIASES count: {len(startup.PERSON_ALIASES)}")

result = engine_answer("năm 1911")
answer = result.get("answer", "NO ANSWER")
events = result.get("events", [])

with open("test_1911_output.txt", "w", encoding="utf-8") as f:
    f.write("=== ANSWER ===\n")
    f.write(answer + "\n\n")
    f.write("=== EVENTS ===\n")
    for i, e in enumerate(events):
        yr = e.get("year", "?")
        ev = str(e.get("event", ""))[:300]
        f.write(f"[{i}] year={yr}: {ev}\n")

print("Output written to test_1911_output.txt")
