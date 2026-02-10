FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
# OPTIMIZATION: Reduce memory fragmentation
ENV MALLOC_ARENA_MAX=2

WORKDIR /app

EXPOSE 8080

# System deps (minimal for faiss-cpu + numpy)
# NOTE: git-lfs is required to properly pull large ONNX model files
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    git-lfs \
    libgomp1 \
    libopenblas-dev \
    && git lfs install \
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
# LFS pointers are ~130 bytes text files starting with "version https://git-lfs"
# The real model is ~130MB. If this check fails, LFS was not pulled properly.
RUN ONNX_SIZE=$(stat -c%s /app/onnx_model/model_quantized.onnx 2>/dev/null || echo 0) && \
    echo "ONNX model size: ${ONNX_SIZE} bytes" && \
    if [ "$ONNX_SIZE" -lt 1000000 ]; then \
    echo "❌ FATAL: ONNX model is too small (${ONNX_SIZE} bytes). Likely a Git LFS pointer!" && \
    echo "Content of file:" && head -c 200 /app/onnx_model/model_quantized.onnx && echo "" && \
    echo "Attempting to pull real file via git-lfs..." && \
    cd /tmp && \
    git clone --filter=blob:none --no-checkout https://github.com/HistoryMindAI/vietnam_history_dataset.git repo && \
    cd repo && \
    git lfs install && \
    git lfs pull --include="ai-service/onnx_model/model_quantized.onnx" && \
    git checkout HEAD -- ai-service/onnx_model/model_quantized.onnx && \
    cp ai-service/onnx_model/model_quantized.onnx /app/onnx_model/model_quantized.onnx && \
    cd / && rm -rf /tmp/repo && \
    NEW_SIZE=$(stat -c%s /app/onnx_model/model_quantized.onnx) && \
    echo "✅ LFS pull successful. New size: ${NEW_SIZE} bytes" ; \
    else \
    echo "✅ ONNX model looks valid (${ONNX_SIZE} bytes)" ; \
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

