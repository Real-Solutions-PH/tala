"""Cloud demo mode (KAPILING_DEMO=1): fictional data only, a banner flag, a reset button, and no pairing.

Everything here is inert unless demo mode is on. Reset wipes and reseeds only settings.data_dir."""

import shutil
from typing import Any

from fastapi import APIRouter, HTTPException

from kapiling import config, db
from kapiling.auth import lock
from seed import persona

router = APIRouter(prefix="/api/demo")

DB_FILES = ("kapiling.db", "kapiling.db-wal", "kapiling.db-shm")


def reset_data() -> dict[str, int]:
    """Delete the demo database and uploaded files inside data_dir, then seed the fictional persona again."""
    d = config.settings.data_dir
    for name in DB_FILES:
        (d / name).unlink(missing_ok=True)
    shutil.rmtree(d / "files", ignore_errors=True)
    lock.reset_state()
    con = db.connect()
    try:
        return persona.seed(con)
    finally:
        con.close()


@router.get("")
def status() -> dict[str, bool]:
    """The frontend reads this to show the "Fictional data" banner and the Reset demo button."""
    return {"demo": config.settings.demo}


@router.post("/reset", status_code=204)
def reset() -> None:
    if not config.settings.demo:
        raise HTTPException(404)
    reset_data()


class NoPairing:
    """Demo mode has no pairing key: every client is treated as local, so the paired_only middleware lets it through.
    Behind Caddy the peer address is the real visitor (uvicorn --proxy-headers), which would otherwise get a 403."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] in ("http", "websocket"):
            scope["client"] = ("127.0.0.1", 0)
        await self.app(scope, receive, send)


def install(app: Any) -> None:
    app.include_router(router)
    if config.settings.demo:
        app.add_middleware(NoPairing)
