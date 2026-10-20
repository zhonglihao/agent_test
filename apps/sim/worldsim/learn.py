"""S2 autonomous learn: gap/curiosity → SearchProvider → gate → memory."""

from __future__ import annotations

import logging
from typing import Any

from .config import AppConfig, SearchConfig
from .memory import gate_memory
from .models import AgentBundle, EpisodicMemory, SimClock, SimState
from .search.providers import SearchHit, SearchProvider, build_search_stack, sanitize_text

logger = logging.getLogger("worldsim.learn")


def _usage(state: SimState, agent_id: str) -> dict[str, Any]:
    bucket = state.search_usage.get(agent_id) or {"sim_day": 0, "count": 0, "cache": {}}
    state.search_usage[agent_id] = bucket
    return bucket


def _budget_ok(bucket: dict[str, Any], sim_day: int, cfg: SearchConfig) -> tuple[bool, str]:
    if bucket.get("sim_day") != sim_day:
        bucket["sim_day"] = sim_day
        bucket["count"] = 0
    if int(bucket.get("count") or 0) >= cfg.max_queries_per_day:
        return False, "daily_budget"
    return True, "ok"


# Mix Instant-Answer-friendly entities (DDG often has Abstract) + zh topics.
_DDG_FRIENDLY = [
    "Python (programming language)",
    "Photosynthesis",
    "Circadian rhythm",
    "DuckDuckGo",
]


def plan_query(
    bundle: AgentBundle,
    *,
    weather: str,
    day_part: str,
    tick_index: int,
) -> tuple[str, str] | None:
    """Return (query, reason_tag) or None if no curiosity this tick."""
    rt = bundle.runtime
    active = [g for g in rt.goal_gaps if g.active]
    if active:
        g = active[0]
        if g.gap_id == "gap_companionship":
            return "loneliness social connection", "curiosity_gap_companionship"
        if g.gap_id == "gap_resource":
            return "food pantry staples", "curiosity_gap_resource"
        if g.gap_id == "gap_commitment":
            return "promise keeping psychology", "curiosity_gap_commitment"

    # Location / weather curiosity on a cadence (every 3rd tick)
    if tick_index % 3 != 0:
        return None

    loc = rt.location_id
    if loc == "outdoors":
        return "urban park", "curiosity_outdoors"
    if loc == "transit":
        return "commuting stress", "curiosity_transit"
    if loc == "workplace":
        return "Pomodoro Technique", "curiosity_workplace"
    if loc == "home" and day_part in ("evening", "night"):
        return "sleep hygiene", "curiosity_home_rest"
    if weather in ("light_rain", "heavy_rain", "cold", "hot"):
        return f"weather {weather}", "curiosity_weather"

    # Ambient: rotate Instant-Answer-friendly topics so default DDG can hit
    return _DDG_FRIENDLY[tick_index % len(_DDG_FRIENDLY)], "curiosity_ambient"


def judge_importance(hits: list[SearchHit], reason_tag: str) -> float:
    """Rule importance — external floor low; gap-related higher."""
    base = 0.32
    if reason_tag.startswith("curiosity_gap_"):
        base = 0.48
    elif reason_tag in ("curiosity_weather", "curiosity_outdoors"):
        base = 0.38
    # slight bump if multiple snippets
    if len(hits) >= 2:
        base = min(0.55, base + 0.04)
    return base


def summarize_hits(hits: list[SearchHit], query: str) -> str:
    if not hits:
        return f"网上想查「{query}」，暂时没查到可用摘要。"
    parts = []
    for h in hits[:2]:
        parts.append(f"[{h.provider}] {h.title}: {h.snippet}")
    body = " ".join(parts)
    return sanitize_text(f"网上学到（查「{query}」）：{body}", 280)


def maybe_external_learn(
    state: SimState,
    agent_id: str,
    cfg: AppConfig,
    *,
    tick_index: int,
    provider: SearchProvider | None = None,
) -> EpisodicMemory | None:
    """≤1 search / tick; budget; cache; WriteGate with source=external_learn."""
    scfg = cfg.search
    if not scfg.enabled:
        return None

    bundle = state.agents[agent_id]
    clock = state.world.clock
    planned = plan_query(
        bundle,
        weather=state.world.weather.value,
        day_part=clock.day_part(),
        tick_index=tick_index,
    )
    if planned is None:
        return None

    query, reason = planned
    bucket = _usage(state, agent_id)
    ok, why = _budget_ok(bucket, clock.day, scfg)
    if not ok:
        logger.info("跳过搜索学习：%s（agent=%s）", why, agent_id)
        mem = gate_memory(
            agent_id=agent_id,
            ts=clock,
            location_id=bundle.runtime.location_id,
            summary=f"想查「{query}」，但今日检索额度用尽，改天再学。",
            importance=0.15,
            affect_tags=["search_budget", reason],
            source="external_learn",
        )
        return mem

    cache: dict[str, Any] = bucket.setdefault("cache", {})
    cache_key = query.strip().lower()
    hits: list[SearchHit] = []
    if cache_key in cache:
        # Already learned this query recently — don't spam identical memories
        logger.info("搜索缓存命中，跳过重复写入：%s", query)
        return None

    stack = provider or build_search_stack(scfg)
    if stack is None:
        return None
    hits = stack.retrieve(query, budget=scfg.max_snippets)
    cache[cache_key] = [
        {
            "title": h.title,
            "snippet": h.snippet,
            "source_url": h.source_url,
            "provider": h.provider,
            "trust": h.trust,
            "fetched_at": h.fetched_at,
        }
        for h in hits
    ]

    bucket["count"] = int(bucket.get("count") or 0) + 1

    if not hits:
        summary = f"网上想查「{query}」，暂时没查到可用摘要（trust=unverified）。"
        importance = 0.18
    else:
        summary = summarize_hits(hits, query)
        importance = judge_importance(hits, reason)

    providers_used = sorted({h.provider for h in hits}) if hits else []
    mem = gate_memory(
        agent_id=agent_id,
        ts=clock,
        location_id=bundle.runtime.location_id,
        summary=summary,
        importance=importance,
        affect_tags=["external_learn", reason, *providers_used],
        source="external_learn",
    )
    if mem is not None:
        logger.info(
            "检索学习写入 memory source=external_learn query=%r providers=%s importance=%.2f",
            query,
            providers_used or ["none"],
            importance,
        )
    return mem
