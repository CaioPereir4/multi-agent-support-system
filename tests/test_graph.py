"""Orchestration: routing, the language decision and how partial results are merged."""

from langchain_core.messages import AIMessage

from src.agents import nodes
from src.agents.graph import build_graph
from src.agents.state import RoutingDecision


class RecordingAgent:
    def __init__(self, answer: str):
        self.answer = answer
        self.payloads: list[dict] = []

    def invoke(self, payload):
        self.payloads.append(payload)
        return {"messages": [AIMessage(content=self.answer)]}


class FakeRouter:
    def __init__(self, decision: RoutingDecision):
        self.decision = decision

    def invoke(self, _):
        return self.decision


class FakeModel:
    def __init__(self, answer: str = "resposta combinada"):
        self.answer = answer
        self.calls = 0

    def invoke(self, _):
        self.calls += 1
        return AIMessage(content=self.answer)


def wire(monkeypatch, agents, language="pt-BR", knowledge=None, support=None, model=None):
    monkeypatch.setattr(
        nodes, "build_router", lambda: FakeRouter(RoutingDecision(agents=agents, language=language))
    )
    knowledge = knowledge or RecordingAgent("resposta da knowledge")
    support = support or RecordingAgent("resposta do suporte")
    model = model or FakeModel()
    monkeypatch.setattr(nodes, "build_knowledge_agent", lambda lang: knowledge)
    monkeypatch.setattr(nodes, "build_customer_support_agent", lambda lang: support)
    monkeypatch.setattr(nodes, "build_chat_model", lambda: model)
    return knowledge, support, model


def run(message="pergunta", user_id="cliente1988"):
    return build_graph().invoke(
        {
            "user_message": message,
            "user_id": user_id,
            "customer_support_result": None,
            "knowledge_result": None,
            "final_response": None,
            "selected_agents": [],
        }
    )


def test_a_single_specialist_answers_without_a_synthesis_round_trip(monkeypatch):
    _knowledge, _support, model = wire(monkeypatch, ["knowledge"])

    result = run()

    assert result["final_response"] == "resposta da knowledge"
    assert model.calls == 0, "one specialist needs no merge; the extra LLM call was pure latency"


def test_two_specialists_are_merged_by_the_synthesizer(monkeypatch):
    _, _, model = wire(monkeypatch, ["knowledge", "customer_support"])

    result = run()

    assert result["final_response"] == "resposta combinada"
    assert model.calls == 1


def test_the_support_agent_receives_the_authenticated_user_through_the_state(monkeypatch):
    _, support, _ = wire(monkeypatch, ["customer_support"])

    run(user_id="cliente2024")

    assert support.payloads[0]["user_id"] == "cliente2024"
    assert "cliente2024" not in str(support.payloads[0]["messages"]), (
        "the id travels in the state, not in the prompt the model can echo"
    )


def test_the_router_language_reaches_every_agent(monkeypatch):
    seen: list[str] = []
    knowledge = RecordingAgent("answer")
    monkeypatch.setattr(
        nodes,
        "build_router",
        lambda: FakeRouter(RoutingDecision(agents=["knowledge"], language="en")),
    )
    monkeypatch.setattr(
        nodes, "build_knowledge_agent", lambda lang: (seen.append(lang), knowledge)[1]
    )

    run()

    assert seen == ["en"]


def test_the_language_instruction_is_appended_to_the_prompt():
    prompt = nodes._with_language_instruction("SYSTEM", "es")

    assert "SYSTEM" in prompt
    assert "`es`" in prompt


def test_the_language_falls_back_when_the_router_did_not_set_one():
    assert nodes._resolve_language({}) == nodes.DEFAULT_LANGUAGE
    assert nodes._resolve_language({"language": "en"}) == "en"


def test_the_router_decision_drives_the_edges(monkeypatch):
    knowledge, support, _ = wire(monkeypatch, ["customer_support"])

    run()

    assert support.payloads, "customer_support was selected and must run"
    assert not knowledge.payloads, "knowledge was not selected and must stay idle"
