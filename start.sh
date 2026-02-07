#!/bin/bash
set -e
cd ai-service
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
