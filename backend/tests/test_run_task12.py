"""Task 12 carried requirements on the run plumbing and the REST additions."""

import asyncio
import json
import re
import time

import pytest

from kapiling.chat import agent, agui, conversations, routes, runs
from tests.test_agent import FakeLLM, text, tool_call
from tests.test_agui import run_data, sse


@pytest.fixture
def fake_llm(monkeypatch):
    f = FakeLLM()
    monkeypatch.setattr(agent, "_llm_stream", f.stream)
    return f


# --- R19: the deadline bounds the time to the first event --------------------------------

def test_deadline_passes_when_nothing_is_streamed_in_time(client, con, lola_unlocked, monkeypatch):
    async def mute(ctx):
        await asyncio.sleep(1.0)
        yield agui.text_start(ctx.message_id)

    monkeypatch.setattr(agent, "stream_run", mute)
    monkeypatch.setattr(runs, "COMPOSING_DEADLINE_S", 0.1)
    t = time.monotonic()
    events = sse(client.post("/api/runs", data=run_data(lola_unlocked)))
    assert time.monotonic() - t < 0.9
    assert events[-2] == {"type": "RUN_ERROR", "message": "errors.timeout", "code": "timeout"}
    assert events[-1]["result"]["status"] == "failed"


def test_long_answer_still_streaming_at_the_deadline_completes(client, con, lola_unlocked, slow_agent, monkeypatch):
    # slow_agent's first event is immediate; the whole answer takes ~0.5 s, well past the 0.12 s deadline.
    monkeypatch.setattr(runs, "COMPOSING_DEADLINE_S", 0.12)
    events = sse(client.post("/api/runs", data=run_data(lola_unlocked)))
    assert not [e for e in events if e["type"] == "RUN_ERROR"]
    assert events[-1]["result"]["status"] == "complete"
    row = con.execute("select content, status from messages where id=?", (events[-1]["result"]["messageId"],)).fetchone()
    assert tuple(row) == ("Partial..........", "complete")


# --- robustness ----------------------------------------------------------------------------

def test_message_id_is_server_side(client, con, lola_unlocked, monkeypatch):
    seen = {}

    async def blocks_only(ctx):
        seen["mid"] = ctx.message_id
        yield agui.custom("block", {"type": "disclaimer"})

    monkeypatch.setattr(agent, "stream_run", blocks_only)
    events = sse(client.post("/api/runs", data=run_data(lola_unlocked)))
    mid = events[-1]["result"]["messageId"]
    assert re.fullmatch(r"[0-9a-f]{32}", mid) and mid == seen["mid"]
    assert con.execute("select blocks from messages where id=?", (mid,)).fetchone()[0] == '[{"type": "disclaimer"}]'


def test_failed_save_finishes_with_null_message_id(client, con, lola_unlocked, echo_agent, monkeypatch):
    real = conversations.append

    def failing(con_, cid, role, *a, **k):
        if role == "assistant":
            raise RuntimeError("disk full")
        return real(con_, cid, role, *a, **k)

    monkeypatch.setattr(conversations, "append", failing)
    events = sse(client.post("/api/runs", data=run_data(lola_unlocked)))
    assert events[-1]["type"] == "RUN_FINISHED"
    assert events[-1]["result"] == {"messageId": None, "status": "failed"}
    assert events[-2]["code"] == "internal"


class FakeCon:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def _ctx(lola, cid="c-test"):
    return agent.RunCtx(con=None, run=runs.start(lola), profile_id=lola, conversation_id=cid, lang="tl", mode="text",
                        speak=False, user_text="x", images=[], audio=None, message_id="m-x")


