from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[4]


def _existing_or_fallback(value: str, fallback: Path) -> str:
    path = Path(value)
    if path.exists():
        return str(path)
    fallback.mkdir(parents=True, exist_ok=True)
    return str(fallback)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(REPO_ROOT / ".env"), ".env"),
        extra="ignore",
    )

    app_name: str = "AgentTest"
    app_version: str = "0.2.0"
    agenttest_env: str = "development"
    agenttest_log_level: str = "INFO"

    llm_base_url: str = "http://127.0.0.1:11434/v1"
    llm_api_key: str = "ollama"
    llm_model: str = "qwen2.5:7b-instruct-q4_K_M"
    llm_num_ctx: int = 2048
    llm_keep_alive: str = "5m"
    llm_temperature: float = 0.7
    vram_profile: str = "balanced"

    chat_working_turns: int = 16
    chat_summarize_after_turns: int = 24
    chat_max_summary_chars: int = 2000

    data_dir: str = str(REPO_ROOT / "data")
    characters_dir: str = str(REPO_ROOT / "characters")
    db_filename: str = "agenttest.db"

    @field_validator("data_dir", mode="after")
    @classmethod
    def resolve_data_dir(cls, value: str) -> str:
        return _existing_or_fallback(value, REPO_ROOT / "data")

    @field_validator("characters_dir", mode="after")
    @classmethod
    def resolve_characters_dir(cls, value: str) -> str:
        return _existing_or_fallback(value, REPO_ROOT / "characters")

    @property
    def db_path(self) -> Path:
        return Path(self.data_dir) / self.db_filename


@lru_cache
def get_settings() -> Settings:
    return Settings()
