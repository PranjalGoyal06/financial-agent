from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SCALE Finance Agent"
    api_v1_prefix: str = "/api/v1"
    chat_orchestration: str = "reactive_graph"
    groq_api_key: str | None = Field(default=None, validation_alias="GROQ_API_KEY")
    groq_model: str | None = Field(default=None, validation_alias="GROQ_MODEL")

    @field_validator("chat_orchestration")
    @classmethod
    def _normalise_chat_orchestration(cls, value: str) -> str:
        return value.strip().lower()

    model_config = SettingsConfigDict(
        env_prefix="SCALE_",
        env_file=(".env", "backend/.env"),
        extra="ignore",
    )


settings = Settings()
