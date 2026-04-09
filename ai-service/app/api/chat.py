import asyncio

from fastapi import APIRouter, HTTPException

from app.core.config import CHAT_ACQUIRE_TIMEOUT_SECONDS, CHAT_MAX_CONCURRENT_REQUESTS
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.engine import engine_answer

router = APIRouter(
    tags=["Chat"]
)
chat_slots = asyncio.Semaphore(CHAT_MAX_CONCURRENT_REQUESTS)

@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    Handles chat requests asynchronously.
    engine_answer is CPU-intensive (embeddings/search),
    so we offload it to a worker thread.
    """
    acquired = False

    try:
        await asyncio.wait_for(chat_slots.acquire(), timeout=CHAT_ACQUIRE_TIMEOUT_SECONDS)
        acquired = True
    except TimeoutError as exc:
        raise HTTPException(
            status_code=503,
            detail="AI service is busy. Please retry shortly.",
            headers={"Retry-After": "1"},
        ) from exc

    try:
        return await asyncio.to_thread(engine_answer, req.query)
    except Exception as exc:
        print(f"[ERROR] Engine failed processing query: {exc}")
        raise HTTPException(
            status_code=503,
            detail="Service unavailable or error while processing the query.",
        ) from exc
    finally:
        if acquired:
            chat_slots.release()
