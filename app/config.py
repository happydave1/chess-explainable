from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    stockfish_path: str = "stockfish"
    engine_depth: int = 14
    engine_time_limit_s: Optional[float] = None

    slm_base_url: str = "http://127.0.0.1:11434/v1"
    slm_model: str = "llama3.2"
    slm_api_key: Optional[str] = None
    slm_timeout_s: float = 120.0
    # Hard cap on completion length (OpenAI-compatible `max_tokens`; Ollama honors it)
    slm_max_tokens: int = 256


settings = Settings()
