FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# System deps for numpy / faiss
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# =====================
# Python dependencies
# =====================
COPY requirements.txt .

RUN pip install --no-cache-dir \
    torch==2.0.1+cpu \
    -f https://download.pytorch.org/whl/torch_stable.html

RUN pip install --no-cache-dir -r requirements.txt

# =====================
# Pre-download ML model (cached in image)
# =====================
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')"

# =====================
# App source
# =====================
COPY app ./app
COPY scripts ./scripts

# =====================
# Build FRESH FAISS index during build (NOT copied from local)
# =====================
# RUN mkdir -p faiss_index && python scripts/build_from_huggingface.py
# COPY faiss_index ./faiss_index  <-- This will be copied by "COPY . ." or specific copy below
COPY faiss_index ./faiss_index

ENV TRANSFORMERS_CACHE=/app/.cache/huggingface
ENV HF_HOME=/app/.cache/huggingface
ENV PYTHONPATH=/app
ENV INDEX_VERSION=v3

# Copy startup script
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Use the startup script
CMD ["/app/start.sh"]

