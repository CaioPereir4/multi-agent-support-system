"""HTTP contract: the payload the challenge specifies and the health endpoint."""

import asyncio

import main
import pytest
from fastapi.testclient import TestClient

from src.rag import vector_store
from src.services import chat_service


@pytest.fixture
def client(monkeypatch):
    """No background crawling and no Bedrock while testing the HTTP layer."""

    async def no_refresh():
        await asyncio.sleep(0)

    monkeypatch.setattr(main, "refresh_periodically", no_refresh)
    monkeypatch.setattr(
        chat_service, "run_agent", lambda user_question, user_id: f"eco:{user_question}"
    )
    with TestClient(main.app) as test_client:
        yield test_client


def test_chat_answers_the_documented_payload(client):
    response = client.post(
        "/api/chat", json={"message": "Como funciona o Pix?", "user_id": "cliente1988"}
    )

    assert response.status_code == 200
    assert response.json() == {"response": "eco:Como funciona o Pix?"}


def test_chat_rejects_a_payload_without_user_id(client):
    response = client.post("/api/chat", json={"message": "oi"})

    assert response.status_code == 422


def test_health_reports_an_empty_knowledge_base(client):
    body = client.get("/api/health").json()

    assert body["status"] == "ok"
    assert body["knowledge_base"]["ready"] is False
    assert body["knowledge_base"]["chunks"] == 0


def test_health_reports_an_indexed_knowledge_base(client, fake_embeddings, monkeypatch):
    from langchain_core.documents import Document

    monkeypatch.setattr(
        vector_store,
        "_crawl_pages",
        lambda: [
            Document(page_content="pix " * 500, metadata={"url": "https://site.getnet.com.br/pix/"})
        ],
    )
    monkeypatch.setattr(vector_store, "_embeddings", lambda: fake_embeddings)
    vector_store.refresh()

    knowledge_base = client.get("/api/health").json()["knowledge_base"]

    assert knowledge_base["ready"] is True
    assert knowledge_base["pages"] == 1
    assert knowledge_base["last_error"] is None


def test_the_refresh_loop_starts_and_stops_with_the_app(monkeypatch):
    ticks = {"count": 0, "cancelled": False}

    async def counting_loop():
        try:
            while True:
                ticks["count"] += 1
                await asyncio.sleep(0.01)
        except asyncio.CancelledError:
            ticks["cancelled"] = True
            raise

    monkeypatch.setattr(main, "refresh_periodically", counting_loop)
    monkeypatch.setattr(chat_service, "run_agent", lambda user_question, user_id: "ok")

    with TestClient(main.app) as test_client:
        test_client.get("/api/health")

    assert ticks["count"] > 0, "the knowledge base must start indexing on startup"
    assert ticks["cancelled"] is True, "and stop cleanly on shutdown"
