from functools import lru_cache
from typing import Literal


class KnowledgeBaseSettings:
    max_results: int = 5
    search_depth: Literal["basic", "advanced"] = "basic"

    crawl_url: str = "https://www.getnet.net/"
    crawl_max_depth: int = 2
    crawl_page_limit: int = 30
    crawl_interval_seconds: int = 600

    chunk_size: int = 1200
    chunk_overlap: int = 150
    top_k: int = 4


@lru_cache(maxsize=1)
def get_knowledge_base_settings() -> KnowledgeBaseSettings:
    return KnowledgeBaseSettings()
