import sqlite3

from fastapi import HTTPException, Request, Response

from kapiling.auth import lock
from kapiling.auth.lock import Actor

SESSION_COOKIE = "kapiling_s"

__all__ = ["Actor", "SESSION_COOKIE", "require_unlocked"]


def require_unlocked(request: Request) -> Actor:
    """FastAPI dependency: a live session (401 otherwise). On routes with a `{pid}` path parameter the
    session's profile must match it (403 otherwise). Routes without `{pid}` must check ownership themselves."""
    actor = lock.session_actor(request.cookies.get(SESSION_COOKIE))
    if actor is None:
        raise HTTPException(401, "errors.locked")
    pid = request.path_params.get("pid")
    if pid is not None and str(actor["profile_id"]) != str(pid):
        raise HTTPException(403, "errors.notYourProfile")
    return actor


def require_owner_of(actor: Actor, pid: int) -> None:
    if actor["profile_id"] != pid:
        raise HTTPException(403, "errors.notYourProfile")


def require_owner(con: sqlite3.Connection, actor: Actor, action: str) -> None:
    """Owner-only actions (PINs, representatives, biometrics, the access log). A representative's attempt is
    refused with an i18n key and written to the access log."""
    if actor["role"] != "owner":
        lock.log_access(con, actor["profile_id"], actor, "denied", action)
        raise HTTPException(403, "settings.ownerOnly")


def start_session(request: Request, response: Response, actor: Actor) -> None:
    """Issue the session cookie for a verified actor (PIN or biometric), replacing any session this browser had."""
    lock.end_session(request.cookies.get(SESSION_COOKIE))
    response.set_cookie(SESSION_COOKIE, lock.new_session(actor), httponly=True, samesite="strict", path="/",
                        secure=request.url.scheme == "https")
