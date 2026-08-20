
from src.infra.logger import get_logger
from langchain.messages import HumanMessage
from src.agents.graph import build_graph

logger = get_logger(__name__)

def run_agent(user_question: str, user_id: str) -> str:
    
    logger.info(f"Agent user question: {user_question}")
    logger.info(f"Agent user ID: {user_id}")
    

    # Build the state graph
    graph = build_graph()
    result = graph.invoke({
        "user_message": HumanMessage(content=user_question),
        "user_id": user_id,
        "customer_support_result": None,
        "knowledge_result": None,
        "final_response": None,
        "selected_agents": []
    })
    
    return result.get("final_response", "No response generated.")
