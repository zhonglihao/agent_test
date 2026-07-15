from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "AgentTest"
    app_version: str = "0.1.0"
    agenttest_env: str = "development"
    agenttest_log_level: str = "INFO"

    llm_base_url: str = "http://host.docker.internal:11434/v1"
    llm_api_key: str = "ollama"
    llm_model: str = "qwen2.5:7b-instruct-q4_K_M"
    llm_num_ctx: int = 2048
    llm_keep_alive: str = "5m"
    vram_profile: str = "balanced"

    data_dir: str = "/data"
    characters_dir: str = "/app/characters"


@lru_cache
def get_settings() -> Settings:
    return Settings()
