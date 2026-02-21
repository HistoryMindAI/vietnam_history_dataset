"""Debug: trace event text through engine pipeline."""
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

import faiss
startup.FAISS_INDEX = faiss.read_index("ai-service/faiss_index/index.bin")
startup.INDEX_READY = True

from sentence_transformers import SentenceTransformer
startup.EMBED_MODEL = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

# Monkey-patch to trace
import app.services.engine as eng
_orig_replace = eng.replace_repeated_names

def _traced_replace(text):
    result = _orig_replace(text)
    if text != result:
        with open("debug_pronoun.txt", "a", encoding="utf-8") as f:
            f.write(f"REPLACED:\n  IN:  {text}\n  OUT: {result}\n\n")
    return result

eng.replace_repeated_names = _traced_replace

# Clear debug file
with open("debug_pronoun.txt", "w", encoding="utf-8") as f:
    f.write("")

result = eng.engine_answer("năm 1911")
answer = result.get("answer", "NO ANSWER")
events = result.get("events", [])

with open("debug_pronoun.txt", "a", encoding="utf-8") as f:
    f.write("=== FINAL ANSWER ===\n")
    f.write(answer + "\n\n")
    f.write("=== FINAL EVENTS ===\n")
    for i, e in enumerate(events):
        yr = e.get("year", "?")
        ev = str(e.get("event", ""))[:300]
        st = str(e.get("story", ""))[:300]
        f.write(f"[{i}] year={yr}\n  event: {ev}\n  story: {st}\n\n")

print("Debug output written to debug_pronoun.txt")