def test_cancelling_the_run_task_still_finishes_and_closes(lola, monkeypatch):
    fake = FakeCon()
    monkeypatch.setattr(routes.db, "connect", lambda: fake)

    async def hang(ctx):
        yield agui.text_start(ctx.message_id)
        await asyncio.sleep(30)

    monkeypatch.setattr(agent, "stream_run", hang)
    ctx = _ctx(lola)

    async def main():
        q: asyncio.Queue = asyncio.Queue()
        task = asyncio.create_task(routes._drive(ctx.run, ctx, q))
        async with asyncio.timeout(2):
            while q.qsize() < 2:  # RUN_STARTED, TEXT_MESSAGE_START
                await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task  # our own cancellation is not swallowed
        events = []
        while not q.empty():
            events.append(q.get_nowait())
        return events

    events = asyncio.run(main())
    assert events[-1]["type"] == "RUN_FINISHED" and events[-1]["result"]["messageId"] is None
    assert fake.closed
    assert runs.get(ctx.run.id) is None


def test_wait_on_a_stubborn_pump_is_bounded(lola, monkeypatch):
    monkeypatch.setattr(routes, "PUMP_GRACE_S", 0.1)

    async def stubborn(ctx):
        yield agui.text_start(ctx.message_id)
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            await asyncio.sleep(0.6)  # ignores the first cancel for a while

    monkeypatch.setattr(agent, "stream_run", stubborn)
    ctx = _ctx(lola)
    reply = routes._Reply()

    async def main():
        async def cancel_soon():
            await asyncio.sleep(0.05)
            ctx.run.cancel.set()

        asyncio.create_task(cancel_soon())
        t = time.monotonic()
        status, err = await routes._compose(ctx.run, ctx, reply, lambda e: None)
        elapsed = time.monotonic() - t
        await asyncio.sleep(0.7)  # let the stubborn task end before the loop closes
        return status, err, elapsed

    status, err, elapsed = asyncio.run(main())
    runs.finish(ctx.run.id)
    assert status == "stopped" and err["code"] == "cancelled" and elapsed < 0.45


def test_agent_that_returns_on_cancel_is_stopped(lola, monkeypatch):
    async def polite(ctx):
        yield agui.text_start(ctx.message_id)
        ctx.run.cancel.set()
        yield agui.text_delta(ctx.message_id, "x")
        yield agui.text_end(ctx.message_id)  # returns by itself, like the real agent does on cancel

    monkeypatch.setattr(agent, "stream_run", polite)
    ctx = _ctx(lola)
    status, err = asyncio.run(routes._compose(ctx.run, ctx, routes._Reply(), lambda e: None))
    runs.finish(ctx.run.id)
    assert status == "stopped" and err["code"] == "cancelled"


def test_close_goes_through_the_threadpool(client, lola_unlocked, echo_agent, monkeypatch):
    calls = []
    real = routes.run_in_threadpool

    async def spy(fn, *a, **k):
        calls.append(getattr(fn, "__name__", repr(fn)))
        return await real(fn, *a, **k)

    monkeypatch.setattr(routes, "run_in_threadpool", spy)
    sse(client.post("/api/runs", data=run_data(lola_unlocked)))
    assert "close" in calls


# --- the real agent behind /api/runs --------------------------------------------------------

def test_default_agent_runs_tools_and_saves_blocks(client, con, lola_unlocked, fake_llm):
    fake_llm.script([tool_call("plan_meals", {"days": 3})], [text("Heto po.")])
    events = sse(client.post("/api/runs", data=run_data(lola_unlocked, message="meal plan", lang="tl")))
    types = [e["type"] for e in events]
    assert types[0] == "RUN_STARTED" and types[-1] == "RUN_FINISHED"
    mid = events[-1]["result"]["messageId"]
    assert mid == next(e["messageId"] for e in events if e["type"] == "TEXT_MESSAGE_START")
    row = con.execute("select content, blocks, steps, status from messages where id=?", (mid,)).fetchone()
    assert row["content"] == "Heto po." and row["status"] == "complete"
    assert {"type": "disclaimer"} in json.loads(row["blocks"]) and json.loads(row["steps"]) == ["planning_meals"]
    stamps = con.execute("select stamps from turn_timings where message_id=?", (mid,)).fetchone()
    assert stamps and "first_token" in json.loads(stamps[0])


