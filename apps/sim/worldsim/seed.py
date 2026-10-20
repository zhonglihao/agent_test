"""Seed reality world pack v0 — 6 locations + placeholder agent."""

from __future__ import annotations

from datetime import datetime, timezone

from .models import (
    AffectState,
    Agent,
    AgentBundle,
    AgentProfile,
    AgentRuntime,
    GoalGap,
    Location,
    LocationEdge,
    MoneyBand,
    Pad,
    PersonaStatus,
    SimClock,
    SimState,
    Weather,
    WorldState,
)


def build_locations() -> list[Location]:
    """6-node graph from world-pack-v0 §2."""
    return [
        Location(
            id="home",
            display_name="家",
            edges=[
                LocationEdge(to="neighborhood", cost_energy=3, cost_minutes=10),
            ],
            attrs={"comfort": 0.8, "quiet": True},
            occupant_ids=[],
        ),
        Location(
            id="neighborhood",
            display_name="社区 / 街头",
            edges=[
                LocationEdge(to="home", cost_energy=3, cost_minutes=10),
                LocationEdge(to="transit", cost_energy=5, cost_minutes=15),
                LocationEdge(to="commerce", cost_energy=4, cost_minutes=12),
                LocationEdge(to="outdoors", cost_energy=4, cost_minutes=15),
            ],
            attrs={"crowding": 0.3},
            occupant_ids=[],
        ),
        Location(
            id="transit",
            display_name="通勤廊道",
            edges=[
                LocationEdge(to="neighborhood", cost_energy=5, cost_minutes=15),
                LocationEdge(to="workplace", cost_energy=8, cost_minutes=25),
            ],
            attrs={"crowding": 0.6, "delay_flag": False},
            occupant_ids=[],
        ),
        Location(
            id="workplace",
            display_name="工作 / 学习点",
            edges=[
                LocationEdge(to="transit", cost_energy=8, cost_minutes=25),
                LocationEdge(to="commerce", cost_energy=10, cost_minutes=35),
            ],
            attrs={"workload": 0.5, "social_density": 0.4},
            occupant_ids=[],
        ),
        Location(
            id="commerce",
            display_name="商业点",
            edges=[
                LocationEdge(to="neighborhood", cost_energy=4, cost_minutes=12),
                LocationEdge(to="workplace", cost_energy=10, cost_minutes=35),
                LocationEdge(to="outdoors", cost_energy=5, cost_minutes=15),
            ],
            attrs={"open_hours": "09:00-22:00", "price_pressure": 0.4},
            occupant_ids=[],
        ),
        Location(
            id="outdoors",
            display_name="户外放松点",
            edges=[
                LocationEdge(to="neighborhood", cost_energy=4, cost_minutes=15),
                LocationEdge(to="commerce", cost_energy=5, cost_minutes=15),
            ],
            attrs={"suitability": 0.7, "quiet": 0.6},
            occupant_ids=[],
        ),
    ]


def build_goal_gaps() -> list[GoalGap]:
    return [
        GoalGap(
            gap_id="gap_companionship",
            kind="companionship",
            metric="lonely_evening_ticks",
            value=0.0,
            threshold=2.0,
            active=False,
            intent_type_hint="companionship",
        ),
        GoalGap(
            gap_id="gap_resource",
            kind="resource",
            metric="staples_empty_ticks",
            value=0.0,
            threshold=4.0,
            active=False,
            intent_type_hint="resource",
        ),
        GoalGap(
            gap_id="gap_commitment",
            kind="commitment",
            metric="pending_overdue",
            value=0.0,
            threshold=1.0,
            active=False,
            intent_type_hint="boundary",
        ),
    ]


def create_seed_state(agent_id: str = "agent_seed_01") -> SimState:
    now = datetime.now(timezone.utc).isoformat()
    locations = build_locations()
    # Day 1 08:00 at home, plan toward workplace
    clock = SimClock(day=1, minute_of_day=8 * 60)
    for loc in locations:
        if loc.id == "home":
            loc.occupant_ids = [agent_id]

    world = WorldState(
        clock=clock,
        weather=Weather.clear,
        air_quality_band="good",
        locations=locations,
        items=[],
        version=1,
        updated_at=now,
    )

    baseline = Pad(p=0.1, a=0.0, d=0.0)
    bundle = AgentBundle(
        agent=Agent(
            id=agent_id,
            display_name="（待定）",
            enabled=True,
            created_at=now,
        ),
        profile=AgentProfile(
            agent_id=agent_id,
            persona_status=PersonaStatus.placeholder,
            persona_notes="人设后填：性格、说话风格、兴趣、关系标签等",
            pad_baseline=baseline,
            traits=None,
            home_location_id="home",
            relationship_to_user="observer_bond_tbd",
        ),
        runtime=AgentRuntime(
            agent_id=agent_id,
            location_id="home",
            energy=70.0,
            hunger=30.0,
            money_band=MoneyBand.ok,
            inventory_staples=2,
            goal_gaps=build_goal_gaps(),
            planned_destination="workplace",
            last_tick_at=None,
        ),
        affect=AffectState(
            agent_id=agent_id,
            pleasure=baseline.p,
            arousal=baseline.a,
            dominance=baseline.d,
            updated_at=clock.label(),
        ),
    )

    return SimState(world=world, agents={agent_id: bundle}, memories=[], affect_log=[])
