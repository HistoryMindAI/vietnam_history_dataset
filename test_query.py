# -*- coding: utf-8 -*-
import sys, os, glob, shutil

# Clear ALL pycache
sys.path.insert(0, 'ai-service')
for d in glob.glob('ai-service/**/__pycache__', recursive=True):
    shutil.rmtree(d, ignore_errors=True)
    print(f"Cleared: {d}")

os.environ['PYTHONIOENCODING'] = 'utf-8'

import json
import app.core.startup as startup
from collections import defaultdict

meta_path = os.path.join('ai-service', 'faiss_index', 'meta.json')
with open(meta_path, encoding='utf-8') as f:
    meta = json.load(f)
startup.DOCUMENTS = meta.get('documents', [])
startup.META_RAW = meta
startup.DOCUMENTS_BY_YEAR = defaultdict(list)
for doc in startup.DOCUMENTS:
    y = doc.get('year')
    if y is not None:
        startup.DOCUMENTS_BY_YEAR[y].append(doc)
startup._build_inverted_indexes()

import faiss
startup.FAISS_INDEX = faiss.read_index(os.path.join('ai-service', 'faiss_index', 'index.bin'))
startup.INDEX_READY = True
from sentence_transformers import SentenceTransformer
startup.EMBED_MODEL = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

from app.services.engine import engine_answer
result = engine_answer("n\u0103m 1911")

with open(r'C:\Users\lenovo\tmp_query_result2.txt', 'w', encoding='utf-8') as f:
    f.write("=== ANSWER ===\n")
    f.write(result.get("answer", "NO ANSWER"))
    f.write("\n\n=== NO_DATA ===\n")
    f.write(str(result.get("no_data", False)))

print("Done!", flush=True)
