from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.api.schemas.chat import (
    ChatRequest,
    MemoryCreate,
    SessionCreate,
    SessionUpdate,
    session_to_dict,
)
from app.core.config import get_settings
from app.db.sqlite import Database
from app.services.chat import ChatService
from app.services.persona import PersonaService

router = APIRouter(prefix="/chat", tags=["chat"])


def _db() -> Database:
    return Database()


def _chat() -> ChatService:
    return ChatService(db=_db())


@router.get("/sessions")
def list_sessions() -> dict[str, Any]:
    return {"items": [session_to_dict(s) for s in _db().list_sessions()]}


@router.post("/sessions")
def create_session(body: SessionCreate) -> dict[str, Any]:
    personas = PersonaService()
    if body.persona_id:
        known = {p.id for p in personas.list_packs()}
        if body.persona_id not in known:
            raise HTTPException(status_code=404, detail="角色不存在")
    session = _db().create_session(title=body.title, persona_id=body.persona_id)
    return session_to_dict(session)


@router.get("/sessions/{session_id}")
def get_session(session_id: str) -> dict[str, Any]:
    session = _db().get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    messages = _db().list_messages(session_id)
    return {
        "session": session_to_dict(session),
        "messages": messages,
    }


@router.patch("/sessions/{session_id}")
def update_session(session_id: str, body: SessionUpdate) -> dict[str, Any]:
    session = _db().update_session(
        session_id,
        title=body.title,
        persona_id=body.persona_id,
    )
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return session_to_dict(session)


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str) -> dict[str, str]:
    if not _db().delete_session(session_id):
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"status": "deleted"}


@router.post("/sessions/{session_id}/messages")
async def post_message(session_id: str, body: ChatRequest) -> StreamingResponse:
    if not _db().get_session(session_id):
        raise HTTPException(status_code=404, detail="会话不存在")

    async def event_generator():
        async for item in _chat().stream_reply(
            session_id, body.message.strip(), persona_id=body.persona_id
        ):
            payload = json.dumps(item["data"], ensure_ascii=False)
            yield f"event: {item['event']}\ndata: {payload}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/memories")
def list_memories(scope_key: str = "shared") -> dict[str, Any]:
    return {"items": _db().list_memories(scope_key)}


@router.post("/memories")
def create_memory(body: MemoryCreate) -> dict[str, Any]:
    scope = body.scope_key or "shared"
    return _db().add_memory(scope, body.content)


@router.delete("/memories/{memory_id}")
def delete_memory(memory_id: str) -> dict[str, str]:
    if not _db().delete_memory(memory_id):
        raise HTTPException(status_code=404, detail="记忆不存在")
    return {"status": "deleted"}


@router.get("/config")
def chat_config() -> dict[str, Any]:
    settings = get_settings()
    return {
        "working_turns": settings.chat_working_turns,
        "summarize_after_turns": settings.chat_summarize_after_turns,
        "num_ctx": settings.llm_num_ctx,
        "model": settings.llm_model,
        "vram_profile": settings.vram_profile,
    }
