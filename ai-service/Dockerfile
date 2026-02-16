FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# OPTIMIZATION: Reduce memory fragmentation
ENV MALLOC_ARENA_MAX=2

WORKDIR /app

# Railway will inject PORT env var at runtime.
# Default to 8000 for local development and for this service specifically.
ENV PORT=8000
EXPOSE 8000

# System deps (minimal for faiss-cpu + numpy + curl for LFS fallback)
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    curl \
    libgomp1 \
    libopenblas-dev \
    && rm -rf /var/lib/apt/lists/*

# =====================
# Python dependencies
# =====================
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# =====================
# Copy ONNX model
# =====================
COPY onnx_model /app/onnx_model

# =====================
# Copy Cross-Encoder ONNX (reranker)
# =====================
COPY onnx_cross_encoder /app/onnx_cross_encoder

# CRITICAL: Validate ONNX model is real binary, not a Git LFS pointer.
# LFS pointers are ~130 bytes text. The real model is ~130MB.
# If LFS pointer detected, download via GitHub Raw URL (auto-resolves LFS).
RUN ONNX_SIZE=$(stat -c%s /app/onnx_model/model_quantized.onnx 2>/dev/null || echo 0) && \
    echo "ONNX model size: ${ONNX_SIZE} bytes" && \
    if [ "$ONNX_SIZE" -lt 1000000 ]; then \
    echo "❌ ONNX is LFS pointer (${ONNX_SIZE} bytes). Downloading real file..." && \
    curl -L --retry 3 --retry-delay 5 -o /app/onnx_model/model_quantized.onnx \
    "https://github.com/HistoryMindAI/vietnam_history_dataset/raw/main/ai-service/onnx_model/model_quantized.onnx" && \
    NEW_SIZE=$(stat -c%s /app/onnx_model/model_quantized.onnx) && \
    echo "✅ Downloaded ONNX model: ${NEW_SIZE} bytes" ; \
    else \
    echo "✅ ONNX model is valid (${ONNX_SIZE} bytes)" ; \
    fi

# =====================
# App source
# =====================
COPY app ./app
COPY scripts ./scripts
COPY knowledge_base.json ./knowledge_base.json

# =====================
# Copy Index (From Local)
# =====================
COPY faiss_index ./faiss_index

# CRITICAL: Validate FAISS index.bin was actually copied (not blocked by .dockerignore)
RUN if [ ! -f /app/faiss_index/index.bin ]; then \
    echo "❌ FATAL: faiss_index/index.bin is MISSING! Check .dockerignore" && exit 1; \
    else \
    INDEX_SIZE=$(stat -c%s /app/faiss_index/index.bin) && \
    echo "✅ FAISS index.bin present: ${INDEX_SIZE} bytes"; \
    fi

# V3: Validate FAISS meta.json audit fields exist and count > 0
RUN if [ -f /app/faiss_index/meta.json ]; then \
    META_COUNT=$(python -c "import json; m=json.load(open('/app/faiss_index/meta.json')); print(m.get('count',0))") && \
    echo "✅ FAISS meta.json: count=${META_COUNT}" && \
    if [ "$META_COUNT" -lt 1 ]; then \
    echo "❌ FATAL: FAISS meta.json count is 0" && exit 1; \
    fi; \
    fi

# V3: Validate checksum if present
RUN if [ -f /app/faiss_index/checksum.sha256 ]; then \
    cd /app/faiss_index && sha256sum -c checksum.sha256 && \
    echo "✅ FAISS index checksum verified"; \
    fi

ENV TRANSFORMERS_CACHE=/app/.cache/huggingface
ENV HF_HOME=/app/.cache/huggingface
ENV PYTHONPATH=/app
ENV INDEX_VERSION=v7
# Runtime lock: service verifies these at startup
ENV FAISS_READONLY=1
ENV INDEX_EXPECTED_VERSION=v7

# =====================
# Non-root user (security hardening)
# =====================
RUN groupadd -r appgroup && useradd -r -g appgroup -d /app -s /sbin/nologin appuser && \
    chown -R appuser:appgroup /app
USER appuser

# Copy startup script
COPY --chown=appuser:appgroup start_server.py /app/start_server.py

# HEALTHCHECK — production monitoring
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run with python script to handle env vars robustly
CMD ["python", "start_server.py"]
