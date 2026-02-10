FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
# OPTIMIZATION: Reduce memory fragmentation
ENV MALLOC_ARENA_MAX=2

WORKDIR /app

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

# =====================
# Copy Index (From Local)
# =====================
COPY faiss_index ./faiss_index

ENV TRANSFORMERS_CACHE=/app/.cache/huggingface
ENV HF_HOME=/app/.cache/huggingface
ENV PYTHONPATH=/app
ENV INDEX_VERSION=v6

# Copy startup script
COPY start_server.py /app/start_server.py

# Run with python script to handle env vars robustly
CMD ["python", "start_server.py"]
