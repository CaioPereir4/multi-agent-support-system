from src.agents.state import AgentState
from langgraph.graph import StateGraph, START, END
from src.agents.nodes import knowledge_node, knowledge_node, route_agents, router_node,customer_support_node, synthesizer_node

def build_graph():


    graph = StateGraph(AgentState)

    graph.add_node(
        "router",
        lambda state: router_node(
            state
        ),
    )

    graph.add_node(
        "knowledge",
        lambda state: knowledge_node(
            state,
        ),
    )

    graph.add_node(
        "customer_support",
        lambda state: customer_support_node(
            state
        ),
    )

    graph.add_node(
        "synthesizer",
        lambda state: synthesizer_node(
            state
        ),
    )

    # --------------------------------------------------------
    # START
    # --------------------------------------------------------

    graph.add_edge(
        START,
        "router",
    )

    # --------------------------------------------------------
    # Router
    # --------------------------------------------------------

    graph.add_conditional_edges(
        "router",
        route_agents,
        {
            "knowledge": "knowledge",
            "customer_support": "customer_support",
        },
    )

    # --------------------------------------------------------
    # Specialized agents
    # --------------------------------------------------------

    graph.add_edge(
        "knowledge",
        "synthesizer",
    )

    graph.add_edge(
        "customer_support",
        "synthesizer",
    )

    # --------------------------------------------------------
    # END
    # --------------------------------------------------------

    graph.add_edge(
        "synthesizer",
        END,
    )

    # --------------------------------------------------------
    # Compile
    # --------------------------------------------------------

    return graph.compile()    