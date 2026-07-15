from __future__ import annotations

import asyncio
import io
import tempfile
from pathlib import Path
from typing import Any

import edge_tts

from app.core.config import get_settings
from app.services.persona import PersonaService


class TTSError(RuntimeError):
    pass


class TTSService:
    def __init__(self, personas: PersonaService | None = None) -> None:
        self.personas = personas or PersonaService()
        self.settings = get_settings()

    def resolve_voice(self, persona_id: str | None, voice_id: str | None) -> str:
        if voice_id:
            return voice_id
        pack = self.personas.get_pack(persona_id)
        return pack.voice.voice_id or "zh-CN-XiaoxiaoNeural"

    async def synthesize(
        self,
        text: str,
        *,
        persona_id: str | None = None,
        voice_id: str | None = None,
        rate: str = "+0%",
    ) -> tuple[bytes, str, str]:
        """Returns (audio_bytes, media_type, provider_used)."""
        clean = text.strip()
        if not clean:
            raise TTSError("文本为空")

        provider = (self.settings.tts_provider or "auto").lower()
        voice = self.resolve_voice(persona_id, voice_id)
        errors: list[str] = []

        if provider in {"auto", "edge"}:
            try:
                audio = await self._edge_synthesize(clean, voice, rate)
                return audio, "audio/mpeg", "edge-tts"
            except Exception as exc:  # noqa: BLE001
                errors.append(f"edge-tts: {exc}")
                if provider == "edge":
                    raise TTSError(f"edge-tts 合成失败：{exc}") from exc

        if provider in {"auto", "sapi"}:
            try:
                audio = await asyncio.to_thread(self._sapi_synthesize, clean)
                return audio, "audio/wav", "sapi"
            except Exception as exc:  # noqa: BLE001
                errors.append(f"sapi: {exc}")
                if provider == "sapi":
                    raise TTSError(f"SAPI 合成失败：{exc}") from exc

        raise TTSError("所有 TTS 后端均失败：" + " | ".join(errors))

    async def _edge_synthesize(self, text: str, voice: str, rate: str) -> bytes:
        communicate = edge_tts.Communicate(text, voice, rate=rate)
        buffer = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                buffer.write(chunk["data"])
        audio = buffer.getvalue()
        if not audio:
            raise TTSError("edge-tts 未返回音频")
        return audio

    def _sapi_synthesize(self, text: str) -> bytes:
        try:
            import pyttsx3
        except ImportError as exc:
            raise TTSError("未安装 pyttsx3，无法使用本机 SAPI 回退") from exc

        engine = pyttsx3.init()
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            path = tmp.name
        try:
            engine.save_to_file(text, path)
            engine.runAndWait()
            data = Path(path).read_bytes()
            if not data:
                raise TTSError("SAPI 未生成音频")
            return data
        finally:
            Path(path).unlink(missing_ok=True)
            try:
                engine.stop()
            except Exception:  # noqa: BLE001
                pass

    async def list_zh_voices(self) -> list[dict[str, Any]]:
        try:
            voices = await edge_tts.list_voices()
        except Exception:
            return [
                {
                    "id": "sapi-default",
                    "locale": "zh-CN",
                    "gender": "Unknown",
                    "friendly_name": "Windows SAPI 默认",
                    "provider": "sapi",
                }
            ]
        result = []
        for item in voices:
            locale = str(item.get("Locale") or "")
            if not locale.startswith("zh-"):
                continue
            result.append(
                {
                    "id": item.get("ShortName"),
                    "locale": locale,
                    "gender": item.get("Gender"),
                    "friendly_name": item.get("FriendlyName"),
                    "provider": "edge-tts",
                }
            )
        return result
