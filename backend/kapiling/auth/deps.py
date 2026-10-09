from fastapi import HTTPException, Request

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
