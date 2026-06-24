from __future__ import annotations

from app.config import Settings


def test_settings_load_backend_env_file() -> None:
    settings = Settings(_env_file="backend/.env")

    assert settings.chat_orchestration == "simple_llm_tools"
    assert settings.groq_api_key
    assert settings.groq_model
