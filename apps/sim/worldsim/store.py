"""JSON file persistence under data/worldsim."""

from __future__ import annotations

import json
from pathlib import Path

from .models import SimState
from .seed import create_seed_state


STATE_FILENAME = "state.json"


class SimStore:
    def __init__(self, data_dir: Path, default_agent_id: str = "agent_seed_01") -> None:
        self.data_dir = data_dir
        self.default_agent_id = default_agent_id
        self.state_path = data_dir / STATE_FILENAME

    def ensure(self) -> SimState:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if not self.state_path.exists():
            state = create_seed_state(self.default_agent_id)
            self.save(state)
            return state
        return self.load()

    def load(self) -> SimState:
        with self.state_path.open(encoding="utf-8") as f:
            raw = json.load(f)
        return SimState.model_validate(raw)

    def save(self, state: SimState) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(state.model_dump(mode="json"), f, ensure_ascii=False, indent=2)
        tmp.replace(self.state_path)

    def reset(self) -> SimState:
        state = create_seed_state(self.default_agent_id)
        self.save(state)
        return state
