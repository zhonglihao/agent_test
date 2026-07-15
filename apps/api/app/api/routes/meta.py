from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter()


@router.get("/meta")
def meta() -> dict:
    settings = get_settings()
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "env": settings.agenttest_env,
        "vram_profile": settings.vram_profile,
        "llm": {
            "base_url": settings.llm_base_url,
            "model": settings.llm_model,
            "num_ctx": settings.llm_num_ctx,
            "keep_alive": settings.llm_keep_alive,
        },
        "features": {
            "chat": "ready",
            "persona_pack": "ready",
            "tts": "planned",
            "desktop": "planned",
            "office": "planned",
            "research": "planned",
            "meeting": "planned",
            "skills_mcp": "planned",
        },
        "modules": [
            {"id": "chat", "title": "对话陪伴", "status": "ready", "priority": "P0"},
            {"id": "desktop", "title": "桌面管家", "status": "planned", "priority": "P0"},
            {"id": "office", "title": "办公文档", "status": "planned", "priority": "P1"},
            {"id": "research", "title": "网页研究", "status": "planned", "priority": "P1"},
            {"id": "meeting", "title": "会议纪要", "status": "planned", "priority": "P2"},
            {"id": "skills", "title": "Skills / MCP", "status": "planned", "priority": "P0"},
        ],
    }
