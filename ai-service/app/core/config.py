import os

# ===============================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ===============================
# EMBEDDING MODEL CONFIG
# ===============================
# EMBED_MODEL = os.getenv(
#     "EMBED_MODEL",
#     "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
# )
# Model ID for reference (and legacy scripts)
EMBED_MODEL = "keepitreal/vietnamese-sbert"
# Using local ONNX model
EMBED_MODEL_PATH = "onnx_model/model_quantized.onnx"
TOKENIZER_PATH = "onnx_model"

# ===============================
# FAISS INDEX CONFIG
# ===============================
INDEX_DIR = os.getenv("FAISS_INDEX_PATH", os.path.join(BASE_DIR, "faiss_index"))

INDEX_PATH = os.path.join(INDEX_DIR, "history.index")
META_PATH = os.path.join(INDEX_DIR, "meta.json")

# ===============================
# SEARCH CONFIG
# ===============================
TOP_K = int(os.getenv("TOP_K", 15))
SIM_THRESHOLD = float(os.getenv("SIM_THRESHOLD", 0.6))
