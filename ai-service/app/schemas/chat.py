from pydantic import BaseModel
from typing import List, Optional

class EventOut(BaseModel):
    year: int
    event: str
    tone: str = "neutral"  # Default value for events without tone
    story: str

class ChatRequest(BaseModel):
    query: str

class ChatResponse(BaseModel):
    query: str
    intent: str
    answer: Optional[str]
    events: List[EventOut]
    no_data: bool
