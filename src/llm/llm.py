from langchain_aws import ChatBedrockConverse
from src.infra.llm_settings import get_llm_settings

def build_chat_model():
    llm_settings = get_llm_settings()
    
    return ChatBedrockConverse(
        model=llm_settings.bedrock_model_id,
        region_name=llm_settings.aws_region,
        temperature=llm_settings.bedrock_temperature,
        max_tokens=llm_settings.bedrock_max_tokens
    )