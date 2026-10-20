"""CLI: seed / tick / tick -n / snapshot / serve."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .config import load_config, package_dir
from .llm import build_llm_client
from .store import SimStore
from .tick import snapshot_dict, tick, tick_n


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s %(name)s: %(message)s",
    )


def _store_from_args(args: argparse.Namespace) -> tuple[SimStore, object]:
    cfg_path = Path(args.config) if args.config else None
    cfg = load_config(cfg_path)
    # Resolve data_dir relative to apps/sim package root
    data_dir = cfg.resolve_data_dir(package_dir())
    agent_id = args.agent_id or cfg.default_agent_id
    store = SimStore(data_dir, default_agent_id=agent_id)
    return store, cfg


def cmd_seed(args: argparse.Namespace) -> int:
    store, cfg = _store_from_args(args)
    state = store.reset()
    print(f"Seeded → {store.state_path}")
    print(json.dumps(snapshot_dict(state, cfg.default_agent_id), ensure_ascii=False, indent=2))
    return 0


def cmd_tick(args: argparse.Namespace) -> int:
    store, cfg = _store_from_args(args)
    state = store.ensure()
    agent_id = args.agent_id or cfg.default_agent_id
    llm = build_llm_client(cfg)
    n = max(1, int(args.n))
    if n == 1:
        state = tick(state, agent_id, cfg, llm=llm)
    else:
        state = tick_n(state, agent_id, n, cfg, llm=llm)
    store.save(state)
    snap = snapshot_dict(state, agent_id)
    print(json.dumps(snap, ensure_ascii=False, indent=2))
    return 0


def cmd_snapshot(args: argparse.Namespace) -> int:
    store, cfg = _store_from_args(args)
    state = store.ensure()
    agent_id = args.agent_id or cfg.default_agent_id
    print(json.dumps(snapshot_dict(state, agent_id), ensure_ascii=False, indent=2))
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    store, cfg = _store_from_args(args)
    store.ensure()
    import uvicorn

    from .api import create_app

    app = create_app(cfg)
    host = args.host or cfg.api.host
    port = int(args.port or cfg.api.port)
    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="worldsim",
        description="Virtual life world sim — path A tick (no-LLM capable)",
    )
    p.add_argument("--config", help="Path to config.yaml")
    p.add_argument("--agent-id", dest="agent_id", help="AgentId (default from config)")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("seed", help="Reset state to world-pack seed")
    s.set_defaults(func=cmd_seed)

    t = sub.add_parser("tick", help="Advance simulation tick(s)")
    t.add_argument("-n", "--n", type=int, default=1, help="Number of ticks")
    t.set_defaults(func=cmd_tick)

    snap = sub.add_parser("snapshot", help="Print current snapshot")
    snap.set_defaults(func=cmd_snapshot)

    srv = sub.add_parser("serve", help="Start read-only HTTP API")
    srv.add_argument("--host", default=None)
    srv.add_argument("--port", type=int, default=None)
    srv.set_defaults(func=cmd_serve)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _setup_logging(args.verbose)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
