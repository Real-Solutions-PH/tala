from typing import TypedDict

from fastapi import Request


class Actor(TypedDict):
    profile_id: int | None
    name: str
    role: str


def require_unlocked(request: Request) -> Actor:
    """STUB (Task 6 swaps the body for real session checks): allows everything as the owner."""
    pid = request.path_params.get("pid")
    return {"profile_id": int(pid) if pid is not None else None, "name": "owner", "role": "owner"}
