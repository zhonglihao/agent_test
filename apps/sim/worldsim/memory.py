"""Episodic memory write gate — template memories for no-LLM ticks."""

from __future__ import annotations

from .models import EpisodicMemory, MemoryTier, SimClock, WriteActor


MAX_SUMMARY_LEN = 280


def gate_memory(
    *,
    agent_id: str,
    ts: SimClock,
    location_id: str | None,
    summary: str,
    importance: float,
    affect_tags: list[str] | None = None,
    source: str = "tick",
    retain_category: str | None = None,
) -> EpisodicMemory | None:
    """Whitelist gate: length, agent_id required, no user actor."""
    text = (summary or "").strip()
    if not text or not agent_id:
        return None
    if len(text) > MAX_SUMMARY_LEN:
        text = text[: MAX_SUMMARY_LEN - 1] + "…"
    importance = max(0.0, min(1.0, float(importance)))
    return EpisodicMemory(
        agent_id=agent_id,
        ts=ts.model_copy(),
        location_id=location_id,
        summary=text,
        importance=importance,
        tier=MemoryTier.hot,
        affect_tags=list(affect_tags or []),
        source=source,
        retain_category=retain_category,
        actor=WriteActor.system,
    )


def template_tick_summary(
    *,
    clock_label: str,
    day_part: str,
    location_name: str,
    weather: str,
    energy: float,
    moved_from: str | None,
    moved_to: str | None,
) -> tuple[str, float]:
    """Rule template diary — agent self-score placeholder via heuristics."""
    if moved_from and moved_to and moved_from != moved_to:
        summary = (
            f"{clock_label}（{day_part}）从{moved_from}前往{moved_to}。"
            f"天气{weather}，精力约{energy:.0f}。"
        )
        importance = 0.45
    else:
        summary = (
            f"{clock_label}（{day_part}）仍在{location_name}。"
            f"天气{weather}，精力约{energy:.0f}。"
        )
        importance = 0.25
    return summary, importance
