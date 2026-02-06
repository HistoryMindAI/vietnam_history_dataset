from fastapi import APIRouter
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.engine import engine_answer
import asyncio

router = APIRouter()

@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    Handles chat requests asynchronously.
    The engine_answer is CPU-intensive (embeddings/search), so we offload it
    to a worker thread to keep the FastAPI event loop responsive.
    """
    return await asyncio.to_thread(engine_answer, req.query)
