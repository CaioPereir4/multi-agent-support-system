from typing import Any, Literal

from langchain.agents import AgentState as ChatAgentState
from pydantic import BaseModel, Field

AgentType = Literal[
    "knowledge",
    "customer_support",
]


class AgentState(ChatAgentState[Any]):
    user_message: str

    user_id: str | None

    language: str | None

    selected_agents: list[AgentType]

    knowledge_result: str | None

    customer_support_result: str | None

    final_response: str | None


class RoutingDecision(BaseModel):
    agents: list[AgentType] = Field(
        description=("Specialized agents required to solve the user's request.")
    )

    language: str = Field(
        default="pt-BR",
        description=(
            "BCP-47 tag of the language the user wrote in "
            "(pt-BR, en, es, ...). The whole answer is written "
            "in this language."
        ),
    )
