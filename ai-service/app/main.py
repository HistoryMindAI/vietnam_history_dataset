from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import threading
import sys
import os
import app.core.startup as startup

# Debug Logging
print(f"🔥 [MAIN] Initializing main.py. PORT={os.environ.get('PORT')}")

from app.api.chat import router as chat_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load resources in background to allow fast startup/health check
    print("[LIFESPAN] Starting resource loading in background...")
    thread = threading.Thread(target=startup.load_resources)
    thread.start()
    yield
    # Clean up (if needed)

app = FastAPI(
    title="Vietnam History AI",
    version="1.0.0",
    lifespan=lifespan
)

# ===== MIDDLEWARE =====
@app.middleware("http")
async def log_requests(request, call_next):
    import time
    start_time = time.time()
    path = request.url.path
    print(f"📥 [REQUEST] {request.method} {path}", flush=True)
    response = await call_next(request)
    duration = time.time() - start_time
    print(f"📤 [RESPONSE] {request.method} {path} | Status: {response.status_code} | {duration:.3f}s", flush=True)
    return response

# ===== CORS =====
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://behistorymindai-production.up.railway.app",
        "https://fehistorymindai-production.up.railway.app",
        "http://localhost:8080",
        "http://localhost:3000",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:3000"
    ],
    allow_credentials=False,   # bắt buộc False khi "*"
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== ROUTER =====
app.include_router(chat_router, prefix="/api")

# ===== HEALTH CHECK =====
@app.get("/health")
def health():
    """Basic health check for load balancers."""
    return {"status": "ok"}


@app.get("/health/detailed")
def health_detailed():
    """
    Detailed health check endpoint to verify:
    - FAISS index is loaded
    - Documents are loaded
    - Year coverage
    - Sample data for verification
    """
    try:
        # Get index status
        index_vectors = startup.index.ntotal if startup.index else 0
        
        # Get document stats
        doc_count = len(startup.DOCUMENTS) if startup.DOCUMENTS else 0
        year_count = len(startup.DOCUMENTS_BY_YEAR) if startup.DOCUMENTS_BY_YEAR else 0
        
        # Get year range
        years = list(startup.DOCUMENTS_BY_YEAR.keys()) if startup.DOCUMENTS_BY_YEAR else []
        min_year = min(years) if years else None
        max_year = max(years) if years else None
        
        # Sample some years to verify data
        sample_years = {}
        if startup.DOCUMENTS_BY_YEAR:
            for y in [40, 1284, 1911, 1945, 1975]:
                if y in startup.DOCUMENTS_BY_YEAR:
                    events = startup.DOCUMENTS_BY_YEAR[y]
                    sample_years[y] = {
                        "count": len(events),
                        "first_event": events[0].get("title", "")[:50] if events else None
                    }
        
        return {
            "status": "ok",
            "faiss": {
                "loaded": startup.index is not None,
                "vectors": index_vectors
            },
            "documents": {
                "loaded": doc_count > 0,
                "count": doc_count,
                "year_count": year_count,
                "year_range": f"{min_year} - {max_year}" if min_year else None
            },
            "sample_years": sample_years,
            "ready": index_vectors > 0 and doc_count > 0
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "ready": False
        }


@app.get("/")
def root():
    try:
        is_ready = startup.index is not None and len(startup.DOCUMENTS) > 0
        loading_error = getattr(startup, 'LOADING_ERROR', None)
        return {
            "service": "Vietnam History AI",
            "status": "ready" if is_ready else "loading",
            "ready": is_ready,
            "error": loading_error
        }
    except Exception as e:
        return {
            "service": "Vietnam History AI",
            "status": "error",
            "ready": False,
            "error": str(e)
        }

# ===== ENTRYPOINT (RAILWAY) =====
# Note: Use start_server.py to run the app.
# This block is removed to avoid confusion about the correct entrypoint.
