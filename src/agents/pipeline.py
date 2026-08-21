from functools import lru_cache

from src.agents.graph import build_graph
from src.infra.logger import get_logger

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def _compiled_graph():
    return build_graph()


def run_agent(user_question: str, user_id: str) -> str:
    logger.info("Agent user question: %s", user_question)
    logger.info("Agent user ID: %s", user_id)

    result = _compiled_graph().invoke(
        {
            "user_message": user_question,
            "user_id": user_id,
            "customer_support_result": None,
            "knowledge_result": None,
            "final_response": None,
            "selected_agents": [],
        }
    )

    return result.get("final_response", "No response generated.")