def test_llm_down_run_is_failed_with_key(client, con, lola_unlocked, monkeypatch):
    async def down(payload):
        raise agent.LLMUnavailable("x")
        yield

    monkeypatch.setattr(agent, "_llm_stream", down)
    events = sse(client.post("/api/runs", data=run_data(lola_unlocked)))
    assert events[-2] == {"type": "RUN_ERROR", "message": "errors.llm_unavailable", "code": "llm_unavailable"}
    assert events[-1]["result"]["status"] == "failed"


# --- POST /api/speak ---------------------------------------------------------------------------

@pytest.fixture
def fake_speak(monkeypatch):
    from kapiling.voice import tts

    said = []
    monkeypatch.setattr(tts, "speak", lambda t, lang: said.append((t, lang)) or b"RIFF0000WAVE")
    return said


def test_speak_returns_wav(client, lola_unlocked, fake_speak):
    r = client.post("/api/speak", data={"text": "Magandang umaga po.", "lang": "tl"})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/wav" and r.content == b"RIFF0000WAVE"
    assert fake_speak == [("Magandang umaga po.", "tl")]


def test_speak_is_locked(client, fake_speak):
    assert client.post("/api/speak", data={"text": "hi", "lang": "en"}).status_code == 401


@pytest.mark.parametrize("data", [{"text": "x" * 401, "lang": "tl"}, {"text": "  ", "lang": "tl"},
                                  {"text": "hi", "lang": "fr"}])
def test_speak_bad_input(client, lola_unlocked, fake_speak, data):
    r = client.post("/api/speak", data=data)
    assert r.status_code == 400 and r.json()["detail"] == "errors.bad_input" and fake_speak == []


def test_speak_400_chars_is_fine(client, lola_unlocked, fake_speak):
    assert client.post("/api/speak", data={"text": "x" * 400, "lang": "en"}).status_code == 200


# --- DELETE /api/documents/{doc_id}/observations/{oid} ------------------------------------------

def _doc_with_obs(con, pid, status):
    did = con.execute("insert into documents (profile_id, title, kind, file_path, mime, sha256, status) "
                      "values (?,?,?,?,?,?, 'indexed')", (pid, "Lab", "lab", "x/1.jpg", "image/jpeg",
                                                          f"sha-{status}-{pid}")).lastrowid
    oid = con.execute("insert into observations (profile_id, code, label, value, unit, date, document_id, status) "
                      "values (?,?,?,?,?,?,?,?)", (pid, "fbs", "FBS", 140, "mg/dL", "2026-09-01", did, status)).lastrowid
    con.commit()
    return did, oid


def test_reject_deletes_a_proposed_observation(client, con, lola_unlocked):
    did, oid = _doc_with_obs(con, lola_unlocked, "proposed")
    assert client.delete(f"/api/documents/{did}/observations/{oid}").status_code == 204
    assert con.execute("select 1 from observations where id=?", (oid,)).fetchone() is None
    row = con.execute("select action, target from access_log order by id desc").fetchone()
    assert row["action"] == "reject_observation" and str(oid) in row["target"]


def test_reject_confirmed_is_409(client, con, lola_unlocked):
    did, oid = _doc_with_obs(con, lola_unlocked, "confirmed")
    assert client.delete(f"/api/documents/{did}/observations/{oid}").status_code == 409
    assert con.execute("select 1 from observations where id=?", (oid,)).fetchone() is not None


def test_reject_unknown_is_404(client, con, lola_unlocked):
    did, oid = _doc_with_obs(con, lola_unlocked, "proposed")
    assert client.delete(f"/api/documents/{did}/observations/999999").status_code == 404
    other, _ = _doc_with_obs(con, lola_unlocked, "confirmed")
    assert client.delete(f"/api/documents/{other}/observations/{oid}").status_code == 404  # wrong document
    assert client.delete(f"/api/documents/999999/observations/{oid}").status_code == 404


