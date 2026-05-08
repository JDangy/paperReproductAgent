from __future__ import annotations

from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    github_token: Optional[str] = None
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    openai_base_url: Optional[str] = None
    openai_model: str = "gpt-4o-mini"

    default_workspace: str = "./workspace"
    default_backend: str = "conda"
    default_timeout_minutes: int = 30
    default_max_repair_attempts: int = 5
    default_prefer_cpu: bool = True


settings = Settings()
