FROM python:3.11

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# System deps for numpy / faiss
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    libgomp1 \
    libopenblas-dev \
    && rm -rf /var/lib/apt/lists/*

# =====================
# Python dependencies
# =====================
COPY requirements.txt .

RUN pip install --no-cache-dir \
    torch==2.2.2+cpu \
    --index-url https://download.pytorch.org/whl/cpu

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
# WE DO NOT BUILD ON SERVER. WE COPY LOCAL INDEX.
COPY faiss_index ./faiss_index

ENV TRANSFORMERS_CACHE=/app/.cache/huggingface
ENV HF_HOME=/app/.cache/huggingface
ENV PYTHONPATH=/app
ENV INDEX_VERSION=v6
ENV MALLOC_ARENA_MAX=2

# Copy startup script
COPY run.py /app/run.py

# Run with Python directly (No shell/CRLF issues)
CMD ["python", "/app/run.py"]

