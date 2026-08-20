from fastapi import APIRouter
from src.api.models import ChatRequest, ChatResponse

api_router = APIRouter()

@api_router.post("/chat")
async def chat(chat_request: ChatRequest) -> ChatResponse:
    return ChatResponse(response="This is a placeholder response.")