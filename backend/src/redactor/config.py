from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Azure Document Intelligence
    azure_doc_intel_endpoint: str = ""
    azure_doc_intel_key: str = ""

    # Azure OpenAI
    azure_openai_endpoint: str = ""
    azure_openai_key: str = ""
    azure_openai_deployment: str = "gpt-4o"
    azure_openai_api_version: str = "2024-02-01"

    # Azure Language Service
    azure_language_endpoint: str = ""
    azure_language_key: str = ""

    # Azure Blob Storage
    azure_storage_account_url: str = ""
    azure_storage_container: str = "redaction-jobs"

    # Feature flags
    enable_pii_service: bool = True

    # App
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

@lru_cache
def get_settings() -> Settings:
    return Settings()
