
from typing import Literal
import os

class KnowledgeBaseSettings:
    api_key: str = os.getenv("KNOWLEDGE_BASE_API_KEY")
    max_results: int = 5
    search_depth: Literal["basic", "advanced"] = "basic"
    
def get_knowledge_base_settings():
    return KnowledgeBaseSettings()