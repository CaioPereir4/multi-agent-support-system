from src.agents.pipeline import run_agent
from src.api.models import ChatRequest


def handle_chat_request(chat_request: ChatRequest):
    response = run_agent(user_question=chat_request.message, user_id=chat_request.user_id)

    return response
