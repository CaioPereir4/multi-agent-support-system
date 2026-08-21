from functools import lru_cache
from typing import Literal


class KnowledgeBaseSettings:
    max_results: int = 3
    search_depth: Literal["basic", "advanced"] = "basic"

    # www.getnet.net is only a country picker: Brazil lives on another domain and
    # TavilyCrawl does not follow external links, so each site is a seed of its own.
    crawl_urls: tuple[str, ...] = (
        "https://site.getnet.com.br/",
        "https://www.getnet.net/en",
    )
    crawl_max_depth: int = 2
    crawl_page_limit: int = 15
    crawl_interval_seconds: int = 86400

    chunk_size: int = 1200
    chunk_overlap: int = 150

    top_k: int = 3
    min_score: float = 0.35
    snippet_chars: int = 600


@lru_cache(maxsize=1)
def get_knowledge_base_settings() -> KnowledgeBaseSettings:
    return KnowledgeBaseSettings()
