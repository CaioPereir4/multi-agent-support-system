from langgraph.graph import END, START, StateGraph

from src.agents.nodes import (
    customer_support_node,
    knowledge_node,
    route_agents,
    router_node,
    synthesizer_node,
)
from src.agents.state import AgentState


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("router", router_node)
    graph.add_node("knowledge", knowledge_node)
    graph.add_node("customer_support", customer_support_node)
    graph.add_node("synthesizer", synthesizer_node)

    graph.add_edge(START, "router")

    graph.add_conditional_edges(
        "router",
        route_agents,
        {
            "knowledge": "knowledge",
            "customer_support": "customer_support",
        },
    )

    graph.add_edge("knowledge", "synthesizer")
    graph.add_edge("customer_support", "synthesizer")
    graph.add_edge("synthesizer", END)

    return graph.compile()
