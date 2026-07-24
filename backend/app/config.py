from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SCALE Finance Agent"
    api_prefix: str = ""
    default_user_id: str = "local-user"
    database_url: str = Field(
        default="postgresql+asyncpg://scale:scale_dev_password@127.0.0.1:5432/scale_finance",
        validation_alias="DATABASE_URL",
    )
    # ── LLM provider selection ─────────────────────────────────────────────────
    llm_provider: str = Field(default="groq", validation_alias="LLM_PROVIDER")
    # ── Groq ───────────────────────────────────────────────────────────────────
    groq_api_key: str | None = Field(default=None, validation_alias="GROQ_API_KEY")
    groq_model: str | None = Field(default=None, validation_alias="GROQ_MODEL")
    # ── Gemini ─────────────────────────────────────────────────────────────────
    gemini_api_key: str | None = Field(default=None, validation_alias="GEMINI_API_KEY")
    gemini_model: str | None = Field(default="gemini-1.5-flash", validation_alias="GEMINI_MODEL")
    # ── Ollama ─────────────────────────────────────────────────────────────────
    ollama_base_url: str = Field(
        default="http://localhost:11434", validation_alias="OLLAMA_BASE_URL"
    )
    ollama_model: str = Field(default="qwen3.5:latest", validation_alias="OLLAMA_MODEL")
    # ── Ollama Cloud ───────────────────────────────────────────────────────────
    ollama_cloud_base_url: str | None = Field(default=None, validation_alias="OLLAMA_CLOUD_BASE_URL")
    ollama_cloud_model: str | None = Field(default="qwen3.5:latest", validation_alias="OLLAMA_CLOUD_MODEL")
    ollama_cloud_api_key: str | None = Field(default=None, validation_alias="OLLAMA_CLOUD_API_KEY")
    # ── Tavily ─────────────────────────────────────────────────────────────────
    tavily_api_key: str | None = Field(default=None, validation_alias="TAVILY_API_KEY")
    # ── ChromaDB ───────────────────────────────────────────────────────────────
    chroma_host: str = Field(default="localhost", validation_alias="CHROMA_HOST")
    chroma_port: int = Field(default=8001, validation_alias="CHROMA_PORT")
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    model_config = SettingsConfigDict(
        env_prefix="SCALE_",
        env_file=(
            str(Path(__file__).resolve().parent.parent.parent / ".env"),
            str(Path(__file__).resolve().parent.parent / ".env"),
            ".env",
            "backend/.env"
        ),
        extra="ignore",
    )


settings = Settings()