def test_reject_other_profile_is_403(client, con, lola, mika_unlocked):
    did, oid = _doc_with_obs(con, lola, "proposed")
    assert client.delete(f"/api/documents/{did}/observations/{oid}").status_code == 403
    assert con.execute("select 1 from observations where id=?", (oid,)).fetchone() is not None


def test_reject_requires_session(client, con, lola):
    did, oid = _doc_with_obs(con, lola, "proposed")
    assert client.delete(f"/api/documents/{did}/observations/{oid}").status_code == 401


# --- TTS warm-up on startup ----------------------------------------------------------------------

def test_tts_warm_up_loads_both_voices_in_background(con, monkeypatch):
    from fastapi.testclient import TestClient

    from kapiling import main
    from kapiling.voice import tts

    loaded = []
    monkeypatch.setattr(tts, "load", lambda lang: loaded.append(lang))
    monkeypatch.setattr(main, "TTS_WARM", True)
    with TestClient(main.app, client=("127.0.0.1", 50000)):
        deadline = time.monotonic() + 2
        while len(loaded) < 2 and time.monotonic() < deadline:
            time.sleep(0.01)
    assert loaded == ["tl", "en"]


def test_tts_warm_up_is_off_in_tests(con, monkeypatch):
    from fastapi.testclient import TestClient

    from kapiling import main
    from kapiling.voice import tts

    loaded = []
    monkeypatch.setattr(tts, "load", lambda lang: loaded.append(lang))
    assert main.TTS_WARM is False
    with TestClient(main.app, client=("127.0.0.1", 50000)):
        time.sleep(0.05)
    assert loaded == []


def test_prompt_cache_warm_up_sends_one_request_with_tools(con, lola, fake_llm):
    fake_llm.script([text("")])
    asyncio.run(agent.warm_prompt_cache())
    assert len(fake_llm.payloads) == 1
    p = fake_llm.payloads[0]
    assert p["max_tokens"] == 1 and p["tools"] == json.loads(json.dumps(agent.tools.SCHEMAS))
    # The same system prompt a run for the first profile gets, so the cached prefix is reused.
    from kapiling.chat import prompts
    assert p["messages"][0] == {"role": "system", "content": prompts.system_prompt(con, lola, "tl")}


def test_prompt_cache_warm_up_swallows_errors(con, monkeypatch):
    calls = []

    async def down(payload):
        calls.append(payload)
        raise agent.LLMUnavailable("ConnectError")
        yield

    monkeypatch.setattr(agent, "_llm_stream", down)
    asyncio.run(agent.warm_prompt_cache())  # does not raise
    assert len(calls) == 1


def test_prompt_cache_warm_up_runs_on_startup_without_blocking(con, monkeypatch):
    from fastapi.testclient import TestClient

    from kapiling import main

    seen = []

    async def hung(payload):
        seen.append(payload)
        await asyncio.sleep(5)  # a hung LLM must not hold up startup
        yield {}

    monkeypatch.setattr(agent, "_llm_stream", hung)
    monkeypatch.setattr(main, "LLM_WARM", True)
    t = time.monotonic()
    with TestClient(main.app, client=("127.0.0.1", 50000)) as c:
        assert c.get("/api/health").status_code == 200
        deadline = time.monotonic() + 2
        while not seen and time.monotonic() < deadline:
            time.sleep(0.01)
    assert len(seen) == 1 and time.monotonic() - t < 4


def test_prompt_cache_warm_up_is_off_in_tests():
    from kapiling import main

    assert main.LLM_WARM is False


def test_tts_warm_up_failure_is_harmless(con, monkeypatch):
    from fastapi.testclient import TestClient

    from kapiling import main
    from kapiling.voice import tts

    def missing(lang):
        raise OSError("model not cached")

    monkeypatch.setattr(tts, "load", missing)
    monkeypatch.setattr(main, "TTS_WARM", True)
    with TestClient(main.app, client=("127.0.0.1", 50000)) as c:
        time.sleep(0.05)
        assert c.get("/api/health").status_code == 200
