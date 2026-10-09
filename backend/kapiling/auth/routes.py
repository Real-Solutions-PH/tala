import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from kapiling.auth import lock
from kapiling.auth.deps import SESSION_COOKIE, Actor, require_owner_of, require_unlocked
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
    lock.end_session(request.cookies.get(SESSION_COOKIE))  # replace any session this browser already had
    response.set_cookie(SESSION_COOKIE, lock.new_session(actor), httponly=True, samesite="strict", path="/",
                        secure=request.url.scheme == "https")


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
    if actor["role"] != "owner":
        raise HTTPException(403, "errors.ownerOnly")
    rows = con.execute("select actor, action, target, at from access_log where profile_id=? order by id desc limit 500",
                       (pid,))
    return [dict(r) for r in rows]
