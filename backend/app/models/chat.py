from pydantic import BaseModel
from typing import List, Optional

class ChatMessage(BaseModel):
    role: str # 'user' or 'assistant'
    content: str

class ChatRequest(BaseModel):
    message: str
    # history: Optional[List[ChatMessage]] = None # Pass history via session instead

class ChatResponse(BaseModel):
    response: str
    structured_output: Optional[dict] = None
    # history: List[ChatMessage] # Return updated history if needed, or manage in session 