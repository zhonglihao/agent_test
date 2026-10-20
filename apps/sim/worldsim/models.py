"""Data contract v0 — Python shapes (docs/data-contract-v0.md)."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


AgentId = str
LocationId = str
MemoryId = str


class Weather(str, Enum):
    clear = "clear"
    cloudy = "cloudy"
    light_rain = "light_rain"
    heavy_rain = "heavy_rain"
    hot = "hot"
    cold = "cold"


class MoneyBand(str, Enum):
    tight = "tight"
    ok = "ok"
    comfortable = "comfortable"


class MemoryTier(str, Enum):
    hot = "hot"
    warm = "warm"
    cold = "cold"
    tombstone = "tombstone"


class PersonaStatus(str, Enum):
    placeholder = "placeholder"
    locked = "locked"


class WriteActor(str, Enum):
    system = "system"
    admin = "admin"


DayPart = Literal["dawn", "morning", "midday", "afternoon", "evening", "night"]


class SimClock(BaseModel):
    day: int = 1
    minute_of_day: int = 0  # 0..1439

    def advance(self, minutes: int) -> SimClock:
        total = self.day * 1440 + self.minute_of_day + minutes
        return SimClock(day=total // 1440, minute_of_day=total % 1440)

    @property
    def hour(self) -> int:
        return self.minute_of_day // 60

    @property
    def minute(self) -> int:
        return self.minute_of_day % 60

    def day_part(self) -> DayPart:
        h = self.hour
        if 5 <= h < 7:
            return "dawn"
        if 7 <= h < 11:
            return "morning"
        if 11 <= h < 14:
            return "midday"
        if 14 <= h < 18:
            return "afternoon"
        if 18 <= h < 22:
            return "evening"
        return "night"

    def label(self) -> str:
        return f"D{self.day} {self.hour:02d}:{self.minute:02d}"


class Pad(BaseModel):
    p: float = 0.0
    a: float = 0.0
    d: float = 0.0

    def clamp(self, lo: float = -1.0, hi: float = 1.0) -> Pad:
        return Pad(
            p=max(lo, min(hi, self.p)),
            a=max(lo, min(hi, self.a)),
            d=max(lo, min(hi, self.d)),
        )

    def __add__(self, other: Pad) -> Pad:
        return Pad(p=self.p + other.p, a=self.a + other.a, d=self.d + other.d)

    def scale(self, s: float) -> Pad:
        return Pad(p=self.p * s, a=self.a * s, d=self.d * s)


class LocationEdge(BaseModel):
    to: LocationId
    cost_energy: float = 5.0
    cost_minutes: int = 30


class Location(BaseModel):
    id: LocationId
    display_name: str
    edges: list[LocationEdge] = Field(default_factory=list)
    attrs: dict[str, Any] = Field(default_factory=dict)
    occupant_ids: list[AgentId] = Field(default_factory=list)


class WorldState(BaseModel):
    clock: SimClock
    weather: Weather = Weather.clear
    air_quality_band: str | None = "good"
    locations: list[Location]
    items: list[dict[str, Any]] = Field(default_factory=list)
    version: int = 1
    updated_at: str | None = None

    def location(self, location_id: LocationId) -> Location:
        for loc in self.locations:
            if loc.id == location_id:
                return loc
        raise KeyError(location_id)

    def move_occupant(self, agent_id: AgentId, from_id: LocationId, to_id: LocationId) -> None:
        self.location(from_id).occupant_ids = [
            a for a in self.location(from_id).occupant_ids if a != agent_id
        ]
        dest = self.location(to_id)
        if agent_id not in dest.occupant_ids:
            dest.occupant_ids.append(agent_id)


class Agent(BaseModel):
    id: AgentId
    display_name: str
    enabled: bool = True
    created_at: str


class AgentProfile(BaseModel):
    agent_id: AgentId
    persona_status: PersonaStatus = PersonaStatus.placeholder
    persona_notes: str | None = None
    pad_baseline: Pad = Field(default_factory=lambda: Pad(p=0.1, a=0.0, d=0.0))
    traits: dict[str, Any] | None = None
    interest_weights: dict[str, Any] | None = None
    style_constraints: dict[str, Any] | None = None
    home_location_id: LocationId = "home"
    relationship_to_user: str | None = "observer_bond_tbd"


class GoalGap(BaseModel):
    gap_id: str
    kind: str
    metric: str
    value: float = 0.0
    threshold: float
    active: bool = False
    linked_commitment_id: str | None = None
    intent_type_hint: str | None = None


class AgentRuntime(BaseModel):
    agent_id: AgentId
    location_id: LocationId
    energy: float = 70.0
    hunger: float = 30.0
    money_band: MoneyBand = MoneyBand.ok
    inventory_staples: int = 2  # 0–2
    goal_gaps: list[GoalGap] = Field(default_factory=list)
    cooldowns: dict[str, str] = Field(default_factory=dict)
    last_tick_at: str | None = None
    planned_destination: LocationId | None = None


class AffectState(BaseModel):
    agent_id: AgentId
    pleasure: float = 0.1
    arousal: float = 0.0
    dominance: float = 0.0
    updated_at: str | None = None

    def as_pad(self) -> Pad:
        return Pad(p=self.pleasure, a=self.arousal, d=self.dominance)

    def apply_pad(self, pad: Pad, updated_at: str | None = None) -> None:
        self.pleasure = pad.p
        self.arousal = pad.a
        self.dominance = pad.d
        self.updated_at = updated_at


class AffectLogEntry(BaseModel):
    id: str = Field(default_factory=lambda: f"aff_{uuid4().hex[:12]}")
    agent_id: AgentId
    ts: SimClock
    wall_ts: str | None = None
    pad: Pad
    delta: Pad | None = None
    cause_tags: list[str] = Field(default_factory=list)
    event_ref: str | None = None
    note: str | None = None
    actor: WriteActor = WriteActor.system


class EpisodicMemory(BaseModel):
    id: MemoryId = Field(default_factory=lambda: f"mem_{uuid4().hex[:12]}")
    agent_id: AgentId
    ts: SimClock
    location_id: LocationId | None = None
    summary: str
    importance: float = 0.4
    tier: MemoryTier = MemoryTier.hot
    affect_tags: list[str] = Field(default_factory=list)
    affect_peak: bool | None = None
    retain_category: str | None = None
    linked_commitment_id: str | None = None
    source: str = "tick"
    actor: WriteActor = WriteActor.system


class AgentBundle(BaseModel):
    agent: Agent
    profile: AgentProfile
    runtime: AgentRuntime
    affect: AffectState


class SimState(BaseModel):
    """Persisted simulation document."""

    world: WorldState
    agents: dict[AgentId, AgentBundle]
    memories: list[EpisodicMemory] = Field(default_factory=list)
    affect_log: list[AffectLogEntry] = Field(default_factory=list)
