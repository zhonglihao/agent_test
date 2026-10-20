"""Load config.example.yaml / config.yaml — keys stay empty by default."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class LlmConfig(BaseModel):
    structured_model: str = "deepseek-flash"
    narrative_model: str = "qwen-plus"
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"


class AffectConfig(BaseModel):
    delta_abs_max: float = 0.25
    decay_lambda: float = 0.08
    bounds: tuple[float, float] = (-1.0, 1.0)


class ApiConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8100


class DuckDuckGoProviderConfig(BaseModel):
    enabled: bool = True
    # Instant Answer API — free, no key. Not a full web SERP.
    endpoint: str = "https://api.duckduckgo.com/"
    timeout_sec: float = 4.0


class WikimediaProviderConfig(BaseModel):
    enabled: bool = True
    endpoint: str = "https://zh.wikipedia.org/w/api.php"
    timeout_sec: float = 4.0


class LocalKnowledgeProviderConfig(BaseModel):
    enabled: bool = True  # offline fallback when network providers return empty


class SearxngProviderConfig(BaseModel):
    """Optional local Docker SearXNG — better full SERP; default OFF (no paid VPS)."""

    enabled: bool = False
    base_url: str = "http://127.0.0.1:8080"
    timeout_sec: float = 5.0


class SearchProvidersConfig(BaseModel):
    duckduckgo: DuckDuckGoProviderConfig = Field(default_factory=DuckDuckGoProviderConfig)
    wikimedia: WikimediaProviderConfig = Field(default_factory=WikimediaProviderConfig)
    local_knowledge: LocalKnowledgeProviderConfig = Field(
        default_factory=LocalKnowledgeProviderConfig
    )
    searxng: SearxngProviderConfig = Field(default_factory=SearxngProviderConfig)


class SearchConfig(BaseModel):
    """S2 free SearchProvider stack — product default on; no paid SERP."""

    enabled: bool = True
    # Locked default third-party (free, no key), wired in tick.
    default_provider: str = "duckduckgo"
    max_queries_per_tick: int = 1
    max_queries_per_day: int = 30
    max_snippets: int = 3
    providers: SearchProvidersConfig = Field(default_factory=SearchProvidersConfig)


class AppConfig(BaseModel):
    timezone: str = "Asia/Shanghai"
    tick_minutes: int = 30
    data_dir: str = "../../data/worldsim"
    default_agent_id: str = "agent_seed_01"
    deepseek_api_key: str = ""
    dashscope_api_key: str = ""
    llm: LlmConfig = Field(default_factory=LlmConfig)
    affect: AffectConfig = Field(default_factory=AffectConfig)
    api: ApiConfig = Field(default_factory=ApiConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)

    def resolve_data_dir(self, base: Path | None = None) -> Path:
        base = base or Path.cwd()
        path = Path(self.data_dir)
        if not path.is_absolute():
            path = (base / path).resolve()
        return path

    @property
    def has_deepseek(self) -> bool:
        return bool(self.deepseek_api_key and self.deepseek_api_key.strip())

    @property
    def has_dashscope(self) -> bool:
        return bool(self.dashscope_api_key and self.dashscope_api_key.strip())


def package_dir() -> Path:
    return Path(__file__).resolve().parent.parent


def default_config_paths() -> list[Path]:
    root = package_dir()
    return [root / "config.yaml", root / "config.example.yaml"]


def load_config(path: Path | None = None) -> AppConfig:
    if path is not None:
        data = _read_yaml(path)
        return AppConfig.model_validate(data)

    for candidate in default_config_paths():
        if candidate.exists():
            data = _read_yaml(candidate)
            return AppConfig.model_validate(data)

    return AppConfig()


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"Config must be a mapping: {path}")
    return raw
