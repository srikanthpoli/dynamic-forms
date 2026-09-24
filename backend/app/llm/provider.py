"""LLM provider factory.

Agents and routers must always obtain a chat model through `get_chat_model()`
instead of importing a provider SDK directly. Switching from xAI Grok to AWS
Bedrock (or any other LangChain-supported provider) only requires changing
LLM_PROVIDER (and its credentials) in the environment - no code changes.
"""

from langchain_core.language_models.chat_models import BaseChatModel

from app.config import get_settings


def get_chat_model(temperature: float = 0.1, json_mode: bool = False) -> BaseChatModel:
    settings = get_settings()

    if settings.llm_provider == "bedrock":
        from langchain_aws import ChatBedrock

        return ChatBedrock(
            model_id=settings.bedrock_model_id,
            region_name=settings.aws_region,
            model_kwargs={"temperature": temperature},
        )

    # default: xAI Grok via its OpenAI-compatible API
    from langchain_openai import ChatOpenAI

    if not settings.xai_api_key:
        raise RuntimeError("XAI_API_KEY is not set")

    extra_kwargs = {}
    if json_mode:
        extra_kwargs["model_kwargs"] = {"response_format": {"type": "json_object"}}

    return ChatOpenAI(
        model=settings.xai_model,
        api_key=settings.xai_api_key,
        base_url=settings.xai_base_url,
        temperature=temperature,
        **extra_kwargs,
    )
