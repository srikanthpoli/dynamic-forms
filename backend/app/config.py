from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    log_level: str = "INFO"

    # LLM provider selection: "grok" (xAI, default) or "bedrock" (AWS)
    llm_provider: str = "grok"

    # xAI Grok (OpenAI-compatible API)
    xai_api_key: str | None = None
    xai_base_url: str = "https://api.x.ai/v1"
    xai_model: str = "grok-4.20-0309-non-reasoning"

    # AWS Bedrock
    bedrock_model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    aws_region: str = "us-east-1"

    # Local embeddings (HuggingFace, no external API calls)
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Local vector DB (Chroma) built from the Angular Material spec file
    chroma_persist_dir: str = "app/data/chroma"
    material_spec_path: str = "app/data/angular_material_capabilities.json"

    # Postgres
    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5433/dynamic_forms"

    # CORS
    cors_origins: list[str] = ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
