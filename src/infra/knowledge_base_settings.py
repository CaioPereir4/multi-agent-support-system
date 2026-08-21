from functools import lru_cache
from typing import Literal


class KnowledgeBaseSettings:
    max_results: int = 5
    search_depth: Literal["basic", "advanced"] = "basic"


@lru_cache(maxsize=1)
def get_knowledge_base_settings() -> KnowledgeBaseSettings:
    return KnowledgeBaseSettings()
