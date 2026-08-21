"""Retrieval rules: a confidence floor, page diversity and an index that survives failure."""

import json

from langchain_core.documents import Document

from src.rag import vector_store
from src.tools import knowledge_base

OFERTAS = "https://site.getnet.com.br/ofertas/"
MAQUININHAS = "https://site.getnet.com.br/todas-as-maquininhas/"
PIX = "https://site.getnet.com.br/pix/"


class FakeIndex:
    def __init__(self, hits):
        self.hits = hits

    def similarity_search_with_score(self, query, k):
        return self.hits[:k]


def doc(url: str, text: str = "conteudo") -> Document:
    return Document(page_content=text, metadata={"url": url})


def test_search_returns_nothing_while_the_index_is_empty():
    assert vector_store.search("pix", k=4, min_score=0.35) == []
    assert vector_store.is_ready() is False


def test_search_drops_hits_below_the_floor():
    vector_store._index = FakeIndex([(doc(PIX), 0.51), (doc(OFERTAS), 0.30)])

    hits = vector_store.search("pix", k=4, min_score=0.35)

    assert [round(score, 2) for _, score in hits] == [0.51]


def test_search_caps_chunks_from_the_same_page():
    """Without the cap the pricing page took every slot and the answer missed the specs."""
    vector_store._index = FakeIndex(
        [
            (doc(OFERTAS, "preco 1"), 0.57),
            (doc(OFERTAS, "preco 2"), 0.53),
            (doc(OFERTAS, "preco 3"), 0.50),
            (doc(MAQUININHAS, "ficha tecnica"), 0.45),
            (doc(PIX, "pix"), 0.41),
        ]
    )

    hits = vector_store.search("get smart", k=4, min_score=0.35, max_per_url=2)

    urls = [d.metadata["url"] for d, _ in hits]
    assert urls.count(OFERTAS) == 2
    assert set(urls) == {OFERTAS, MAQUININHAS, PIX}


def test_refresh_indexes_pages_and_publishes_status(monkeypatch, fake_embeddings):
    monkeypatch.setattr(vector_store, "_crawl_pages", lambda: [doc(PIX, "pix " * 500)])
    monkeypatch.setattr(vector_store, "_embeddings", lambda: fake_embeddings)

    chunks = vector_store.refresh()

    status = vector_store.status()
    assert chunks > 0
    assert status["ready"] is True
    assert status["pages"] == 1
    assert status["chunks"] == chunks
    assert status["last_refresh"] is not None
    assert status["refreshing"] is False


def test_a_failed_refresh_keeps_the_previous_index(monkeypatch, fake_embeddings):
    monkeypatch.setattr(vector_store, "_crawl_pages", lambda: [doc(PIX, "pix " * 500)])
    monkeypatch.setattr(vector_store, "_embeddings", lambda: fake_embeddings)
    vector_store.refresh()

    monkeypatch.setattr(vector_store, "_crawl_pages", list)
    assert vector_store.refresh() == 0

    assert vector_store.is_ready() is True
    assert vector_store.status()["chunks"] > 0


def test_crawler_and_curated_list_are_deduplicated_by_url(monkeypatch):
    crawled = {"results": [{"url": PIX, "raw_content": "do crawler"}]}
    extracted = {
        "results": [
            {"url": PIX, "raw_content": "da lista"},
            {"url": OFERTAS, "raw_content": "ofertas"},
        ]
    }
    monkeypatch.setattr(vector_store, "TavilyCrawl", lambda **kwargs: _Responder(crawled))
    monkeypatch.setattr(vector_store, "TavilyExtract", lambda **kwargs: _Responder(extracted))

    pages = vector_store._crawl_pages()

    assert [p.metadata["url"] for p in pages] == [PIX, OFERTAS]
    assert pages[0].page_content == "do crawler"


def test_a_string_crawl_payload_is_not_treated_as_pages(monkeypatch):
    monkeypatch.setattr(
        vector_store, "TavilyCrawl", lambda **kwargs: _Responder("No crawl results found")
    )
    monkeypatch.setattr(vector_store, "TavilyExtract", lambda **kwargs: _Responder({"results": []}))

    assert vector_store._crawl_pages() == []
    assert "unexpected payload" in vector_store.status()["last_error"]


def test_extract_failure_does_not_discard_crawled_pages(monkeypatch):
    monkeypatch.setattr(
        vector_store,
        "TavilyCrawl",
        lambda **kwargs: _Responder({"results": [{"url": PIX, "raw_content": "x"}]}),
    )
    monkeypatch.setattr(
        vector_store, "TavilyExtract", lambda **kwargs: _Responder(error=RuntimeError("403"))
    )

    pages = vector_store._crawl_pages()

    assert len(pages) == 1
    assert "403" in vector_store.status()["last_error"]


def test_knowledge_base_tool_reports_an_unavailable_index():
    out = json.loads(knowledge_base.knowledge_base_search.func(query="pix"))

    assert out["status"] == "knowledge_base_unavailable"


def test_knowledge_base_tool_reports_weak_matches_so_the_agent_falls_back():
    vector_store._index = FakeIndex([(doc(PIX), 0.20)])

    out = json.loads(knowledge_base.knowledge_base_search.func(query="previsao do tempo"))

    assert out["status"] == "no_relevant_results"


def test_knowledge_base_tool_returns_scored_snippets():
    vector_store._index = FakeIndex([(doc(PIX, "a" * 5000), 0.61)])

    out = json.loads(knowledge_base.knowledge_base_search.func(query="pix"))

    assert out["status"] == "ok"
    assert out["results"][0]["url"] == PIX
    assert out["results"][0]["score"] == 0.61
    assert len(out["results"][0]["content"]) == 600


class _Responder:
    def __init__(self, payload=None, error=None):
        self.payload = payload
        self.error = error

    def invoke(self, _):
        if self.error is not None:
            raise self.error
        return self.payload
