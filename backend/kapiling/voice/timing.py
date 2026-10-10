"""Per-turn timing: one line of millisecond stamps, stored in turn_timings."""

import json
import sqlite3
import time


class TurnTimer:
    def __init__(self) -> None:
        self._t0 = time.perf_counter()
        self._stamps: dict[str, float] = {}

    def stamp(self, name: str) -> None:
        self._stamps[name] = round((time.perf_counter() - self._t0) * 1000, 1)

    def as_dict(self) -> dict[str, float]:
        return dict(self._stamps)

    def save(self, con: sqlite3.Connection, message_id: str) -> None:
        con.execute(
            "insert or replace into turn_timings(message_id, stamps) values (?, ?)",
            (message_id, json.dumps(self._stamps)),
        )
        con.commit()
