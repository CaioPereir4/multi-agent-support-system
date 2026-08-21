from __future__ import annotations

import asyncio
import threading
from functools import lru_cache

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


def is_ready() -> bool:
    """False until the first crawl finishes, so the agent can fall back to web search."""
    return _index is not None


def search(query: str, k: int) -> list[Document]:
    index = _index
    if index is None:
        return []
    return index.similarity_search(query, k=k)


def refresh() -> int:
    """Crawl, re-embed and swap the whole index. Returns the number of chunks indexed."""
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

    logger.info("knowledge base indexed: %s pages, %s chunks", len(pages), len(chunks))
    return len(chunks)


async def refresh_periodically() -> None:
    interval = get_knowledge_base_settings().crawl_interval_seconds
    while True:
        try:
            await asyncio.to_thread(refresh)
        except Exception:
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
    try:
        crawler = TavilyCrawl(
            max_depth=settings.crawl_max_depth,
            limit=settings.crawl_page_limit,
            extract_depth="basic",
        )
        raw = crawler.invoke({"url": settings.crawl_url})
    except Exception as exc:
        logger.warning("tavily_crawl_failed: %s", exc)
        return []

    # TavilyCrawl sets handle_tool_error=True, so an empty crawl comes back as
    # the error message string instead of the documented dict.
    results = raw.get("results") if isinstance(raw, dict) else None
    if not isinstance(results, list):
        logger.warning("tavily_crawl_unexpected_payload: type=%s", type(raw).__name__)
        return []

    return [
        Document(page_content=page["raw_content"], metadata={"url": page.get("url", "")})
        for page in results
        if isinstance(page, dict) and page.get("raw_content")
    ]


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    print(f"chunks indexed: {refresh()}")
