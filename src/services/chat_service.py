import logging
from src.api.models import ChatRequest
from src.agents.agent import run_agent

agent_logger = logging.getLogger(__name__)

def handle_chat_request(chat_request: ChatRequest):
    response = run_agent(
        user_question=chat_request.message,
        user_id=chat_request.user_id
    )
    
    return response