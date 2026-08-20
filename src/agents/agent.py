
from src.infra.logger import get_logger
from langchain.messages import HumanMessage
from langchain.agents import create_agent
from src.llm.llm import build_chat_model
from src.prompts.templates import SMALLTALK_PROMPT

agent_logger = get_logger(__name__)

def run_agent(user_question: str, user_id: str) -> str:
    model = build_chat_model()
    
    agent_logger.info(f"Agent user question: {user_question}")
    agent_logger.info(f"Agent user ID: {user_id}")
    
    agent = create_agent(
        model=model,
        system_prompt=SMALLTALK_PROMPT
    )
    
    question = HumanMessage(content=user_question)
    response = agent.invoke({
        "messages": [question],
    })
    
    agent_logger.info(f"Agent response: {response}")
    
    return response["messages"][-1].content
