from pathlib import Path
from functools import lru_cache
import json
import logging

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Determine absolute path to backend/.env so settings load regardless of cwd.
# Config lives at backend/app/config.py, so one parent up is backend/.
env_path = Path(__file__).resolve().parents[1] / ".env"
if not env_path.exists():
    logging.getLogger(__name__).warning(
        f".env file not found at {env_path}; environment variables may be missing"
    )

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=env_path,
        env_file_encoding="utf-8",
        extra="ignore",
    )

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
    azure_storage_container: str = "redacted-jobs"
    azure_storage_account_key: str = ""   # fallback when managed identity lacks permissions

    # Azure Cosmos DB
    cosmos_endpoint: str = ""
    cosmos_db_name: str = "redactor"
    cosmos_key: str = ""   # fallback when managed identity lacks permissions

    # Feature flags
    enable_pii_service: bool = True

    # Authentication
    AZURE_AD_TENANT_ID: str = ""
    AZURE_AD_CLIENT_ID: str = ""
    AZURE_AD_AUDIENCE: str = ""
    DEV_BYPASS: bool = False
    ENV: str = "production"

    # App
    # Read raw env into a string field to avoid pydantic_settings trying to
    # json-decode a complex type too early (which raises JSONDecodeError).
    cors_origins_raw: str | None = Field(default=None, env="CORS_ORIGINS")

    @property
    def cors_origins(self) -> list[str]:
        """Return parsed CORS origins as a list.

        Reads `cors_origins_raw` (string from env/.env) and supports:
        - JSON array (e.g. ["http://localhost:5173"]) 
        - comma-separated values
        - empty string -> empty list
        - missing env -> default localhost origin
        """
        raw = getattr(self, "cors_origins_raw", None)
        if raw is None:
            # Include common local dev ports used by the frontend
            return [
                "http://localhost:5173",
                "http://localhost:3000",
                "http://localhost:3001",
            ]
        raw = raw.strip()
        if raw == "":
            return []
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(x) for x in parsed]
        except Exception:
            pass
        return [item.strip() for item in raw.split(",") if item.strip()]

    @model_validator(mode="after")
    def validate_dev_bypass(self) -> "Settings":
        if self.DEV_BYPASS and self.ENV != "development":
            raise ValueError(
                "DEV_BYPASS=true is only allowed when ENV=development. "
                "Remove DEV_BYPASS or set ENV=development."
            )
        return self

@lru_cache
def get_settings() -> Settings:
    return Settings()
