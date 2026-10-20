"""Path A tick(world, agent_id) — rules-first, optional LLM skip."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from .affect import affect_step, rule_appraise
from .config import AppConfig
from .llm import LlmClient, build_llm_client
from .memory import gate_memory, template_tick_summary
from .models import AgentBundle, SimState

logger = logging.getLogger("worldsim.tick")

# Generic adult schedule anchors (world-pack §3)
# night sleep preference: 23:00–07:00 → home
SLEEP_START = 23 * 60
SLEEP_END = 7 * 60


def _in_sleep_window(minute_of_day: int) -> bool:
    return minute_of_day >= SLEEP_START or minute_of_day < SLEEP_END


def _pick_next_location(bundle: AgentBundle, state: SimState) -> str | None:
    """At most one edge per tick; schedule heuristics without LLM."""
    runtime = bundle.runtime
    loc = state.world.location(runtime.location_id)
    clock = state.world.clock
    home = bundle.profile.home_location_id

    if _in_sleep_window(clock.minute_of_day):
        if runtime.location_id != home:
            # move toward home if edge exists, else stay
            for edge in loc.edges:
                if edge.to == home:
                    return home
            # try neighborhood as hop
            for edge in loc.edges:
                if edge.to == "neighborhood":
                    return "neighborhood"
        return None

    # Morning commute toward workplace
    if clock.day_part() in ("dawn", "morning") and runtime.location_id != "workplace":
        dest = runtime.planned_destination or "workplace"
        for edge in loc.edges:
            if edge.to == dest:
                return dest
        # BFS one hop toward dest via known graph
        prefer = {
            "home": "neighborhood",
            "neighborhood": "transit",
            "transit": "workplace",
            "commerce": "neighborhood",
            "outdoors": "neighborhood",
        }
        hop = prefer.get(runtime.location_id)
        if hop and any(e.to == hop for e in loc.edges):
            return hop

    # Midday / afternoon at workplace — stay or short commerce if hungry
    if runtime.location_id == "workplace":
        if runtime.hunger > 75 and any(e.to == "commerce" for e in loc.edges):
            return "commerce"
        return None

    # Evening: head home
    if clock.day_part() in ("evening", "night") and runtime.location_id != home:
        prefer_home = {
            "workplace": "transit",
            "transit": "neighborhood",
            "neighborhood": "home",
            "commerce": "neighborhood",
            "outdoors": "neighborhood",
        }
        hop = prefer_home.get(runtime.location_id)
        if hop and any(e.to == hop for e in loc.edges):
            return hop

    # Low staples → commerce
    if runtime.inventory_staples <= 0:
        for edge in loc.edges:
            if edge.to == "commerce":
                return "commerce"

    return None


def _apply_body_rules(bundle: AgentBundle, moved: bool, edge_cost: float, day_part: str) -> None:
    rt = bundle.runtime
    rt.hunger = min(100.0, rt.hunger + 3.0)
    if moved:
        rt.energy = max(0.0, rt.energy - max(3.0, edge_cost))
    elif day_part in ("evening", "night") and rt.location_id == bundle.profile.home_location_id:
        rt.energy = min(100.0, rt.energy + 8.0)
    elif rt.location_id == "workplace":
        rt.energy = max(0.0, rt.energy - 4.0)
    else:
        rt.energy = max(0.0, min(100.0, rt.energy - 1.0))

    # Eat at home/commerce when hungry
    if rt.hunger > 60 and rt.location_id in ("home", "commerce"):
        if rt.location_id == "commerce" or rt.inventory_staples > 0:
            rt.hunger = max(0.0, rt.hunger - 25.0)
            rt.energy = min(100.0, rt.energy + 5.0)


def _update_gaps(bundle: AgentBundle, day_part: str) -> None:
    rt = bundle.runtime
    for gap in rt.goal_gaps:
        if gap.gap_id == "gap_companionship":
            if day_part in ("evening", "night") and rt.location_id == "home":
                gap.value += 1.0
            gap.active = gap.value >= gap.threshold
        elif gap.gap_id == "gap_resource":
            if rt.inventory_staples <= 0:
                gap.value += 1.0
            else:
                gap.value = max(0.0, gap.value - 0.5)
            gap.active = gap.value >= gap.threshold
        elif gap.gap_id == "gap_commitment":
            # no commitments in P0 — keep inactive
            gap.active = False


def tick(state: SimState, agent_id: str, cfg: AppConfig, llm: LlmClient | None = None) -> SimState:
    """Advance one tick for agent_id. Mutates and returns state."""
    if agent_id not in state.agents:
        raise KeyError(f"unknown agent_id: {agent_id}")

    llm = llm or build_llm_client(cfg)
    # Probe LLM once per tick (explicit skip log when no key)
    _ = llm.structured("tick-noop")
    _ = llm.narrative("tick-noop")

    bundle = state.agents[agent_id]
    if not bundle.agent.enabled:
        logger.warning("agent %s disabled — skip", agent_id)
        return state

    world = state.world
    # Global clock advance once per tick call (MVP single agent)
    world.clock = world.clock.advance(cfg.tick_minutes)
    clock = world.clock
    day_part = clock.day_part()

    from_id = bundle.runtime.location_id
    loc_before = world.location(from_id)
    next_id = _pick_next_location(bundle, state)
    moved = False
    edge_cost = 0.0
    from_name = loc_before.display_name
    to_name = from_name

    if next_id and next_id != from_id:
        edge = next((e for e in loc_before.edges if e.to == next_id), None)
        if edge and bundle.runtime.energy >= edge.cost_energy:
            world.move_occupant(agent_id, from_id, next_id)
            bundle.runtime.location_id = next_id
            moved = True
            edge_cost = edge.cost_energy
            to_name = world.location(next_id).display_name

    _apply_body_rules(bundle, moved, edge_cost, day_part)

    # Slow staple drip while at home eating often
    if bundle.runtime.location_id == "home" and bundle.runtime.hunger < 35:
        if clock.minute_of_day % 180 == 0 and bundle.runtime.inventory_staples > 0:
            bundle.runtime.inventory_staples = max(0, bundle.runtime.inventory_staples - 1)

    _update_gaps(bundle, day_part)

    # affect_step (rules)
    delta, tags, note = rule_appraise(
        energy=bundle.runtime.energy,
        hunger=bundle.runtime.hunger,
        location_id=bundle.runtime.location_id,
        weather=world.weather.value,
        day_part=day_part,
        moved=moved,
        staples=bundle.runtime.inventory_staples,
    )
    entry = affect_step(
        affect=bundle.affect,
        baseline=bundle.profile.pad_baseline,
        delta=delta,
        cause_tags=tags,
        clock=clock,
        cfg=cfg.affect,
        note=note,
    )
    state.affect_log.append(entry)

    # template episodic memory + gate
    summary, importance = template_tick_summary(
        clock_label=clock.label(),
        day_part=day_part,
        location_name=to_name,
        weather=world.weather.value,
        energy=bundle.runtime.energy,
        moved_from=from_name if moved else None,
        moved_to=to_name if moved else None,
    )
    mem = gate_memory(
        agent_id=agent_id,
        ts=clock,
        location_id=bundle.runtime.location_id,
        summary=summary,
        importance=importance,
        affect_tags=tags,
        source="tick",
    )
    if mem is not None:
        state.memories.append(mem)

    now = datetime.now(timezone.utc).isoformat()
    bundle.runtime.last_tick_at = now
    world.updated_at = now
    world.version += 1
    return state


def tick_n(
    state: SimState,
    agent_id: str,
    n: int,
    cfg: AppConfig,
    llm: LlmClient | None = None,
) -> SimState:
    llm = llm or build_llm_client(cfg)
    for _ in range(max(1, n)):
        state = tick(state, agent_id, cfg, llm=llm)
    return state


def snapshot_dict(state: SimState, agent_id: str) -> dict:
    bundle = state.agents[agent_id]
    loc = state.world.location(bundle.runtime.location_id)
    return {
        "clock": state.world.clock.model_dump(),
        "clock_label": state.world.clock.label(),
        "day_part": state.world.clock.day_part(),
        "weather": state.world.weather.value,
        "agent_id": agent_id,
        "display_name": bundle.agent.display_name,
        "location": {"id": loc.id, "display_name": loc.display_name},
        "energy": bundle.runtime.energy,
        "hunger": bundle.runtime.hunger,
        "inventory_staples": bundle.runtime.inventory_staples,
        "money_band": bundle.runtime.money_band.value,
        "pad": bundle.affect.as_pad().model_dump(),
        "goal_gaps": [g.model_dump() for g in bundle.runtime.goal_gaps],
        "memory_count": len([m for m in state.memories if m.agent_id == agent_id]),
        "affect_log_count": len([a for a in state.affect_log if a.agent_id == agent_id]),
        "world_version": state.world.version,
    }
