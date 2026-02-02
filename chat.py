import os
import sys
import json
import re
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from llama_cpp import Llama

# ===================== FIX WINDOWS ENCODING =====================
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# ===================== CONFIG =====================
EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

FAISS_INDEX_PATH = "./faiss_index/history.index"
META_PATH = "./faiss_index/meta.json"

MODEL_PATH = "./models/qwen2.5-7b-instruct-q4_k_m.gguf"

TOP_K = 8

SYSTEM_RULES = """Bạn là trợ lý AI lịch sử Việt Nam.
CHỈ sử dụng thông tin trong tài liệu.
KHÔNG suy đoán.
KHÔNG dùng kiến thức bên ngoài.
Nếu tài liệu không có thông tin, chỉ trả lời đúng 1 câu:
Không có thông tin trong tài liệu.
Chỉ trả lời bằng tiếng Việt.
"""

YEAR_PATTERN = re.compile(r"\b(1[0-9]{3})\b")

# ===================== LOAD FAISS =====================
def load_faiss():
    index = faiss.read_index(FAISS_INDEX_PATH)
    with open(META_PATH, encoding="utf-8") as f:
        meta = json.load(f)
    docs = [m["text"] for m in meta]
    return index, docs

# ===================== YEAR EXTRACTION =====================
def extract_year(query: str):
    m = YEAR_PATTERN.search(query)
    return m.group(1) if m else None

# ===================== QUERY EXPANSION =====================
def expand_query(query: str):
    """
    Giữ mở rộng NHẸ để tăng recall,
    KHÔNG quyết định logic ở đây
    """
    queries = [query]
    year = extract_year(query)
    if year:
        queries.append(f"Năm {year}")
    return queries

# ===================== FAISS RETRIEVAL =====================
def retrieve_context(query, embedder, index, docs):
    queries = expand_query(query)
    results = []

    for q in queries:
        emb = embedder.encode([q], convert_to_numpy=True).astype("float32")
        faiss.normalize_L2(emb)
        _, ids = index.search(emb, TOP_K)

        for i in ids[0]:
            if 0 <= i < len(docs):
                results.append(docs[i])

    # unique, giữ thứ tự
    seen = set()
    uniq = []
    for r in results:
        if r not in seen:
            uniq.append(r)
            seen.add(r)

    return uniq

# ===================== HARD FILTER BY YEAR =====================
def filter_by_year(docs, year):
    """
    QUYẾT ĐỊNH BẰNG CODE – KHÔNG GIAO CHO LLM
    """
    if not year:
        return docs

    filtered = []
    for d in docs:
        if d.startswith(f"Năm {year},"):
            filtered.append(d)

    return filtered

# ===================== PROMPT =====================
def build_prompt(context_docs, question):
    context = "\n".join(context_docs)
    return f"""{SYSTEM_RULES}

TÀI LIỆU:
{context}

CÂU HỎI:
{question}

TRẢ LỜI:
"""

# ===================== MAIN =====================
def main():
    embedder = SentenceTransformer(EMBED_MODEL)
    index, docs = load_faiss()

    llm = Llama(
        model_path=MODEL_PATH,
        n_ctx=4096,
        temperature=0.0,
        n_threads=8,
        n_gpu_layers=0,
        verbose=False
    )

    print("\n👉 Gõ câu hỏi (exit để thoát)\n")

    while True:
        query = input("🧑 Bạn: ").strip()
        if query.lower() == "exit":
            break

        year = extract_year(query)

        # 1️⃣ Retrieve
        ctx_raw = retrieve_context(query, embedder, index, docs)

        # 2️⃣ HARD FILTER (QUAN TRỌNG NHẤT)
        ctx = filter_by_year(ctx_raw, year)

        # 3️⃣ Không có → trả lời cứng
        if not ctx:
            print("\n🤖 AI: Không có thông tin trong tài liệu.\n")
            continue

        # 4️⃣ Build prompt & generate
        prompt = build_prompt(ctx, query)

        output = llm(
            prompt,
            max_tokens=120,
            stop=["\n", "Human:", "Assistant:", "请", "Premier", "。"]
        )

        raw = output["choices"][0]["text"].strip()
        answer = raw.split("\n")[0].strip()

        if "." in answer:
            answer = answer.split(".")[0] + "."

        if not answer:
            answer = "Không có thông tin trong tài liệu."

        print(f"\n🤖 AI: {answer}\n")

# ===================== RUN =====================
if __name__ == "__main__":
    main()
