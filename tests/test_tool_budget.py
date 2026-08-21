"""One flailing agent turned a single question into nine LLM calls; these caps stop that."""

from langchain.agents import create_agent
from langchain.agents.middleware import ToolCallLimitMiddleware
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from tests.conftest import FakeChatModel, tool_call


def build_counting_tools():
    calls = {"knowledge_base_search": 0, "web_search": 0}

    @tool
    def knowledge_base_search(query: str) -> str:
        """Search the knowledge base."""
        calls["knowledge_base_search"] += 1
        return '{"status": "ok"}'

    @tool
    def web_search(query: str, restrict_to_getnet: bool = False) -> str:
        """Search the web."""
        calls["web_search"] += 1
        return '{"status": "ok"}'

    return calls, [knowledge_base_search, web_search]


def run_agent_with(sequence):
    calls, tools = build_counting_tools()
    messages = iter(
        [tool_call(name, str(i), query=f"q{i}") for i, name in enumerate(sequence)]
        + [AIMessage(content="resposta")]
    )
    agent = create_agent(
        model=FakeChatModel(messages=messages),
        tools=tools,
        system_prompt="sys",
        middleware=[
            ToolCallLimitMiddleware(run_limit=4, exit_behavior="continue"),
            ToolCallLimitMiddleware(
                tool_name="knowledge_base_search", run_limit=1, exit_behavior="continue"
            ),
        ],
    )
    result = agent.invoke({"messages": [{"role": "user", "content": "pergunta"}]})
    return calls, result


def test_the_knowledge_base_is_searched_at_most_once():
    calls, result = run_agent_with(["knowledge_base_search"] * 3)

    assert calls["knowledge_base_search"] == 1
    assert result["messages"][-1].content == "resposta"


def test_the_web_fallback_survives_a_stubborn_agent():
    """A tighter global cap let blocked retries eat the fallback budget."""
    calls, _ = run_agent_with(["knowledge_base_search"] * 3 + ["web_search"])

    assert calls["knowledge_base_search"] == 1
    assert calls["web_search"] == 1


def test_the_intended_path_costs_two_tool_calls():
    calls, _ = run_agent_with(["knowledge_base_search", "web_search"])

    assert calls == {"knowledge_base_search": 1, "web_search": 1}
