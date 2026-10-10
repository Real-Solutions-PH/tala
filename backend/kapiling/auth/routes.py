import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from kapiling.auth import lock
from kapiling.auth.deps import (SESSION_COOKIE, Actor, end_other_sessions, require_current_pin, require_owner,
                                require_owner_of, require_unlocked, start_session)
from kapiling.db import get_con

router = APIRouter(prefix="/api")
Con = Annotated[sqlite3.Connection, Depends(get_con)]
Unlocked = Annotated[Actor, Depends(require_unlocked)]


class UnlockBody(BaseModel):
    profile_id: int
    pin: str = Field(min_length=1, max_length=64)


@router.post("/unlock", status_code=204)
def unlock(body: UnlockBody, request: Request, response: Response, con: Con):
    try:
        actor = lock.check_pin(con, body.profile_id, body.pin)
    except lock.BackedOff:
        raise HTTPException(429, "errors.tooManyAttempts", headers={"Retry-After": str(int(lock.BACKOFF))}) from None
    if actor is None:
        raise HTTPException(401, "errors.wrongPin")
    start_session(request, response, actor)  # replaces any session this browser already had


@router.post("/lock", status_code=204)
def lock_now(request: Request, response: Response):
    # No session needed: this only revokes the token the caller presents, so an expired tab can still clear it.
    lock.end_session(request.cookies.get(SESSION_COOKIE))
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, samesite="strict",
                           secure=request.url.scheme == "https")


@router.get("/access-log")
def access_log(con: Con, actor: Unlocked, profile_id: int | None = None):
    pid = actor["profile_id"] if profile_id is None else profile_id
    require_owner_of(actor, pid)
    require_owner(con, actor, "view_access_log")
    rows = con.execute("select actor, action, target, at from access_log where profile_id=? order by id desc limit 500",
                       (pid,))
    out = [dict(r) for r in rows]
    lock.log_access(con, pid, actor, "view_access_log")  # after the read, so the list shows what came before
    return out


# --- Task 15: settings, representatives and the owner PIN --------------------------------------------

Pin = Annotated[str, Field(pattern=r"^[0-9]{6}$")]


def _pin_in_use(con: sqlite3.Connection, pid: int, pin: str, *, include_owner: bool = True) -> bool:
    """True when the PIN already opens this profile (owner or any representative). PINs must be unique,
    otherwise an unlock could not tell who is acting."""
    hashes = [r["pin_hash"] for r in con.execute("select pin_hash from representatives where profile_id=?", (pid,))]
    if include_owner:
        hashes += [r["pin_hash"] for r in con.execute("select pin_hash from owner_lock where profile_id=?", (pid,))]
    return any(lock.verify_pin(pin, h) for h in hashes)


def _rep_json(r) -> dict:
    return {"id": r["id"], "name": r["name"], "relation": r["relation"]}


@router.get("/profiles/{pid}/settings")
def settings_overview(pid: int, con: Con, actor: Unlocked):
    """Everything the Settings page needs. Representatives are listed for the owner only."""
    from kapiling.auth.webauthn import has_biometric
    from kapiling.records.summary import _DEFAULT_FIELDS, _fields

    chosen = _fields(con, pid)
    reps = con.execute("select id, name, relation from representatives where profile_id=? order by id", (pid,))
    return {"actor": actor["name"], "role": actor["role"],
            "representatives": [_rep_json(r) for r in reps] if actor["role"] == "owner" else [],
            "emergency_fields": [f for f in _DEFAULT_FIELDS if f in chosen],
            "has_biometric": has_biometric(con, pid)}


class RepBody(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    relation: str | None = Field(default=None, max_length=40)
    pin: Pin


@router.post("/profiles/{pid}/representatives", status_code=201)
def add_representative(pid: int, body: RepBody, con: Con, actor: Unlocked):
    require_owner(con, actor, "add_representative")
    if _pin_in_use(con, pid, body.pin):
        lock.log_access(con, pid, actor, "pin_clash", "add_representative")  # the PIN itself is never logged
        raise HTTPException(409, "settings.pinInUse")
    name = body.name.strip()
    cur = con.execute("insert into representatives (profile_id, name, relation, pin_hash) values (?,?,?,?)",
                      (pid, name, (body.relation or "").strip() or None, lock.hash_pin(body.pin)))
    con.commit()
    lock.log_access(con, pid, actor, "add_representative", name)
    return _rep_json(con.execute("select * from representatives where id=?", (cur.lastrowid,)).fetchone())


@router.delete("/profiles/{pid}/representatives/{rid}", status_code=204)
def remove_representative(pid: int, rid: int, con: Con, actor: Unlocked):
    require_owner(con, actor, "remove_representative")
    row = con.execute("select name from representatives where id=? and profile_id=?", (rid, pid)).fetchone()
    if row is None:
        raise HTTPException(404, "errors.notFound")
    con.execute("delete from representatives where id=?", (rid,))
    con.commit()
    # Revocation: the removed representative's open sessions end now, not at their next idle timeout.
    lock.end_sessions(pid, lambda _t, a: a.get("rep_id") == rid)
    lock.log_access(con, pid, actor, "remove_representative", row["name"])


class PinBody(BaseModel):
    current_pin: str = Field(min_length=1, max_length=64)
    new_pin: Pin


@router.put("/profiles/{pid}/pin", status_code=204)
def change_pin(pid: int, body: PinBody, request: Request, con: Con, actor: Unlocked):
    require_owner(con, actor, "change_pin")
    require_current_pin(con, pid, actor, body.current_pin, "change_pin_failed")
    if _pin_in_use(con, pid, body.new_pin, include_owner=False):
        lock.log_access(con, pid, actor, "pin_clash", "change_pin")
        raise HTTPException(409, "settings.pinInUse")
    con.execute("update owner_lock set pin_hash=? where profile_id=?", (lock.hash_pin(body.new_pin), pid))
    con.commit()
    end_other_sessions(request, pid)  # anyone else holding the old PIN is signed out
    lock.log_access(con, pid, actor, "change_pin")
