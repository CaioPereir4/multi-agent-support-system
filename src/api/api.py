from typing import Any

from fastapi import APIRouter

from src.api.models import ChatRequest, ChatResponse
from src.rag import vector_store
from src.services.chat_service import handle_chat_request

api_router = APIRouter()


@api_router.post("/chat")
def chat(chat_request: ChatRequest) -> ChatResponse:
    response = handle_chat_request(chat_request)
    return ChatResponse(response=response)


@api_router.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "knowledge_base": vector_store.status()}
