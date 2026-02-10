#!/bin/sh
set -e

# Default to port 8080 if PORT is not set
# Railway provides PORT, but good to have fallback
export PORT=${PORT:-8080}

echo "Starting app via run.py on port $PORT..."
# Exec python to replace shell process
exec python /app/run.py
