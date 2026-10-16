from functools import lru_cache
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parents[2] / '.env', extra='ignore', env_ignore_empty=True)
    database_url: str = 'sqlite:///./biddy.db'
    biddy_access_token: str = 'local-development-token-change-me'
    biddy_workspace_id: str = 'primary-workspace'
    cors_origins: str = 'http://localhost:5173,http://localhost:8080'
    llm_provider: str = 'rules'
    llm_api_key: str = ''
    llm_model: str = ''
    llm_base_url: str = 'https://api.openai.com/v1'
    llm_concurrency: int = Field(default=3, ge=1)
    llm_input_usd_per_million: float | None = None
    llm_output_usd_per_million: float | None = None
    max_upload_bytes: int = 10 * 1024 * 1024
    max_document_chars: int = 180_000
    job_max_attempts: int = Field(default=3, ge=1)
    job_lease_seconds: int = Field(default=900, ge=3)
    sam_api_key: str = ''


@lru_cache
def settings():
    return Settings()
