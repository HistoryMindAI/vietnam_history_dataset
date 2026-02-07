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

# Torch CPU (nhẹ, không CUDA)
RUN pip install --no-cache-dir \
    torch==2.0.1+cpu \
    -f https://download.pytorch.org/whl/torch_stable.html

RUN pip install --no-cache-dir -r requirements.txt

# =====================
# App source
# =====================
COPY app ./app
COPY faiss_index ./faiss_index

# HuggingFace cache
ENV TRANSFORMERS_CACHE=/app/.cache/huggingface
ENV HF_HOME=/app/.cache/huggingface

EXPOSE 8000

# ✅ CÁCH 2: Python đọc PORT
CMD ["python", "-m", "app.main"]
