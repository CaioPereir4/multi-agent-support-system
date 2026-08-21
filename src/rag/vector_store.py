from __future__ import annotations

import asyncio
import threading
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

from langchain_aws import BedrockEmbeddings
from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_tavily import TavilyCrawl
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.infra.knowledge_base_settings import get_knowledge_base_settings
from src.infra.llm_settings import get_llm_settings
from src.infra.logger import get_logger

logger = get_logger(__name__)

_index: InMemoryVectorStore | None = None
_index_lock = threading.Lock()
_status: dict[str, Any] = {
    "ready": False,
    "refreshing": False,
    "started_at": None,
    "pages": 0,
    "chunks": 0,
    "last_refresh": None,
    "last_error": None,
}


def status() -> dict[str, Any]:
    """Exposed by /api/health: without it an empty index is invisible from outside."""
    return dict(_status)


def is_ready() -> bool:
    """False until the first crawl finishes, so the agent can fall back to web search."""
    return _index is not None


def search(query: str, k: int, min_score: float) -> list[tuple[Document, float]]:
    """Nearest chunks above `min_score`. Cosine similarity, so scores run from -1 to 1.

    Without the floor the store always returns its k nearest chunks, however irrelevant
    they are, and the agent keeps reformulating instead of falling back to web search.
    """
    index = _index
    if index is None:
        return []

    hits = index.similarity_search_with_score(query, k=k)
    for doc, score in hits:
        logger.info("kb_hit score=%.3f url=%s", score, doc.metadata.get("url", ""))

    return [(doc, score) for doc, score in hits if score >= min_score]


def refresh() -> int:
    """Crawl, re-embed and swap the whole index. Returns the number of chunks indexed."""
    global _index

    _status.update(refreshing=True, started_at=datetime.now(UTC).isoformat(timespec="seconds"))
    logger.info("knowledge base refresh started")
    try:
        return _refresh()
    finally:
        _status["refreshing"] = False


def _refresh() -> int:
    global _index

    pages = _crawl_pages()
    if not pages:
        logger.warning("crawl returned no pages; keeping the previous index")
        return 0

    settings = get_knowledge_base_settings()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    chunks = splitter.split_documents(pages)

    index = InMemoryVectorStore(_embeddings())
    index.add_documents(chunks)

    with _index_lock:
        _index = index

    _status.update(
        ready=True,
        pages=len(pages),
        chunks=len(chunks),
        last_refresh=datetime.now(UTC).isoformat(timespec="seconds"),
        last_error=None,
    )
    logger.info("knowledge base indexed: %s pages, %s chunks", len(pages), len(chunks))
    return len(chunks)


async def refresh_periodically() -> None:
    interval = get_knowledge_base_settings().crawl_interval_seconds
    while True:
        try:
            await asyncio.to_thread(refresh)
        except Exception as exc:
            # Embeddings blow up here, not in the crawl: without this the failure
            # is invisible on /health.
            _status["last_error"] = f"refresh: {str(exc)[:200]}"
            logger.exception("knowledge base refresh failed")
        await asyncio.sleep(interval)


@lru_cache(maxsize=1)
def _embeddings() -> BedrockEmbeddings:
    settings = get_llm_settings()
    return BedrockEmbeddings(
        model_id=settings.bedrock_embedding_model_id,
        region_name=settings.aws_region,
        dimensions=settings.bedrock_embedding_dimensions,
        normalize=True,
    )


def _crawl_pages() -> list[Document]:
    settings = get_knowledge_base_settings()
    pages: list[Document] = []
    for url in settings.crawl_urls:
        pages.extend(_crawl_site(url, settings))
    return pages


def _crawl_site(url: str, settings: Any) -> list[Document]:
    try:
        crawler = TavilyCrawl(
            max_depth=settings.crawl_max_depth,
            limit=settings.crawl_page_limit,
            extract_depth="basic",
        )
        raw = crawler.invoke({"url": url})
    except Exception as exc:
        logger.warning("tavily_crawl_failed url=%s: %s", url, exc)
        _status["last_error"] = f"{url}: {str(exc)[:200]}"
        return []

    # TavilyCrawl sets handle_tool_error=True, so an empty crawl comes back as
    # the error message string instead of the documented dict.
    results = raw.get("results") if isinstance(raw, dict) else None
    if not isinstance(results, list):
        logger.warning("tavily_crawl_unexpected_payload url=%s type=%s", url, type(raw).__name__)
        _status["last_error"] = f"{url}: unexpected payload {type(raw).__name__}"
        return []

    documents = [
        Document(page_content=page["raw_content"], metadata={"url": page.get("url", url)})
        for page in results
        if isinstance(page, dict) and page.get("raw_content")
    ]
    logger.info("crawled %s pages from %s", len(documents), url)
    return documents


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    print(f"chunks indexed: {refresh()}")
