from functools import lru_cache

from src.llm.llm import build_chat_model
from langchain.agents import create_agent
from src.agents.state import AgentState, RoutingDecision
from src.prompts.templates import ROUTER_PROMPT, KNOWLEDGE_AGENT_PROMPT, SUPPORT_AGENT_PROMPT, SYNTHESIS_PROMPT
from src.tools.knowledge_base import web_search
from src.tools.customer_support import get_merchant_profile, get_recent_transactions, get_settlement_schedule, get_terminal_diagnostics, open_support_ticket

@lru_cache(maxsize=1)
def build_router():
    model = build_chat_model()
    return model.with_structured_output(RoutingDecision)

def router_node(state: AgentState):
    router = build_router()
    decision = router.invoke([
        {
            "role": "system",
            "content": ROUTER_PROMPT,
        },
        {
            "role": "user",
            "content": state["user_message"],
        },
    ])

    return {
        "selected_agents": decision.agents
    }
    

@lru_cache(maxsize=1)
def build_knowledge_agent():
    model = build_chat_model()
    return create_agent(
        model=model,
        tools=[
            web_search,
        ],
        system_prompt=KNOWLEDGE_AGENT_PROMPT,
    )    
    
def knowledge_node(state: AgentState):
    agent = build_knowledge_agent()
    result = agent.invoke({
        "messages": [
            {
                "role": "user",
                "content": state["user_message"],
            }
        ]
    })

    return {
        "knowledge_result":
            result["messages"][-1].content
    }    
    
@lru_cache(maxsize=1)
def build_customer_support_agent():

    return create_agent(
        model=build_chat_model(),
        tools=[
            get_merchant_profile,
            get_recent_transactions,
            get_settlement_schedule,
            get_terminal_diagnostics,
            open_support_ticket,
        ],
        system_prompt=SUPPORT_AGENT_PROMPT,
    )


def customer_support_node(state: AgentState):

    agent = build_customer_support_agent()

    user_id = state["user_id"]

    prompt = f"""
    USER ID:
    {user_id}

    User request:
    {state["user_message"]}
    """

    result = agent.invoke({
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ]
    })

    return {
        "customer_support_result":
            result["messages"][-1].content
    }
   
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
    {SYNTHESIS_PROMPT}

    Original request:
    {state["user_message"]}

    {sections}
    """

    model = build_chat_model()

    result = model.invoke(prompt)

    return {
        "final_response": result.content
    }
    
