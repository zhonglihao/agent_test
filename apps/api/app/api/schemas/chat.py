from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    title: str = "新对话"
    persona_id: str | None = None


class SessionUpdate(BaseModel):
    title: str | None = None
    persona_id: str | None = None


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    persona_id: str | None = None


class MemoryCreate(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    scope_key: str | None = None


def session_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "persona_id": row.get("persona_id"),
        "summary": row.get("summary") or "",
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
