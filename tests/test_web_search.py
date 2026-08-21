"""The Tavily payload is not always the documented dict; these shapes crashed production."""

import json

import pytest
from langchain_core.tools import ToolException

from src.tools import knowledge_base


class FakeClient:
    def __init__(self, payload=None, error=None):
        self.payload = payload
        self.error = error
        self.include_domains = None

    def invoke(self, _):
        if self.error is not None:
            raise self.error
        return self.payload


def run_web_search(monkeypatch, payload=None, error=None, **kwargs):
    client = FakeClient(payload=payload, error=error)
    monkeypatch.setattr(knowledge_base, "_build_search_client", lambda: client)
    return json.loads(knowledge_base.web_search.func(query="taxa do pix", **kwargs)), client


@pytest.mark.parametrize(
    ("results", "expected"),
    [
        ([{"title": "t", "url": "u", "content": "c", "score": 1}], 1),
        ("No search results found for 'x'", 0),
        (["https://a", "https://b"], 0),
        ({"0": {"title": "a"}, "1": {"title": "b"}}, 2),
        ([{"title": "a"}, "garbage", None], 1),
        (None, 0),
    ],
    ids=["dicts", "string", "list-of-strings", "dict-of-dicts", "mixed", "empty"],
)
def test_parse_search_results_keeps_only_usable_dicts(results, expected):
    assert len(knowledge_base._parse_search_results({"results": results})) == expected


def test_web_search_returns_trimmed_results(monkeypatch):
    payload = {
        "results": [{"title": "Pix", "url": "https://x", "content": "a" * 5000, "score": 0.9}],
        "answer": "resposta",
    }
    out, _ = run_web_search(monkeypatch, payload=payload)

    assert out["status"] == "ok"
    assert out["count"] == 1
    assert len(out["results"][0]["content"]) == 600


def test_web_search_reports_empty_search_instead_of_crashing(monkeypatch):
    """A raw string used to be iterated character by character: 'str' has no attribute 'get'."""
    out, _ = run_web_search(monkeypatch, payload="No search results found for 'x'")

    assert out["status"] == "no_relevant_results"


def test_web_search_maps_tool_exception_to_no_results(monkeypatch):
    out, _ = run_web_search(monkeypatch, error=ToolException("No search results found"))

    assert out["status"] == "no_relevant_results"


def test_web_search_reports_transport_failure(monkeypatch):
    out, _ = run_web_search(monkeypatch, error=RuntimeError("connection reset"))

    assert out["status"] == "web_search_failed"
    assert "connection reset" in out["error"]


def test_web_search_surfaces_error_payload(monkeypatch):
    out, _ = run_web_search(monkeypatch, payload={"error": "quota exceeded"})

    assert out["status"] == "web_search_failed"


def test_restrict_to_getnet_limits_the_search_to_brazilian_domains(monkeypatch):
    _, client = run_web_search(
        monkeypatch, payload={"results": [{"url": "u", "content": "c"}]}, restrict_to_getnet=True
    )

    assert client.include_domains == ["site.getnet.com.br", "getnet.com.br"]
