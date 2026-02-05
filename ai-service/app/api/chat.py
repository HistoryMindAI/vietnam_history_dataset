from fastapi import APIRouter
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.engine import engine_answer

router = APIRouter()

@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    return engine_answer(req.query)
