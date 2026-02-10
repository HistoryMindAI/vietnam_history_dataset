from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import threading
import app.core.startup as startup

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

# ===== CORS =====
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://behistorymindai-production.up.railway.app",
        "http://localhost:8080",
        "http://127.0.0.1:8080"
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
    return {
        "service": "Vietnam History AI",
        "status": "running",
        "ready": startup.index is not None
    }

# ===== ENTRYPOINT (RAILWAY) =====
if __name__ == "__main__":
    import os
    import uvicorn

    port = int(os.environ.get("PORT", 8000))

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
    )
