from pydantic import BaseModel, ConfigDict
from typing import List, Optional

class EventOut(BaseModel):
    id: Optional[str] = None
    year: Optional[int] = None
    event: Optional[str] = None
    story: Optional[str] = None
    persons: Optional[List[str]] = []
    places: Optional[List[str]] = []
    keywords: Optional[List[str]] = []

    model_config = ConfigDict(extra="ignore")

class ChatRequest(BaseModel):
    query: str

class ChatResponse(BaseModel):
    query: str
    intent: str
    answer: Optional[str]
    events: List[EventOut]
    no_data: bool

