import hashlib
import hmac
import os
import secrets
import sqlite3
import threading
import time
from typing import TypedDict

_N, _R, _P = 2**14, 8, 1


def _scrypt(pin: str, salt: bytes) -> bytes:
    return hashlib.scrypt(pin.encode(), salt=salt, n=_N, r=_R, p=_P)


def hash_pin(pin: str) -> str:
    salt = os.urandom(16)
    return f"scrypt${salt.hex()}${_scrypt(pin, salt).hex()}"


def verify_pin(pin: str, stored: str) -> bool:
    try:
        scheme, salt_hex, hash_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        return hmac.compare_digest(_scrypt(pin, bytes.fromhex(salt_hex)), bytes.fromhex(hash_hex))
    except ValueError:
        return False


class Actor(TypedDict):
    profile_id: int
    name: str
    role: str  # 'owner' | 'representative'


IDLE_TIMEOUT = 300.0      # seconds without an authorised request before a session dies
FAIL_WINDOW = 300.0       # failures counted over this many seconds, per profile
FAIL_LIMIT = 5
BACKOFF = 60.0            # seconds of 429 once FAIL_LIMIT is reached
UNKNOWN = "unknown"


def _now() -> float:
    """Injectable clock (tests monkeypatch it)."""
    return time.monotonic()


# ponytail: in-memory sessions; a restart locks everyone, which is the safe direction
_sessions: dict[str, tuple[Actor, float]] = {}   # token -> (actor, last_seen)
_failures: dict[int, list[float]] = {}            # profile_id -> attempt timestamps (pending or failed)
_blocked_until: dict[int, float] = {}
_mu = threading.Lock()


def reset_state() -> None:
    with _mu:
        _sessions.clear()
        _failures.clear()
        _blocked_until.clear()


def log_access(con: sqlite3.Connection, pid: int, actor: Actor | str, action: str, target: str | None = None) -> None:
    name = actor if isinstance(actor, str) else actor["name"]
    con.execute("insert into access_log (profile_id, actor, action, target) values (?,?,?,?)", (pid, name, action, target))
    con.commit()


# --- sessions -----------------------------------------------------------------

def new_session(actor: Actor) -> str:
    token = secrets.token_urlsafe(32)
    now = _now()
    with _mu:
        for t in [t for t, (_, seen) in _sessions.items() if now - seen > IDLE_TIMEOUT]:
            del _sessions[t]
        _sessions[token] = (actor, now)
    return token


def session_actor(token: str | None) -> Actor | None:
    """The live session's actor, refreshing its idle timer; None when missing or expired."""
    if not token:
        return None
    now = _now()
    with _mu:
        entry = _sessions.get(token)
        if entry is None:
            return None
        actor, seen = entry
        if now - seen > IDLE_TIMEOUT:
            del _sessions[token]
            return None
        _sessions[token] = (actor, now)
        return actor


def end_session(token: str | None) -> None:
    if token:
        with _mu:
            _sessions.pop(token, None)


# --- unlock with backoff --------------------------------------------------------

class BackedOff(Exception):
    pass


def _begin_attempt(pid: int) -> float:
    """Reserve an attempt slot (counted as a failure unless it succeeds); raise BackedOff when blocked."""
    now = _now()
    with _mu:
        if now < _blocked_until.get(pid, 0.0):
            raise BackedOff
        recent = [t for t in _failures.get(pid, []) if now - t < FAIL_WINDOW]
        if len(recent) >= FAIL_LIMIT:  # in-flight attempts already fill the window
            raise BackedOff
        recent.append(now)
        _failures[pid] = recent
        return now


def _end_attempt(pid: int, stamp: float, ok: bool) -> None:
    with _mu:
        recent = _failures.get(pid, [])
        if ok:
            if stamp in recent:
                recent.remove(stamp)
            if not recent:
                _failures.pop(pid, None)
        elif len([t for t in recent if _now() - t < FAIL_WINDOW]) >= FAIL_LIMIT:
            _blocked_until[pid] = _now() + BACKOFF
            _failures.pop(pid, None)  # the count restarts once the backoff ends


def check_pin(con: sqlite3.Connection, pid: int, pin: str) -> Actor | None:
    """Owner PIN first, then each representative of the profile. Raises BackedOff while blocked."""
    profile = con.execute("select nickname, full_name from profiles where id=?", (pid,)).fetchone()
    if profile is None:
        return None
    stamp = _begin_attempt(pid)
    actor: Actor | None = None
    try:
        owner = con.execute("select pin_hash from owner_lock where profile_id=?", (pid,)).fetchone()
        if owner is not None and verify_pin(pin, owner["pin_hash"]):
            actor = {"profile_id": pid, "name": profile["nickname"] or profile["full_name"], "role": "owner"}
        else:
            for rep in con.execute("select name, pin_hash from representatives where profile_id=? order by id", (pid,)):
                if verify_pin(pin, rep["pin_hash"]):
                    actor = {"profile_id": pid, "name": rep["name"], "role": "representative"}
                    break
    finally:
        _end_attempt(pid, stamp, actor is not None)
    log_access(con, pid, actor or UNKNOWN, "unlock" if actor else "unlock_failed")
    return actor
