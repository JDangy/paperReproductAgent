from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    github_token: str | None = None
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    openai_base_url: str | None = None
    openai_model: str = "gpt-4o-mini"

    default_workspace: str = "./workspace"
    default_backend: str = "venv"
    default_timeout_minutes: int = 30
    default_max_repair_attempts: int = 5
    default_prefer_cpu: bool = True


settings = Settings()
