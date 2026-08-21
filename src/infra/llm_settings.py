from functools import lru_cache


class LLMSettings:
    aws_region: str = "us-east-1"
    bedrock_model_id: str = "global.anthropic.claude-sonnet-4-5-20250929-v1:0"
    bedrock_embedding_model_id: str = "amazon.titan-embed-text-v2:0"
    bedrock_embedding_dimensions: int = 256
    bedrock_max_tokens: int = 2048
    bedrock_temperature: float = 0.5


@lru_cache(maxsize=1)
def get_llm_settings() -> LLMSettings:
    return LLMSettings()
