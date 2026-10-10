"""Chat REST: conversations, the AG-UI run stream and cancel."""

import asyncio
import logging
import sqlite3
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Annotated

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from kapiling import db
from kapiling.auth.deps import Actor, require_owner_of, require_unlocked
from kapiling.chat import agent, agui, conversations, runs
from kapiling.db import get_con
from kapiling.records.routes import _read_image
from kapiling.voice import tts
from kapiling.voice.timing import TurnTimer

router = APIRouter(prefix="/api")
Con = Annotated[sqlite3.Connection, Depends(get_con)]
Unlocked = Annotated[Actor, Depends(require_unlocked)]
log = logging.getLogger("kapiling.chat")  # ids and exception types only: never message text (no PHI)

LANGS = {"en", "tl"}
MODES = {"text", "voice", "usap", "listen"}
MAX_AUDIO = 25 * 1024 * 1024
SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
BAD_INPUT = "errors.bad_input"
SPEAK_MAX = 400
# Seconds to wait for a cancelled agent to unwind before the run moves on without it.
PUMP_GRACE_S = 2.0


def _conversation_or_404(con: sqlite3.Connection, cid: str, actor: Actor) -> None:
    pid = conversations.owner(con, cid)
    if pid is None:
        raise HTTPException(404, "errors.notFound")
    require_owner_of(actor, pid)  # no {pid} in these paths, so the dependency cannot check it


# --- conversations -------------------------------------------------------------------

@router.get("/profiles/{pid}/conversations")
def list_conversations(pid: int, con: Con, _a: Unlocked):
    return conversations.list_for(con, pid)


@router.get("/conversations/{cid}")
def get_conversation(cid: str, con: Con, actor: Unlocked):
    _conversation_or_404(con, cid, actor)
    conv = conversations.get(con, cid)
    del conv["profile_id"]
    return conv


@router.patch("/conversations/{cid}", status_code=204)
def rename_conversation(cid: str, con: Con, actor: Unlocked, title: Annotated[str, Body(embed=True)]):
    _conversation_or_404(con, cid, actor)
    title = " ".join(title.split())[:120]
    if not title:
        raise HTTPException(400, BAD_INPUT)
    conversations.rename(con, cid, title)
    return Response(status_code=204)


@router.delete("/conversations/{cid}", status_code=204)
def delete_conversation(cid: str, con: Con, actor: Unlocked):
    _conversation_or_404(con, cid, actor)
    conversations.delete(con, cid)
    return Response(status_code=204)


# --- runs --------------------------------------------------------------------------------

@dataclass
class _Prepared:
    conversation_id: str
    text: str
    images: list[bytes]
    audio: bytes | None


def _prepare(con: sqlite3.Connection, pid: int, conversation_id: str | None, message: str | None, lang: str | None,
             mode: str | None, files: list[UploadFile], audio: UploadFile | None) -> _Prepared:
    """Everything that can fail with a 4xx, run before the stream starts (G-C-012). Then the conversation is
    created if needed and the user message saved."""
    if lang not in LANGS or mode not in MODES:
        raise HTTPException(400, BAD_INPUT)
    text = (message or "").strip()
    images = [_read_image(f)[0] for f in files if f.filename]  # 413/415 like card uploads
    audio_bytes = None
    if audio is not None and audio.filename:
        audio_bytes = audio.file.read(MAX_AUDIO + 1)
        if len(audio_bytes) > MAX_AUDIO:
            raise HTTPException(413, "errors.fileTooLarge")
        audio_bytes = audio_bytes or None
    if not text and not images and audio_bytes is None:
        raise HTTPException(400, BAD_INPUT)
    if conversation_id:
        owner = conversations.owner(con, conversation_id)
        if owner is None:
            raise HTTPException(404, "errors.notFound")
        if owner != pid:
            raise HTTPException(403, "errors.notYourProfile")
        cid = conversation_id
    else:
        cid = conversations.create(con, pid, text, mode=mode, lang=lang)
    attachments = [{"type": "image"} for _ in images] + ([{"type": "audio"}] if audio_bytes else [])
    conversations.append(con, cid, "user", text, mode=mode, attachments=attachments)
    return _Prepared(cid, text, images, audio_bytes)


