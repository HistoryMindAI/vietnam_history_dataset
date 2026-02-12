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
# Using local ONNX model (absolute paths to avoid CWD issues)
EMBED_MODEL_PATH = os.path.join(BASE_DIR, "onnx_model", "model_quantized.onnx")
TOKENIZER_PATH = os.path.join(BASE_DIR, "onnx_model")

# ===============================
# FAISS INDEX CONFIG
# ===============================
INDEX_DIR = os.getenv("FAISS_INDEX_PATH", os.path.join(BASE_DIR, "faiss_index"))

# ===============================
# KNOWLEDGE BASE CONFIG
# ===============================
KNOWLEDGE_BASE_PATH = os.path.join(BASE_DIR, "knowledge_base.json")

# NOTE: history.index only has 1 vector (placeholder). index.bin has 630 real vectors.
INDEX_PATH = os.path.join(INDEX_DIR, "index.bin")
META_PATH = os.path.join(INDEX_DIR, "meta.json")

# ===============================
# SEARCH CONFIG
# ===============================
TOP_K = int(os.getenv("TOP_K", 15))
SIM_THRESHOLD = float(os.getenv("SIM_THRESHOLD", 0.35))

# ===============================
# NLU CONFIG (Natural Language Understanding)
# ===============================
SIM_THRESHOLD_LOW = float(os.getenv("SIM_THRESHOLD_LOW", 0.25))  # Fallback search
FUZZY_MATCH_THRESHOLD = float(os.getenv("FUZZY_MATCH_THRESHOLD", 0.75))  # Entity fuzzy match
HIGH_CONFIDENCE_SCORE = float(os.getenv("HIGH_CONFIDENCE_SCORE", 0.55))  # Bypass keyword check
