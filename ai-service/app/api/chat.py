from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.engine import engine_answer
import asyncio

router = APIRouter(
    tags=["Chat"]
)

@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    Handles chat requests asynchronously.
    engine_answer is CPU-intensive (embeddings/search),
    so we offload it to a worker thread.
    """
    try:
        return await asyncio.to_thread(engine_answer, req.query)
    except Exception as e:
        print(f"[ERROR] Engine failed processing query: {e}")
        # Return 503 so load balancers know the service is having issues
        # and to differentiate from standard 500 crashes.
        return JSONResponse(
            status_code=503,
            content={"detail": f"Service unavailable or error: {str(e)}"}
        )
