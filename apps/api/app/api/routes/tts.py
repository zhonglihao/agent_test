from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.services.tts import TTSError, TTSService

router = APIRouter(prefix="/tts", tags=["tts"])


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    persona_id: str | None = None
    voice_id: str | None = None
    rate: str = "+0%"


@router.get("/voices")
async def list_voices() -> dict[str, Any]:
    try:
        items = await TTSService().list_zh_voices()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"无法拉取声线列表：{exc}") from exc
    return {"items": items}


@router.post("/speak")
async def speak(body: SpeakRequest) -> Response:
    try:
        audio, media_type, provider = await TTSService().synthesize(
            body.text,
            persona_id=body.persona_id,
            voice_id=body.voice_id,
            rate=body.rate,
        )
    except TTSError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(
        content=audio,
        media_type=media_type,
        headers={"X-TTS-Provider": provider},
    )