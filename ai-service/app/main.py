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
    return {"status": "ok"}

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
