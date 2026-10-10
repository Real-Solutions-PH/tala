"""The chat agent: a streaming tool loop against the local llama-server (OpenAI-compatible).

Content deltas stream straight out as TEXT_MESSAGE_CONTENT. Tool calls run the record tools (kapiling.chat.tools)
in the threadpool and emit STEP_* and CUSTOM block/sources events. Safety blocks are fixed (kapiling.chat.safety).
"""

import asyncio
import base64
import json
import logging
import sqlite3
from collections import deque
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import httpx
from starlette.concurrency import run_in_threadpool

from kapiling import config
from kapiling.chat import agui, conversations, listen, prompts, safety, tools
from kapiling.chat.runs import Run
from kapiling.voice import tts
from kapiling.voice.sentences import SentenceAggregator

log = logging.getLogger("kapiling.chat")  # ids and exception types only: never message text (no PHI)

MAX_STEPS = 5
TEMPERATURE = 0.2
LLM_TIMEOUT = httpx.Timeout(120.0, connect=3.0)


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
    message_id: str  # the assistant message id, generated server-side (uuid4().hex) and used for TEXT_MESSAGE_START
    timer: Any = None  # TurnTimer
    user_message_id: str | None = None  # the saved user row, updated with the transcript after the prelude
    gated_out: bool = False  # listen mode, not about the record: no text and no audio (set by listen.prelude)
    sources: list = field(default_factory=list)  # citations emitted so far in this reply (numbering continues)


class LLMUnavailable(Exception):
    pass


async def _llm_stream(payload: dict) -> AsyncIterator[dict]:
    """The one seam for LLM calls: yields parsed OpenAI stream chunks. Closing this generator closes the HTTP
    stream, which makes llama-server stop generating."""
    try:
        async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
            async with client.stream("POST", f"{config.settings.llm_url}/v1/chat/completions", json=payload) as r:
                if r.status_code >= 400:
                    await r.aread()
                    raise LLMUnavailable(f"HTTP {r.status_code}")
                async for line in r.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        return
                    yield json.loads(data)
    except httpx.HTTPError as e:
        raise LLMUnavailable(type(e).__name__) from e


def _warm_messages() -> list[dict] | None:
    """The real system prompt of the first profile (the demo's main user), or None with no profile."""
    from kapiling import db

    con = db.connect()
    try:
        row = con.execute("select id, language from profiles order by id limit 1").fetchone()
        if row is None:
            return None
        lang = row["language"] if row["language"] in ("en", "tl") else "tl"
        return [{"role": "system", "content": prompts.system_prompt(con, row["id"], lang)},
                {"role": "user", "content": "hi"}]
    finally:
        con.close()


async def warm_prompt_cache() -> None:
    """One max_tokens=1 request with the run's system prompt and tool schemas, so llama-server caches that
    prefix and the first real question is fast. Never raises: a down LLM only means a slower first reply."""
    try:
        messages = await run_in_threadpool(_warm_messages)
        if messages is None:
            return
        payload = {"messages": messages, "tools": tools.SCHEMAS, "stream": True, "temperature": TEMPERATURE,
                   "max_tokens": 1}
        stream = _llm_stream(payload)
        try:
            async for _ in stream:
                pass
        finally:
            await stream.aclose()
        log.info("prompt cache warmed")
    except Exception as e:  # noqa: BLE001
        log.warning("prompt cache warm-up failed: %s", type(e).__name__)


