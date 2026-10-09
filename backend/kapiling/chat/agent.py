"""The chat agent. Until Task 12 this is an echo, so the run plumbing can be built and tested on its own."""

import sqlite3
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from kapiling.chat import agui
from kapiling.chat.runs import Run


@dataclass
class RunCtx:
    con: sqlite3.Connection  # the run's own connection, opened by the run task (never the request's)
    run: Run
    profile_id: int
    conversation_id: str
    lang: str  # en | tl
    mode: str  # text | voice | usap | listen
    speak: bool
    user_text: str
    images: list[bytes]
    audio: bytes | None
    timer: Any = None  # turn timer, wired in Task 9


async def stream_run(ctx: RunCtx) -> AsyncIterator[dict]:
    """Yield AG-UI events for one reply (no RUN_STARTED/RUN_FINISHED: the run owns those). The run saves
    the first TEXT_MESSAGE_START messageId as the assistant message id. Task 12 replaces this body."""
    yield agui.step_started("check_profile")
    yield agui.step_finished("check_profile")
    mid = uuid.uuid4().hex
    yield agui.text_start(mid)
    if ctx.user_text:
        yield agui.text_delta(mid, ctx.user_text)
    yield agui.text_end(mid)
