from dataclasses import dataclass, field
from typing import Any

import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from src.agents import nodes
from src.rag import vector_store
from src.tools import crm


@dataclass
class FakeRuntime:
    """Stands in for the ToolRuntime LangGraph injects into the support tools."""

    state: dict[str, Any] = field(default_factory=dict)


class FakeChatModel(GenericFakeChatModel):
    """GenericFakeChatModel refuses bind_tools; agents need it."""

    def bind_tools(self, tools, **kwargs):
        return self


def tool_call(name: str, call_id: str = "1", **args) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


@pytest.fixture(autouse=True)
def isolate_state():
    """Every test starts with a clean repository, empty index and cold factories."""
    crm.set_repository(None)
    vector_store._index = None
    vector_store._status.update(
        ready=False,
        refreshing=False,
        started_at=None,
        pages=0,
        chunks=0,
        last_refresh=None,
        last_error=None,
    )
    for factory in (
        nodes.build_router,
        nodes.build_knowledge_agent,
        nodes.build_customer_support_agent,
    ):
        factory.cache_clear()
    yield
    crm.set_repository(None)


@pytest.fixture
def fake_embeddings():
    return DeterministicFakeEmbedding(size=256)


@pytest.fixture
def merchant_runtime():
    return FakeRuntime(state={"user_id": "cliente1988"})
