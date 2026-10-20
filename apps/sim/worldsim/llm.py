"""LLM adapter interface — DeepSeek Flash (structured) + DashScope Qwen-Plus (narrative).

No key → skip / mock; never bind business to a vendor SDK.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from .config import AppConfig

logger = logging.getLogger("worldsim.llm")


class LlmClient(ABC):
    @abstractmethod
    def structured(self, prompt: str, schema_hint: str | None = None) -> dict[str, Any] | None:
        """Flash path: cognize / appraisal JSON."""

    @abstractmethod
    def narrative(self, prompt: str) -> str | None:
        """Plus path: speech / diary narrative."""


class NullLlmClient(LlmClient):
    """Used when API keys are empty — logs skip and returns None."""

    def __init__(self) -> None:
        self._logged_structured = False
        self._logged_narrative = False

    def structured(self, prompt: str, schema_hint: str | None = None) -> dict[str, Any] | None:
        if not self._logged_structured:
            logger.info("跳过 LLM（structured / Flash）：无 deepseek_api_key，使用规则层")
            self._logged_structured = True
        return None

    def narrative(self, prompt: str) -> str | None:
        if not self._logged_narrative:
            logger.info("跳过 LLM（narrative / Plus）：无 dashscope_api_key，使用模板叙事")
            self._logged_narrative = True
        return None


class HttpLlmClient(LlmClient):
    """Minimal OpenAI-compatible client; only called when keys present."""

    def __init__(self, cfg: AppConfig) -> None:
        self.cfg = cfg

    def structured(self, prompt: str, schema_hint: str | None = None) -> dict[str, Any] | None:
        if not self.cfg.has_deepseek:
            logger.info("跳过 LLM（structured / Flash）：无 deepseek_api_key")
            return None
        # Reserved: real HTTP call when key is configured.
        logger.warning(
            "LLM structured 已配置 key，但 MVP tick 仍走规则层；"
            "完整 cognize 接入见后续 Intent 阶段"
        )
        return None

    def narrative(self, prompt: str) -> str | None:
        if not self.cfg.has_dashscope:
            logger.info("跳过 LLM（narrative / Plus）：无 dashscope_api_key")
            return None
        logger.warning(
            "LLM narrative 已配置 key，但 MVP tick 仍走模板日记；"
            "完整叙事接入见后续阶段"
        )
        return None


def build_llm_client(cfg: AppConfig) -> LlmClient:
    if cfg.has_deepseek or cfg.has_dashscope:
        return HttpLlmClient(cfg)
    return NullLlmClient()