@router.post("/runs")
async def post_run(
    con: Con, actor: Unlocked,
    profile_id: Annotated[int, Form()],
    lang: Annotated[str | None, Form()] = None,
    mode: Annotated[str | None, Form()] = None,
    message: Annotated[str | None, Form()] = None,
    conversation_id: Annotated[str | None, Form()] = None,
    speak: Annotated[int, Form()] = 0,
    files: Annotated[list[UploadFile] | None, File()] = None,
    audio: Annotated[UploadFile | None, File()] = None,
):
    require_owner_of(actor, profile_id)  # profile_id is a form field, not a {pid} path param
    prep = await run_in_threadpool(_prepare, con, profile_id, conversation_id, message, lang, mode, files or [], audio)
    run = runs.start(profile_id)
    ctx = agent.RunCtx(con=None, run=run, profile_id=profile_id, conversation_id=prep.conversation_id, lang=lang,
                       mode=mode, speak=bool(speak), user_text=prep.text, images=prep.images, audio=prep.audio,
                       message_id=uuid.uuid4().hex, timer=TurnTimer())
    queue: asyncio.Queue[dict] = asyncio.Queue()
    # Its own task (EZ-D-017): a client disconnect ends the relay below, never the run.
    run.task = asyncio.create_task(_drive(run, ctx, queue))
    return StreamingResponse(_relay(queue), media_type="text/event-stream", headers=SSE_HEADERS)


@router.post("/runs/{run_id}/cancel", status_code=204)
async def cancel_run(run_id: str, actor: Unlocked):
    # async so run.cancel (an asyncio.Event) is set on the event loop thread.
    run = runs.get(run_id)
    if run is None:
        raise HTTPException(404, "errors.notFound")
    require_owner_of(actor, run.profile_id)
    runs.cancel(run_id)
    return Response(status_code=204)


async def _relay(queue: asyncio.Queue) -> AsyncIterator[bytes]:
    while True:
        event = await queue.get()
        yield agui.encode(event)
        if event["type"] == "RUN_FINISHED":
            return


@dataclass
class _Reply:
    """What the agent has streamed so far; saved even when the run stops early."""
    message_id: str | None = None
    open_message: str | None = None
    text: list[str] = field(default_factory=list)
    blocks: list = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    sources: list = field(default_factory=list)
    errored: bool = False

    def take(self, ev: dict) -> bool:
        """Record one agent event; False for events the run owns and drops."""
        t = ev.get("type")
        if t in ("RUN_STARTED", "RUN_FINISHED"):
            return False
        if t == "TEXT_MESSAGE_START":
            self.message_id = self.message_id or ev["messageId"]
            self.open_message = ev["messageId"]
        elif t == "TEXT_MESSAGE_CONTENT":
            self.text.append(ev["delta"])
        elif t == "TEXT_MESSAGE_END":
            self.open_message = None
        elif t == "STEP_STARTED":
            self.steps.append(ev["stepName"])
        elif t == "CUSTOM" and ev.get("name") == "block":
            self.blocks.append(ev["value"])
        elif t == "CUSTOM" and ev.get("name") == "sources":
            self.sources.extend(ev["value"])
        elif t == "RUN_ERROR":
            self.errored = True
        return True


async def _pump(ctx: agent.RunCtx, reply: _Reply, put) -> None:
    stream = agent.stream_run(ctx)  # looked up per run so tests (and Task 12) can swap it
    try:
        async for ev in stream:
            if reply.take(ev):
                put(ev)
    finally:
        await stream.aclose()


