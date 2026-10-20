"""Read-only HTTP API — world / memories / affect. No user writes to memory/PAD."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .config import AppConfig, load_config, package_dir
from .store import SimStore
from .tick import snapshot_dict


def create_app(cfg: AppConfig | None = None) -> FastAPI:
    cfg = cfg or load_config()
    data_dir = cfg.resolve_data_dir(package_dir())
    store = SimStore(data_dir, default_agent_id=cfg.default_agent_id)

    app = FastAPI(
        title="WorldSim Read-Only API",
        version="0.1.0",
        description="只读观测：世界快照 / 记忆 / PAD 轨迹。用户不可写记忆或情绪。",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    def _load():
        return store.ensure()

    def _require_agent(state, agent_id: str):
        if agent_id not in state.agents:
            raise HTTPException(status_code=404, detail=f"unknown agent_id: {agent_id}")

    @app.get("/health")
    def health():
        return {"ok": True, "service": "worldsim"}

    @app.get("/world/snapshot")
    def world_snapshot(agent_id: str = Query(..., description="required AgentId filter")):
        state = _load()
        _require_agent(state, agent_id)
        snap = snapshot_dict(state, agent_id)
        snap["locations"] = [
            {
                "id": loc.id,
                "display_name": loc.display_name,
                "occupant_ids": loc.occupant_ids,
                "attrs": loc.attrs,
            }
            for loc in state.world.locations
        ]
        return snap

    @app.get("/memories")
    def memories(
        agent_id: str = Query(...),
        limit: int = Query(50, ge=1, le=500),
    ):
        state = _load()
        _require_agent(state, agent_id)
        rows = [m for m in state.memories if m.agent_id == agent_id]
        rows = rows[-limit:]
        return {
            "agent_id": agent_id,
            "count": len(rows),
            "items": [m.model_dump(mode="json") for m in rows],
        }

    @app.get("/affect/trajectory")
    def affect_trajectory(
        agent_id: str = Query(...),
        limit: int = Query(100, ge=1, le=1000),
    ):
        state = _load()
        _require_agent(state, agent_id)
        rows = [a for a in state.affect_log if a.agent_id == agent_id]
        rows = rows[-limit:]
        current = state.agents[agent_id].affect
        return {
            "agent_id": agent_id,
            "current": current.model_dump(mode="json"),
            "count": len(rows),
            "items": [a.model_dump(mode="json") for a in rows],
        }

    @app.get("/requests")
    def requests_placeholder(agent_id: str = Query(...)):
        """Intent history — empty until C5."""
        state = _load()
        _require_agent(state, agent_id)
        return {"agent_id": agent_id, "items": [], "note": "Intent 闭环尚未实现（P0）"}

    # Debug / acceptance: advance tick (not a memory/emotion write by user)
    @app.post("/debug/tick")
    def debug_tick(
        agent_id: str = Query(None),
        n: int = Query(1, ge=1, le=48),
    ):
        state = _load()
        aid = agent_id or cfg.default_agent_id
        _require_agent(state, aid)
        from .llm import build_llm_client
        from .tick import tick_n

        llm = build_llm_client(cfg)
        state = tick_n(state, aid, n, cfg, llm=llm)
        store.save(state)
        return snapshot_dict(state, aid)

    def _forbid_user_write():
        raise HTTPException(
            status_code=403,
            detail="用户态禁止写记忆/情绪；纠错仅 system/admin 追加",
        )

    for path in ("/memories", "/memories/{memory_id}", "/affect", "/affect/trajectory"):
        app.add_api_route(path, _forbid_user_write, methods=["POST", "PUT", "PATCH", "DELETE"])

    return app


# uvicorn worldsim.api:app
app = create_app()
