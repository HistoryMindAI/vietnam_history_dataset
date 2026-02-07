import os

INDEX_DIR = os.getenv("FAISS_INDEX_PATH", "faiss_index")

INDEX_PATH = os.path.join(INDEX_DIR, "history.index")
META_PATH = os.path.join(INDEX_DIR, "meta.json")

TOP_K = int(os.getenv("TOP_K", 15))
SIM_THRESHOLD = float(os.getenv("SIM_THRESHOLD", 0.45))