async def _compose(run: runs.Run, ctx: agent.RunCtx, reply: _Reply, put) -> tuple[str, dict | None]:
    """Run the agent against the cancel event and the composing deadline. Returns (status, error event).

    The deadline (R19) bounds the time to the FIRST streamed event (token, step or block): a long answer that is
    still streaming when it passes runs to the end."""
    first = asyncio.Event()

    def put_first(ev: dict) -> None:
        first.set()
        put(ev)

    pump = asyncio.create_task(_pump(ctx, reply, put_first))
    stop = asyncio.create_task(run.cancel.wait())
    started = asyncio.create_task(first.wait())
    try:
        await asyncio.wait({pump, stop, started}, timeout=run.deadline_s, return_when=asyncio.FIRST_COMPLETED)
        if not first.is_set() and not pump.done() and not stop.done():
            log.warning("run %s: nothing streamed within the composing deadline of %ss", run.id, run.deadline_s)
            return "failed", agui.run_error("errors.timeout", "timeout")
        await asyncio.wait({pump, stop}, return_when=asyncio.FIRST_COMPLETED)
        if pump.done() and not run.cancel.is_set():
            exc = pump.exception()
            if exc is not None:
                log.error("run %s: agent raised %s", run.id, type(exc).__name__)
                return "failed", agui.run_error("errors.internal", "internal")
            return ("failed" if reply.errored else "complete"), None
        return "stopped", agui.run_error("errors.cancelled", "cancelled")
    finally:
        # Also on our own cancellation: never leave the agent running. The wait is bounded, and asyncio.wait
        # neither raises the pump's exception nor swallows a cancellation of this task.
        for t in (stop, started):
            t.cancel()
        if not pump.done():
            pump.cancel()
            await asyncio.wait({pump}, timeout=PUMP_GRACE_S)


async def _drive(run: runs.Run, ctx: agent.RunCtx, queue: asyncio.Queue) -> None:
    """The run task. It always ends the stream with RUN_FINISHED, after the assistant message is saved; the
    connection is closed and the run forgotten even when this task is cancelled."""
    put = queue.put_nowait
    cid = ctx.conversation_id
    reply = _Reply()
    con = None
    status, saved_id = "failed", None
    try:
        try:
            put(agui.run_started(cid, run.id))
            # Its own connection: the request's connection is closed once the response starts streaming.
            con = ctx.con = await run_in_threadpool(db.connect)
            status, error = await _compose(run, ctx, reply, put)
        except Exception as e:  # noqa: BLE001 - the stream must still finish
            log.error("run %s: %s", run.id, type(e).__name__)
            status, error = "failed", agui.run_error("errors.internal", "internal")
        if reply.open_message:
            put(agui.text_end(reply.open_message))
        if error:
            put(error)
        mid = reply.message_id or ctx.message_id
        try:
            # Saved BEFORE RUN_FINISHED, which carries this id (VCAC-G-022). Partial text is kept.
            if con is None:
                con = await run_in_threadpool(db.connect)
            await run_in_threadpool(conversations.append, con, cid, "assistant", "".join(reply.text), id=mid,
                                    mode=ctx.mode, status=status, blocks=reply.blocks, steps=reply.steps,
                                    sources=reply.sources)
            saved_id = mid
        except Exception as e:  # noqa: BLE001
            log.error("run %s: saving the reply failed: %s", run.id, type(e).__name__)
            if not error:
                put(agui.run_error("errors.internal", "internal"))
            status = "failed"
        if saved_id and ctx.timer is not None:
            try:
                await run_in_threadpool(ctx.timer.save, con, saved_id)
            except Exception as e:  # noqa: BLE001 - timings are diagnostics only
                log.warning("run %s: saving timings failed: %s", run.id, type(e).__name__)
    finally:
        put(agui.run_finished(cid, run.id, saved_id, status))
        try:
            if con is not None:
                await run_in_threadpool(con.close)
        finally:
            runs.finish(run.id)


# --- speech --------------------------------------------------------------------------------

@router.post("/speak")
async def speak(_a: Unlocked, text: Annotated[str, Form()], lang: Annotated[str, Form()]):
    """Read a reply aloud on demand (the speaker button). No profile data is read, so no owner check."""
    text = text.strip()
    if not text or len(text) > SPEAK_MAX or lang not in LANGS:
        raise HTTPException(400, BAD_INPUT)
    wav = await run_in_threadpool(tts.speak, text, lang)
    return Response(wav, media_type="audio/wav", headers={"Cache-Control": "no-store"})
