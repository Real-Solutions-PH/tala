"""Serve the built frontend: static files, plus index.html for any other GET outside /api (deep links, reloads)."""

from pathlib import Path
from typing import Any

from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException


class SPAStaticFiles(StaticFiles):
    """Mounted at "/" behind the paired_only middleware, so an unpaired LAN client still gets 403 first."""

    async def get_response(self, path: str, scope: Any) -> Any:
        try:
            return await super().get_response(path, scope)
        except HTTPException as e:
            # path is relative to the mount ("chat", "api/nope"); unknown /api paths keep their 404 JSON.
            if e.status_code != 404 or scope["method"] not in ("GET", "HEAD") or path.split("/")[0] == "api":
                raise
            return await super().get_response("index.html", scope)


def spa(directory: Path | str) -> SPAStaticFiles:
    return SPAStaticFiles(directory=directory, html=True)
