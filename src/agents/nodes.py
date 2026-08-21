from functools import lru_cache

from langchain.agents import create_agent

from src.agents.state import AgentState, RoutingDecision
from src.llm.llm import build_chat_model
from src.prompts.templates import (
    KNOWLEDGE_AGENT_PROMPT,
    ROUTER_PROMPT,
    SUPPORT_AGENT_PROMPT,
    SYNTHESIS_PROMPT,
)
from src.tools.customer_support import (
    get_merchant_profile,
    get_recent_transactions,
    get_settlement_schedule,
    get_terminal_diagnostics,
    open_support_ticket,
)
from src.tools.knowledge_base import knowledge_base_search, web_search

DEFAULT_LANGUAGE = "pt-BR"


def _resolve_language(state: AgentState) -> str:
    return state.get("language") or DEFAULT_LANGUAGE


def _with_language_instruction(prompt: str, language: str) -> str:
    return f"{prompt}\n# User language\nAnswer entirely in `{language}`.\n"


@lru_cache(maxsize=1)
def build_router():
    model = build_chat_model()
    return model.with_structured_output(RoutingDecision)


def router_node(state: AgentState):
    router = build_router()
    decision = router.invoke(
        [
            {
                "role": "system",
                "content": ROUTER_PROMPT,
            },
            {
                "role": "user",
                "content": state["user_message"],
            },
        ]
    )

    return {
        "selected_agents": decision.agents,
        "language": decision.language,
    }


@lru_cache(maxsize=8)
def build_knowledge_agent(language: str):
    model = build_chat_model()
    return create_agent(
        model=model,
        tools=[
            knowledge_base_search,
            web_search,
        ],
        system_prompt=_with_language_instruction(KNOWLEDGE_AGENT_PROMPT, language),
    )


def knowledge_node(state: AgentState):
    agent = build_knowledge_agent(_resolve_language(state))
    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": state["user_message"],
                }
            ]
        }
    )

    return {"knowledge_result": result["messages"][-1].content}


@lru_cache(maxsize=8)
def build_customer_support_agent(language: str):

    return create_agent(
        model=build_chat_model(),
        tools=[
            get_merchant_profile,
            get_recent_transactions,
            get_settlement_schedule,
            get_terminal_diagnostics,
            open_support_ticket,
        ],
        system_prompt=_with_language_instruction(SUPPORT_AGENT_PROMPT, language),
        state_schema=AgentState,
    )


def customer_support_node(state: AgentState):

    agent = build_customer_support_agent(_resolve_language(state))

    prompt = f"""
    User request:
    {state["user_message"]}
    """

    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            "user_id": state["user_id"],
        }
    )

    return {"customer_support_result": result["messages"][-1].content}


def route_agents(state: AgentState):
    return state["selected_agents"]


def synthesizer_node(state: AgentState):

    findings = [
        (label, state.get(key))
        for label, key in (
            ("Customer Support Agent", "customer_support_result"),
            ("Knowledge Agent", "knowledge_result"),
        )
        if state.get(key)
    ]

    if not findings:
        return {"final_response": "No response generated."}

    # Only one specialist ran: its answer is already the answer.
    # Re-writing it costs an extra LLM round trip and loses content.
    if len(findings) == 1:
        return {"final_response": findings[0][1]}

    sections = "\n\n".join(f"{label}:\n{value}" for label, value in findings)

    prompt = f"""
    {_with_language_instruction(SYNTHESIS_PROMPT, _resolve_language(state))}

    Original request:
    {state["user_message"]}

    {sections}
    """

    model = build_chat_model()

    result = model.invoke(prompt)

    return {"final_response": result.content}
