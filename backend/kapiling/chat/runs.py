"""In-process registry of live chat runs, so POST /runs/{id}/cancel can reach them."""

import asyncio
import threading
import uuid
from dataclasses import dataclass, field

# Seconds the agent has to compose a reply before the run fails with RUN_ERROR(timeout).
# Read when a Run is created, so tests can monkeypatch it.
COMPOSING_DEADLINE_S: float = 20


@dataclass
class Run:
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    cancel: asyncio.Event = field(default_factory=asyncio.Event)
    deadline_s: float = field(default_factory=lambda: COMPOSING_DEADLINE_S)
    profile_id: int | None = None
    task: asyncio.Task | None = None  # the agent task; held here so it is not garbage-collected mid-run


_runs: dict[str, Run] = {}
_mu = threading.Lock()


def start(profile_id: int | None = None) -> Run:
    run = Run(profile_id=profile_id)
    with _mu:
        _runs[run.id] = run
    return run


def get(rid: str) -> Run | None:
    with _mu:
        return _runs.get(rid)


def cancel(rid: str) -> bool:
    run = get(rid)
    if run is None:
        return False
    run.cancel.set()
    return True


def finish(rid: str) -> None:
    with _mu:
        _runs.pop(rid, None)
