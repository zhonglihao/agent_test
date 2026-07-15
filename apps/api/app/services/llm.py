from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.core.config import Settings, get_settings


class LLMError(RuntimeError):
    pass


class LLMClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.settings.llm_api_key}",
            "Content-Type": "application/json",
        }

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
        stream: bool = False,
    ) -> dict[str, Any] | AsyncIterator[str]:
        if stream:
            return self.stream_chat(messages, temperature=temperature)
        payload = {
            "model": self.settings.llm_model,
            "messages": messages,
            "temperature": temperature
            if temperature is not None
            else self.settings.llm_temperature,
            "stream": False,
            "options": {
                "num_ctx": self.settings.llm_num_ctx,
                "keep_alive": self.settings.llm_keep_alive,
            },
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(
                    f"{self.settings.llm_base_url.rstrip('/')}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                )
            except httpx.RequestError as exc:
                raise LLMError(
                    f"无法连接 LLM（{self.settings.llm_base_url}）：{exc}"
                ) from exc
        if response.status_code >= 400:
            raise LLMError(
                f"LLM 返回 {response.status_code}: {response.text[:500]}"
            )
        return response.json()

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
    ) -> AsyncIterator[str]:
        payload = {
            "model": self.settings.llm_model,
            "messages": messages,
            "temperature": temperature
            if temperature is not None
            else self.settings.llm_temperature,
            "stream": True,
            "options": {
                "num_ctx": self.settings.llm_num_ctx,
                "keep_alive": self.settings.llm_keep_alive,
            },
        }
        async with httpx.AsyncClient(timeout=None) as client:
            try:
                async with client.stream(
                    "POST",
                    f"{self.settings.llm_base_url.rstrip('/')}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                ) as response:
                    if response.status_code >= 400:
                        body = await response.aread()
                        raise LLMError(
                            f"LLM 返回 {response.status_code}: {body.decode()[:500]}"
                        )
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        if line.startswith("data: "):
                            data = line[6:].strip()
                        else:
                            data = line.strip()
                        if not data or data == "[DONE]":
                            if data == "[DONE]":
                                break
                            continue
                        try:
                            chunk = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        choices = chunk.get("choices") or []
                        if not choices:
                            continue
                        delta = choices[0].get("delta") or {}
                        content = delta.get("content")
                        if content:
                            yield content
            except httpx.RequestError as exc:
                raise LLMError(
                    f"无法连接 LLM（{self.settings.llm_base_url}）：{exc}"
                ) from exc

    async def complete_text(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.3,
    ) -> str:
        result = await self.chat_completion(
            messages, temperature=temperature, stream=False
        )
        assert isinstance(result, dict)
        choices = result.get("choices") or []
        if not choices:
            return ""
        message = choices[0].get("message") or {}
        return str(message.get("content") or "").strip()
