FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

WORKDIR /app

EXPOSE 8080

# System deps (minimal for faiss-cpu + numpy)
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
# Copy Index (From Local)
# =====================
COPY faiss_index ./faiss_index

ENV TRANSFORMERS_CACHE=/app/.cache/huggingface
ENV HF_HOME=/app/.cache/huggingface
ENV PYTHONPATH=/app
ENV INDEX_VERSION=v6

# Copy startup script & make executable
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Run with shell script to handle env vars robustly
CMD ["/app/start.sh"]

