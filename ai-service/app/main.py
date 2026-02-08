from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router

app = FastAPI(
    title="Vietnam History AI",
    version="1.0.0"
)

# ===== CORS =====
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
    from app.core.startup import DOCUMENTS, DOCUMENTS_BY_YEAR, index
    
    try:
        # Get index status
        index_vectors = index.ntotal if index else 0
        
        # Get document stats
        doc_count = len(DOCUMENTS) if DOCUMENTS else 0
        year_count = len(DOCUMENTS_BY_YEAR) if DOCUMENTS_BY_YEAR else 0
        
        # Get year range
        years = list(DOCUMENTS_BY_YEAR.keys()) if DOCUMENTS_BY_YEAR else []
        min_year = min(years) if years else None
        max_year = max(years) if years else None
        
        # Sample some years to verify data
        sample_years = {}
        for y in [40, 1284, 1911, 1945, 1975]:
            if y in DOCUMENTS_BY_YEAR:
                events = DOCUMENTS_BY_YEAR[y]
                sample_years[y] = {
                    "count": len(events),
                    "first_event": events[0].get("title", "")[:50] if events else None
                }
        
        return {
            "status": "ok",
            "faiss": {
                "loaded": index is not None,
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
        "status": "running"
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
