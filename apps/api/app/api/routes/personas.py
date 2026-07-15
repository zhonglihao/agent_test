from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.services.persona import PersonaService

router = APIRouter(prefix="/personas", tags=["personas"])


@router.get("")
def list_personas() -> dict[str, Any]:
    packs = PersonaService().list_packs()
    return {
        "items": [
            {
                "id": p.id,
                "name": p.name,
                "version": p.version,
                "description": p.description,
                "greeting": p.greeting,
                "style": p.style,
                "memory_scope": p.memory_scope,
                "voice": p.voice.model_dump(),
                "boundaries": p.boundaries.model_dump(),
                "sampling": p.sampling.model_dump(),
            }
            for p in packs
        ]
    }


@router.get("/{persona_id}")
def get_persona(persona_id: str) -> dict[str, Any]:
    service = PersonaService()
    known = {p.id for p in service.list_packs()}
    if persona_id not in known:
        raise HTTPException(status_code=404, detail="角色不存在")
    pack = service.get_pack(persona_id)
    return {
        "id": pack.id,
        "name": pack.name,
        "version": pack.version,
        "description": pack.description,
        "system_prompt": pack.system_prompt,
        "greeting": pack.greeting,
        "style": pack.style,
        "memory_scope": pack.memory_scope,
        "voice": pack.voice.model_dump(),
        "boundaries": pack.boundaries.model_dump(),
        "sampling": pack.sampling.model_dump(),
        "path": pack.path,
    }
