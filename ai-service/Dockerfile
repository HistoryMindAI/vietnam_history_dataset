FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# System deps tối thiểu cho numpy / faiss
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
# App source
# =====================
COPY app ./app
COPY faiss_index ./faiss_index

ENV TRANSFORMERS_CACHE=/app/.cache/huggingface
ENV HF_HOME=/app/.cache/huggingface

# ❌ KHÔNG EXPOSE CŨNG ĐƯỢC (Railway không cần)
# EXPOSE 8000

# ✅ CMD ĐÚNG CHO RAILWAY
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
