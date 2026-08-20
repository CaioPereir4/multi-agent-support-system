from typing import Any, Literal

from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from langchain.agents import AgentState as ChatAgentState, create_agent
from langchain_core.language_models import BaseChatModel
from langgraph.graph import StateGraph, START, END

AgentType = Literal[
    "knowledge",
    "customer_support",
]


class AgentState(ChatAgentState[Any]):
    user_message: str

    user_id: str | None

    selected_agents: list[AgentType]

    knowledge_result: str | None

    customer_support_result: str | None

    final_response: str | None
    
class RoutingDecision(BaseModel):
    agents: list[AgentType] = Field(
        description=(
            "Specialized agents required to solve "
            "the user's request."
        )
    )    