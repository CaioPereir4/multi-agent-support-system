from pydantic import BaseModel

class ChatRequest(BaseModel):
    user_id: str
    message: str
    thread_id: str
    
class ChatResponse(BaseModel):
    response: str