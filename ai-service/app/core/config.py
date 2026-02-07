import os

# ===============================
# EMBEDDING MODEL CONFIG
# ===============================
# Model mặc định: nhẹ, chạy CPU ổn, dim = 384
EMBED_MODEL = os.getenv(
    "EMBED_MODEL",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)

# ===============================
# FAISS INDEX CONFIG
# ===============================
INDEX_DIR = os.getenv("FAISS_INDEX_PATH", "faiss_index")

INDEX_PATH = os.path.join(INDEX_DIR, "history.index")
META_PATH = os.path.join(INDEX_DIR, "meta.json")

# ===============================
# SEARCH CONFIG
# ===============================
TOP_K = int(os.getenv("TOP_K", 15))
SIM_THRESHOLD = float(os.getenv("SIM_THRESHOLD", 0.45))
