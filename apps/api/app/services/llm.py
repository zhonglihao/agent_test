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

    def _endpoint(self) -> str:
        return f"{self.settings.llm_base_url.rstrip('/')}/chat/completions"

    def _base_payload(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float | None,
        stream: bool,
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.settings.llm_model,
            "messages": messages,
            "temperature": temperature
            if temperature is not None
            else self.settings.llm_temperature,
            "stream": stream,
            "options": {
                "num_ctx": self.settings.llm_num_ctx,
                "keep_alive": self.settings.llm_keep_alive,
            },
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        return payload

    async def chat_completion(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float | None = None,
        stream: bool = False,
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any] | AsyncIterator[str]:
        if stream:
            return self.stream_chat(messages, temperature=temperature, tools=None)
        payload = self._base_payload(
            messages, temperature=temperature, stream=False, tools=tools
        )
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(
                    self._endpoint(),
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
        messages: list[dict[str, Any]],
        *,
        temperature: float | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[str]:
        # Streaming + tools is unreliable across local servers; prefer no tools here.
        payload = self._base_payload(
            messages, temperature=temperature, stream=True, tools=tools
        )
        async with httpx.AsyncClient(timeout=None) as client:
            try:
                async with client.stream(
                    "POST",
                    self._endpoint(),
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

    async def complete_message(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        result = await self.chat_completion(
            messages, temperature=temperature, stream=False, tools=tools
        )
        assert isinstance(result, dict)
        choices = result.get("choices") or []
        if not choices:
            return {"role": "assistant", "content": ""}
        message = choices[0].get("message") or {}
        return message

    async def complete_text(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float = 0.3,
    ) -> str:
        message = await self.complete_message(messages, temperature=temperature)
        return str(message.get("content") or "").strip()
