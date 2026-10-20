"""affect_step — sole ΔPAD write path (M2)."""

from __future__ import annotations

from .config import AffectConfig
from .models import AffectLogEntry, AffectState, Pad, SimClock, WriteActor


def clamp_delta(delta: Pad, abs_max: float) -> Pad:
    def _c(v: float) -> float:
        return max(-abs_max, min(abs_max, v))

    return Pad(p=_c(delta.p), a=_c(delta.a), d=_c(delta.d))


def affect_step(
    affect: AffectState,
    baseline: Pad,
    delta: Pad,
    cause_tags: list[str],
    clock: SimClock,
    cfg: AffectConfig,
    note: str | None = None,
    event_ref: str | None = None,
) -> AffectLogEntry:
    """Appraisal → merge → clamp → decay → persist (in-memory)."""
    lo, hi = cfg.bounds
    delta = clamp_delta(delta, cfg.delta_abs_max)
    pad = (affect.as_pad() + delta).clamp(lo, hi)
    # decay toward baseline
    pad = (pad + baseline.scale(cfg.decay_lambda) + pad.scale(-cfg.decay_lambda)).clamp(lo, hi)
    affect.apply_pad(pad, updated_at=clock.label())
    return AffectLogEntry(
        agent_id=affect.agent_id,
        ts=clock.model_copy(),
        pad=pad,
        delta=delta,
        cause_tags=cause_tags,
        event_ref=event_ref,
        note=note,
        actor=WriteActor.system,
    )


def rule_appraise(
    *,
    energy: float,
    hunger: float,
    location_id: str,
    weather: str,
    day_part: str,
    moved: bool,
    staples: int,
) -> tuple[Pad, list[str], str]:
    """Rule-only appraisal for no-LLM ticks."""
    delta = Pad()
    tags: list[str] = []
    notes: list[str] = []

    if moved:
        delta.a += 0.03
        tags.append("movement")
        notes.append("移动消耗唤醒略升")

    if energy < 35:
        delta.p -= 0.04
        delta.a += 0.02
        tags.append("low_energy")
        notes.append("精力偏低")
    elif energy > 75 and day_part in ("morning", "midday"):
        delta.p += 0.02
        tags.append("rested")

    if hunger > 70:
        delta.p -= 0.05
        delta.a += 0.03
        tags.append("hungry")
        notes.append("饥饿上升")

    if location_id == "home" and day_part in ("evening", "night"):
        delta.a -= 0.02
        delta.p += 0.01
        tags.append("home_rest")
        notes.append("晚间在家偏静")

    if location_id == "workplace":
        delta.a += 0.04
        delta.p -= 0.01
        tags.append("workload")
        notes.append("职场负荷")

    if location_id == "outdoors":
        if weather in ("clear", "cloudy"):
            delta.p += 0.05
            delta.a -= 0.02
            tags.append("outdoors_pleasant")
            notes.append("户外适宜")
        elif weather in ("heavy_rain", "cold"):
            delta.p -= 0.04
            tags.append("outdoors_harsh")
            notes.append("户外天气不佳")

    if staples <= 0:
        delta.p -= 0.03
        tags.append("resource_scarce")
        notes.append("日用品见底")

    if not tags:
        tags.append("ambient")
        notes.append("日常漂移")

    return delta, tags, "；".join(notes)
