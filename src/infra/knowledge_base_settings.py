from functools import lru_cache
from typing import Literal


class KnowledgeBaseSettings:
    max_results: int = 3
    search_depth: Literal["basic", "advanced"] = "basic"

    # Brazil only for now: the other country sites (uy, ar, cl, mx) answer in the
    # wrong language about products this merchant does not have, and they were
    # crowding the index. Getnet Brazil lives on its own domain.
    crawl_urls: tuple[str, ...] = ("https://site.getnet.com.br/",)

    # Product pages the index must always contain, whatever the crawler discovers.
    extract_urls: tuple[str, ...] = (
        "https://site.getnet.com.br/todas-as-maquininhas/",
        "https://site.getnet.com.br/pix/",
        "https://site.getnet.com.br/link-de-pagamento/",
        "https://site.getnet.com.br/crediario/",
        "https://site.getnet.com.br/get-tap/",
        "https://site.getnet.com.br/conta-digital/",
        "https://site.getnet.com.br/ofertas/",
    )

    crawl_max_depth: int = 2
    crawl_page_limit: int = 20
    crawl_interval_seconds: int = 86400

    chunk_size: int = 1200
    chunk_overlap: int = 150

    top_k: int = 4
    max_chunks_per_url: int = 2
    min_score: float = 0.35
    snippet_chars: int = 600


@lru_cache(maxsize=1)
def get_knowledge_base_settings() -> KnowledgeBaseSettings:
    return KnowledgeBaseSettings()
