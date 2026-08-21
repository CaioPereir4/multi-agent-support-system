import json

from langchain.tools import tool
from langchain_core.tools import ToolException
from langchain_tavily import TavilySearch

from src.infra.knowledge_base_settings import get_knowledge_base_settings
from src.infra.logger import get_logger
from src.rag import vector_store

logger = get_logger(__name__)


def _parse_search_results(payload: dict) -> list[dict]:
    results = payload.get("results") or []
    if isinstance(results, dict):
        results = list(results.values())
    if isinstance(results, (str, bytes)) or not isinstance(results, (list, tuple)):
        results = []
    return [r for r in results if isinstance(r, dict)]


def _build_search_client():
    settings = get_knowledge_base_settings()
    return TavilySearch(max_results=settings.max_results, search_depth=settings.search_depth)


@tool(parse_docstring=True)
def knowledge_base_search(query: str) -> str:
    """Search the getnet.net pages ingested into the knowledge base. Use this first for
    anything about Getnet itself: card machines, fees, Pix, payment links, receivables
    advance (antecipacao) or crediario.

    Args:
        query: The search query, in the user's language.
    """
    if not vector_store.is_ready():
        return json.dumps({"status": "knowledge_base_unavailable"}, ensure_ascii=False)

    hits = vector_store.search(query, k=get_knowledge_base_settings().top_k)
    if not hits:
        return json.dumps({"status": "no_relevant_results", "query": query}, ensure_ascii=False)

    return json.dumps(
        {
            "status": "ok",
            "count": len(hits),
            "results": [
                {
                    "url": doc.metadata.get("url", ""),
                    "content": doc.page_content[:1200],
                }
                for doc in hits
            ],
        },
        ensure_ascii=False,
    )


@tool(parse_docstring=True)
def web_search(query: str, restrict_to_getnet: bool = False) -> str:
    """Search the live web with Tavily for information the knowledge base does not
    contain: current events, weather, exchange rates, third-party comparisons, or
    Getnet pages that were not ingested.

    Args:
        query: The search query, in the user's language.
        restrict_to_getnet: Set True to limit results to getnet.net — useful when
            the knowledge base returned nothing but the topic is still Getnet's.
    """
    try:
        client = _build_search_client()
        if restrict_to_getnet:
            client.include_domains = ["getnet.net", "www.getnet.net"]
        raw = client.invoke({"query": query})
    except ToolException as exc:
        logger.warning("tavily_no_results: %s", exc)
        return json.dumps({"status": "no_relevant_results", "query": query}, ensure_ascii=False)
    except Exception as exc:
        logger.warning("tavily_failed: %s", exc)
        return json.dumps(
            {"status": "web_search_failed", "error": str(exc)[:300]}, ensure_ascii=False
        )

    payload = raw if isinstance(raw, dict) else {"results": raw}
    if payload.get("error"):
        logger.warning("tavily_failed: %s", payload["error"])
        return json.dumps(
            {"status": "web_search_failed", "error": str(payload["error"])[:300]},
            ensure_ascii=False,
        )

    results = _parse_search_results(payload)
    if not results:
        logger.warning("tavily_unexpected_payload: type=%s preview=%.300s", type(raw).__name__, raw)
        return json.dumps({"status": "no_relevant_results", "query": query}, ensure_ascii=False)

    trimmed = [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "score": r.get("score"),
            "content": (r.get("content") or "")[:1200],
        }
        for r in results
    ]

    return json.dumps(
        {
            "status": "ok",
            "answer": payload.get("answer"),
            "count": len(trimmed),
            "results": trimmed,
        },
        ensure_ascii=False,
    )
