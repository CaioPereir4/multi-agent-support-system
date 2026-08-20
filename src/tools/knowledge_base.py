from asyncio import log
import json
import logging
from langchain.tools import tool
from langchain_tavily import TavilySearch      
from src.infra.knowledge_base_settings import get_knowledge_base_settings

logger = logging.getLogger(__name__)

def _web_search_client():
    settings = get_knowledge_base_settings()
    return TavilySearch(
        tavily_api_key=settings.api_key,
        max_results=settings.max_results,
        search_depth=settings.search_depth
    )

@tool(parse_docstring=True)
def web_search(query: str,restrict_to_getnet: bool = False) -> str:
    """Search the live web with Tavily for information the knowledge base does not
    contain: current events, weather, exchange rates, third-party comparisons, or
    Getnet pages that were not ingested.

    Args:
        query: The search query, in the user's language.
        restrict_to_getnet: Set True to limit results to getnet.net — useful when
            the knowledge base returned nothing but the topic is still Getnet's.
    """ 
    try:
        client = _web_search_client()
        if restrict_to_getnet:
            client.include_domains = ["getnet.net", "www.getnet.net"]
        raw = client.invoke({"query": query})
    except Exception as exc:
        logger.warning("tavily_failed", error=str(exc))
        return json.dumps(
            {"status": "web_search_failed", "error": str(exc)[:300]}, ensure_ascii=False
        )
    
    payload = raw if isinstance(raw, dict) else {"results": raw}
    results = payload.get("results", []) or []
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