def _mime(img: bytes) -> str:
    if img.startswith(b"\x89PNG"):
        return "image/png"
    if img[:4] == b"RIFF" and img[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


def _messages(ctx: RunCtx, forced: str | None) -> list[dict]:
    system = prompts.system_prompt(ctx.con, ctx.profile_id, ctx.lang)
    history = conversations.history(ctx.con, ctx.conversation_id)  # already ends with this run's user message
    if forced and history and history[-1]["role"] == "user":
        # Appended to the request copy of the user turn, not the system prompt, so the cached prompt prefix
        # (system + tools) is reused and the refusal reply starts as fast as any other.
        history[-1] = {"role": "user", "content": history[-1]["content"] + "\n\n" + prompts.forced_refusal(forced)}
    if ctx.images and history and history[-1]["role"] == "user":
        parts: list[dict] = [{"type": "text", "text": history[-1]["content"]}]
        parts += [{"type": "image_url", "image_url": {"url": f"data:{_mime(i)};base64,{base64.b64encode(i).decode()}"}}
                  for i in ctx.images]
        history[-1] = {"role": "user", "content": parts}
    return [{"role": "system", "content": system}, *history]


class _Speaker:
    """Speaks finished sentences in the threadpool and releases the audio strictly in sentence order."""

    def __init__(self, ctx: RunCtx):
        self.ctx = ctx
        self.agg = SentenceAggregator()
        self.pending: deque[asyncio.Task] = deque()
        self.seq = 0

    def push(self, delta: str) -> None:
        for s in self.agg.push(delta):
            self._schedule(s)

    def flush(self) -> None:
        for s in self.agg.flush():
            self._schedule(s)

    def _schedule(self, sentence: str) -> None:
        if self.seq == 0 and not self.pending and self.ctx.timer:
            self.ctx.timer.stamp("first_sentence")
        self.pending.append(asyncio.ensure_future(run_in_threadpool(tts.speak, sentence, self.ctx.lang)))

    def _event(self, task: asyncio.Task) -> dict | None:
        try:
            wav = task.result()
        except Exception as e:  # noqa: BLE001 - a sentence that cannot be spoken is skipped, the text still shows
            log.warning("tts failed: %s", type(e).__name__)
            return None
        if self.seq == 0 and self.ctx.timer:
            self.ctx.timer.stamp("first_audio_ready")
        ev = agui.custom("audio", {"seq": self.seq, "wav_b64": base64.b64encode(wav).decode()})
        self.seq += 1
        return ev

    def ready(self) -> list[dict]:
        out = []
        while self.pending and self.pending[0].done():
            ev = self._event(self.pending.popleft())
            if ev:
                out.append(ev)
        return out

    async def drain(self) -> AsyncIterator[dict]:
        while self.pending:
            task = self.pending[0]
            await asyncio.wait({task})
            ev = self._event(self.pending.popleft())
            if ev:
                yield ev

    def cancel(self) -> None:
        for t in self.pending:
            t.cancel()
        self.pending.clear()


def _accumulate(calls: dict[int, dict], deltas: list[dict]) -> None:
    for tc in deltas:
        slot = calls.setdefault(tc.get("index", len(calls)), {"id": None, "name": "", "arguments": ""})
        if tc.get("id"):
            slot["id"] = tc["id"]
        fn = tc.get("function") or {}
        if fn.get("name"):
            slot["name"] += fn["name"]
        if fn.get("arguments"):
            slot["arguments"] += fn["arguments"]


async def stream_run(ctx: RunCtx) -> AsyncIterator[dict]:
    """Yield AG-UI events for one reply (no RUN_STARTED/RUN_FINISHED: the run owns those)."""
    had_audio = bool(ctx.audio)
    async for ev in listen.prelude(ctx):  # transcribing step, CUSTOM transcript, listen gate, CUSTOM timing
        yield ev
    if had_audio and ctx.user_message_id and ctx.con is not None:
        await run_in_threadpool(conversations.set_content, ctx.con, ctx.user_message_id, ctx.user_text)
    if had_audio and not ctx.user_text.strip():  # nothing was heard: no reply to compose
        ctx.gated_out = True
    if ctx.gated_out:  # listen mode, not about the record: stay quiet
        return
    mid = ctx.message_id
    started = False
    shown: list[dict] = []  # safety blocks already emitted, so each appears once per reply
    speaker = _Speaker(ctx) if ctx.speak else None

    def block(b: dict):
        if b.get("type") in ("disclaimer", "refusal"):
            if b in shown:
                return None
            shown.append(b)
        return agui.custom("block", b)

    forced = safety.precheck(ctx.user_text)
    if forced:  # deterministic: shown even if the model never calls decline_medical_advice
        yield block(safety.refusal(forced))

    messages = await run_in_threadpool(_messages, ctx, forced)
    try:
        for step in range(MAX_STEPS):
            payload = {"messages": messages, "tools": tools.SCHEMAS, "stream": True, "temperature": TEMPERATURE}
            content: list[str] = []
            calls: dict[int, dict] = {}
            stream = _llm_stream(payload)
            try:
                async for chunk in stream:
                    if ctx.run.cancel.is_set():
                        break
                    choices = chunk.get("choices") or []
                    delta = (choices[0].get("delta") or {}) if choices else {}
                    piece = delta.get("content")
                    if piece:
                        if not started:
                            started = True
                            if ctx.timer:
                                ctx.timer.stamp("first_token")
                            yield agui.text_start(mid)
                        content.append(piece)
                        yield agui.text_delta(mid, piece)
                        if speaker:
                            speaker.push(piece)
                            for ev in speaker.ready():
                                yield ev
                    if delta.get("tool_calls"):
                        _accumulate(calls, delta["tool_calls"])
            except (LLMUnavailable, httpx.HTTPError, json.JSONDecodeError) as e:
                log.warning("run %s: llm unavailable: %s", ctx.run.id, type(e).__name__)
                if started:
                    yield agui.text_end(mid)
                    started = False
                yield agui.run_error("errors.llm_unavailable", "llm_unavailable")
                return
            finally:
                await stream.aclose()  # closes the upstream HTTP stream (stops generation on cancel)
            if ctx.run.cancel.is_set() or not calls:
                break
            ordered = [calls[i] for i in sorted(calls)]
            for n, c in enumerate(ordered):
                c["id"] = c["id"] or f"call_{step}_{n}"
            messages.append({"role": "assistant", "content": "".join(content) or None, "tool_calls": [
                {"id": c["id"], "type": "function", "function": {"name": c["name"], "arguments": c["arguments"] or "{}"}}
                for c in ordered]})
            for c in ordered:
                async for ev in _run_tool(ctx, c, block):
                    yield ev
                if ctx.run.cancel.is_set():
                    break
                messages.append({"role": "tool", "tool_call_id": c["id"], "content": c["result"]})
            if ctx.run.cancel.is_set():
                break
        if speaker and not ctx.run.cancel.is_set():
            speaker.flush()
            async for ev in speaker.drain():
                yield ev
        if started:
            yield agui.text_end(mid)
            started = False
        if ctx.timer:
            yield agui.custom("timing", ctx.timer.as_dict())
    finally:
        if speaker:
            speaker.cancel()


async def _run_tool(ctx: RunCtx, call: dict, block) -> AsyncIterator[dict]:
    """Run one tool call; leaves the JSON result for the model in call["result"]."""
    name = call["name"]
    yield agui.tool_start(call["id"], name)
    fn = tools.TOOLS.get(name)
    result: dict
    if fn is None:
        result = {"error": "unknown_tool", "name": name, "message": "No such tool. Use only the tools listed."}
    else:
        try:
            args = json.loads(call["arguments"] or "{}")
            if not isinstance(args, dict):
                raise ValueError("arguments must be an object")
        except ValueError:
            args = None
            result = {"error": "bad_arguments", "message": "The arguments were not a valid JSON object."}
        if args is not None:
            step = tools.STEPS.get(name)
            if step:
                yield agui.step_started(step)
            try:
                result, blocks, _ = await run_in_threadpool(fn, ctx.con, ctx.profile_id, args, ctx)
            except Exception as e:  # noqa: BLE001 - a broken tool is reported to the model, the run goes on
                log.error("run %s: tool %s raised %s", ctx.run.id, name, type(e).__name__)
                result, blocks = {"error": "tool_failed"}, []
            sources = result.pop("_sources", None)
            extra_steps = [x for x in (result.pop("_steps", None) or []) if x != step]
            for b in blocks:
                ev = block(b)
                if ev:
                    yield ev
            if sources:
                ctx.sources.extend(sources)
                yield agui.custom("sources", sources)
            if step:
                yield agui.step_finished(step)
            for x in extra_steps:  # later phases of one tool (e.g. answering_form), reported once the tool returns
                yield agui.step_started(x)
                yield agui.step_finished(x)
    yield agui.tool_end(call["id"])
    call["result"] = json.dumps(result, ensure_ascii=False)
