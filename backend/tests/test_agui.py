import asyncio
import io
import json

import httpx
import pytest
from PIL import Image

from kapiling.chat import agui, runs


def sse(r) -> list[dict]:
    assert r.status_code == 200, r.text
    frames = r.content.split(b"\n\n")
    assert frames[-1] == b""
    out = []
    for f in frames[:-1]:
        assert f.startswith(b"data: ")
        out.append(json.loads(f[len(b"data: "):]))
    return out


def run_data(pid, **extra):
    return {"profile_id": pid, "message": "hello", "lang": "en", "mode": "text", **extra}


def png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), "white").save(buf, "PNG")
    return buf.getvalue()


# --- encoding ------------------------------------------------------------------

def test_encode_is_one_sse_frame():
    assert agui.encode(agui.text_delta("m1", "hi")) == b'data: {"type":"TEXT_MESSAGE_CONTENT","messageId":"m1","delta":"hi"}\n\n'


def test_constructors_match_c3():
    assert agui.run_started("t", "r") == {"type": "RUN_STARTED", "threadId": "t", "runId": "r"}
    assert agui.step_started("search_records") == {"type": "STEP_STARTED", "stepName": "search_records"}
    assert agui.step_finished("search_records") == {"type": "STEP_FINISHED", "stepName": "search_records"}
    assert agui.tool_start("c1", "get_medications") == {"type": "TOOL_CALL_START", "toolCallId": "c1",
                                                        "toolCallName": "get_medications"}
    assert agui.tool_end("c1") == {"type": "TOOL_CALL_END", "toolCallId": "c1"}
    assert agui.text_start("m") == {"type": "TEXT_MESSAGE_START", "messageId": "m", "role": "assistant"}
    assert agui.text_end("m") == {"type": "TEXT_MESSAGE_END", "messageId": "m"}
    assert agui.custom("block", {"type": "disclaimer"}) == {"type": "CUSTOM", "name": "block",
                                                           "value": {"type": "disclaimer"}}
    assert agui.run_error("errors.timeout", "timeout") == {"type": "RUN_ERROR", "message": "errors.timeout",
                                                           "code": "timeout"}
    assert agui.run_finished("t", "r", "m", "complete") == {
        "type": "RUN_FINISHED", "threadId": "t", "runId": "r", "result": {"messageId": "m", "status": "complete"}}


def test_encode_keeps_tagalog_and_newlines_in_one_frame():
    frame = agui.encode(agui.text_delta("m", "Ñ\n\nopo"))
    assert frame.count(b"\n\n") == 1 and "Ñ".encode() in frame


# --- validation before the stream (G-C-012) --------------------------------------

def test_bad_input_is_a_400_not_an_empty_stream(client, lola_unlocked):
    r = client.post("/api/runs", data={"profile_id": lola_unlocked, "lang": "tl", "mode": "text"})
    assert r.status_code == 400
    assert r.json()["detail"] == "errors.bad_input"


@pytest.mark.parametrize("field,value", [("lang", "fr"), ("mode", "shout"), ("lang", ""), ("message", "   ")])
def test_bad_fields_are_400(client, lola_unlocked, field, value):
    r = client.post("/api/runs", data=run_data(lola_unlocked, **{field: value}))
    assert r.status_code == 400 and r.json()["detail"] == "errors.bad_input"


def test_run_requires_session(client, lola):
    assert client.post("/api/runs", data=run_data(lola)).status_code == 401


def test_run_for_another_profile_is_403(client, lola, mika_unlocked):
    assert client.post("/api/runs", data=run_data(lola)).status_code == 403


def test_run_on_another_profiles_conversation_is_403(client, mika_unlocked, lola_conversation):
    r = client.post("/api/runs", data=run_data(mika_unlocked, conversation_id=lola_conversation))
    assert r.status_code == 403


def test_run_on_unknown_conversation_is_404(client, lola_unlocked):
    assert client.post("/api/runs", data=run_data(lola_unlocked, conversation_id="nope")).status_code == 404


def test_non_image_file_is_415(client, con, lola_unlocked):
    r = client.post("/api/runs", data=run_data(lola_unlocked), files={"files": ("x.jpg", b"not an image", "image/jpeg")})
    assert r.status_code == 415
    assert con.execute("select count(*) from conversations where profile_id=?", (lola_unlocked,)).fetchone()[0] == 0


def test_oversized_audio_is_413(client, lola_unlocked, monkeypatch):
    from kapiling.chat import routes

    monkeypatch.setattr(routes, "MAX_AUDIO", 10)
    r = client.post("/api/runs", data=run_data(lola_unlocked), files={"audio": ("a.webm", b"x" * 11, "audio/webm")})
    assert r.status_code == 413


def test_image_only_run_streams(client, con, lola_unlocked, echo_agent):
    data = run_data(lola_unlocked)
    del data["message"]
    events = sse(client.post("/api/runs", data=data, files={"files": ("p.png", png_bytes(), "image/png")}))
    assert events[-1]["result"]["status"] == "complete"
    att = con.execute("select attachments from messages where role='user'").fetchone()[0]
    assert json.loads(att) == [{"type": "image"}]


def test_audio_only_run_streams(client, lola_unlocked, echo_agent):
    data = run_data(lola_unlocked, mode="voice")
    del data["message"]
    events = sse(client.post("/api/runs", data=data, files={"audio": ("a.webm", b"RIFFxxxx", "audio/webm")}))
    assert events[0]["type"] == "RUN_STARTED" and events[-1]["type"] == "RUN_FINISHED"


# --- the stream --------------------------------------------------------------------

def test_sse_headers(client, lola_unlocked, echo_agent):
    r = client.post("/api/runs", data=run_data(lola_unlocked))
    assert r.headers["content-type"].startswith("text/event-stream")
    assert r.headers["cache-control"] == "no-cache"
    assert r.headers["x-accel-buffering"] == "no"


def test_run_order_and_saved_id_on_finish(client, con, lola_unlocked, echo_agent):
    events = sse(client.post("/api/runs", data=run_data(lola_unlocked)))
    types = [e["type"] for e in events]
    assert types[0] == "RUN_STARTED" and types[-1] == "RUN_FINISHED"
    assert types[1:-1] == ["STEP_STARTED", "STEP_FINISHED", "TEXT_MESSAGE_START", "TEXT_MESSAGE_CONTENT",
                           "TEXT_MESSAGE_END"]
    mid = events[-1]["result"]["messageId"]
    assert events[-1]["result"]["status"] == "complete"
    assert mid == events[3]["messageId"]  # the streamed id is the saved id
    row = con.execute("select role, content, status, steps from messages where id=?", (mid,)).fetchone()
    assert row["role"] == "assistant" and row["content"] == "hello" and row["status"] == "complete"
    assert json.loads(row["steps"]) == ["check_profile"]
    assert runs.get(events[0]["runId"]) is None  # the registry forgets finished runs


def test_default_agent_is_the_real_one(client, con, lola_unlocked, monkeypatch):
    """Task 12 replaced the echo: the default agent asks the LLM (here a one-chunk fake)."""
    from kapiling.chat import agent

    async def one(payload):
        yield {"choices": [{"index": 0, "delta": {"content": "Opo."}}]}

    monkeypatch.setattr(agent, "_llm_stream", one)
    events = sse(client.post("/api/runs", data=run_data(lola_unlocked, message="kumusta")))
    assert "".join(e["delta"] for e in events if e["type"] == "TEXT_MESSAGE_CONTENT") == "Opo."


def test_blocks_and_sources_are_saved(client, con, lola_unlocked, monkeypatch):
    from kapiling.chat import agent

    async def rich(ctx):
        yield agui.text_start("m-rich")
        yield agui.text_delta("m-rich", "Ito po")
        yield agui.text_end("m-rich")
        yield agui.custom("block", {"type": "disclaimer"})
        yield agui.custom("sources", [{"n": 1, "chunk_id": 3}])

    monkeypatch.setattr(agent, "stream_run", rich)
    events = sse(client.post("/api/runs", data=run_data(lola_unlocked)))
    row = con.execute("select blocks, sources from messages where id='m-rich'").fetchone()
    assert events[-1]["result"]["messageId"] == "m-rich"
    assert json.loads(row["blocks"]) == [{"type": "disclaimer"}]
    assert json.loads(row["sources"]) == [{"n": 1, "chunk_id": 3}]


def test_agent_crash_is_run_error_then_finished(client, con, lola_unlocked, monkeypatch):
    from kapiling.chat import agent

    async def boom(ctx):
        yield agui.text_start("m-boom")
        yield agui.text_delta("m-boom", "Kal")
        raise RuntimeError("secret patient detail")

    monkeypatch.setattr(agent, "stream_run", boom)
    events = sse(client.post("/api/runs", data=run_data(lola_unlocked)))
    types = [e["type"] for e in events]
    assert types[-3:] == ["TEXT_MESSAGE_END", "RUN_ERROR", "RUN_FINISHED"]
    assert events[-2] == {"type": "RUN_ERROR", "message": "errors.internal", "code": "internal"}
    assert events[-1]["result"]["status"] == "failed"
    row = con.execute("select content, status from messages where id='m-boom'").fetchone()
    assert tuple(row) == ("Kal", "failed")


def test_composing_deadline_is_timeout_error_and_failed(client, con, lola_unlocked, monkeypatch):
    """R19 (Task 12): the deadline bounds the time to the FIRST event; see test_run_task12 for the long-answer case."""
    from kapiling.chat import agent

    async def late(ctx):
        await asyncio.sleep(0.5)
        yield agui.text_start(ctx.message_id)

    monkeypatch.setattr(agent, "stream_run", late)
    monkeypatch.setattr(runs, "COMPOSING_DEADLINE_S", 0.12)
    events = sse(client.post("/api/runs", data=run_data(lola_unlocked)))
    assert events[-2] == {"type": "RUN_ERROR", "message": "errors.timeout", "code": "timeout"}
    assert events[-1]["type"] == "RUN_FINISHED" and events[-1]["result"]["status"] == "failed"
    row = con.execute("select content, status from messages where id=?", (events[-1]["result"]["messageId"],)).fetchone()
    assert row["status"] == "failed" and row["content"] == ""


def test_user_message_saved_at_start(client, con, lola_unlocked, echo_agent):
    events = sse(client.post("/api/runs", data=run_data(lola_unlocked, message="  Ano ang BP ko?  ")))
    rows = con.execute("select role, content from messages where conversation_id=? order by rowid",
                       (events[0]["threadId"],)).fetchall()
    assert [tuple(r) for r in rows] == [("user", "Ano ang BP ko?"), ("assistant", "Ano ang BP ko?")]


# --- raw ASGI: cancel mid-stream and disconnect --------------------------------------

class AsgiCall:
    """Drives the app over raw ASGI so a test can act mid-stream (TestClient buffers whole responses)."""

    def __init__(self, method, path, data, cookie):
        req = httpx.Request(method, "http://testserver" + path, data=data,
                            headers={"cookie": f"kapiling_s={cookie}"})
        self.body = req.read()
        self.scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method,
                      "scheme": "http", "path": path, "raw_path": path.encode(), "query_string": b"",
                      "root_path": "", "client": ("127.0.0.1", 50000), "server": ("testserver", 80),
                      "headers": [(k.lower().encode(), v.encode()) for k, v in req.headers.items()]}
        self.status = None
        self.events: list[dict] = []
        self.new_event = asyncio.Event()
        self.disconnected = asyncio.Event()
        self._sent = False
        self._buf = b""

    async def _receive(self):
        if not self._sent:
            self._sent = True
            return {"type": "http.request", "body": self.body, "more_body": False}
        await self.disconnected.wait()
        return {"type": "http.disconnect"}

    async def _send(self, msg):
        if msg["type"] == "http.response.start":
            self.status = msg["status"]
        elif msg["type"] == "http.response.body":
            self._buf += msg.get("body", b"")
            while b"\n\n" in self._buf:
                frame, self._buf = self._buf.split(b"\n\n", 1)
                if frame.startswith(b"data: "):
                    self.events.append(json.loads(frame[6:]))
            self.new_event.set()

    def start(self, app):
        return asyncio.create_task(app(self.scope, self._receive, self._send))

    async def wait_for(self, pred, timeout=5.0):
        async with asyncio.timeout(timeout):
            while not any(pred(e) for e in self.events):
                self.new_event.clear()
                await self.new_event.wait()


async def _wait_until(pred, timeout=5.0):
    async with asyncio.timeout(timeout):
        while not pred():
            await asyncio.sleep(0.02)


def test_cancel_saves_partial_as_stopped(client, con, lola_unlocked, slow_agent):
    from kapiling.main import app

    cookie = client.cookies.get("kapiling_s")

    async def main():
        call = AsgiCall("POST", "/api/runs", run_data(lola_unlocked), cookie)
        task = call.start(app)
        await call.wait_for(lambda e: e["type"] == "TEXT_MESSAGE_CONTENT")
        rid = call.events[0]["runId"]
        stop = AsgiCall("POST", f"/api/runs/{rid}/cancel", {}, cookie)
        await stop.start(app)
        assert stop.status == 204
        await asyncio.wait_for(task, 5)
        return call.events

    events = asyncio.run(main())
    types = [e["type"] for e in events]
    assert types[-3:] == ["TEXT_MESSAGE_END", "RUN_ERROR", "RUN_FINISHED"]
    assert events[-2]["code"] == "cancelled"
    assert events[-1]["result"]["status"] == "stopped"
    row = con.execute("select content, status from messages where id=?", (events[-1]["result"]["messageId"],)).fetchone()
    assert row["status"] == "stopped" and row["content"].startswith("Partial")
    assert len(row["content"]) < len("Partial") + 10  # it really stopped early


def test_cancel_by_another_profile_is_403(client, lola, mika_unlocked, monkeypatch):
    run = runs.start(lola)
    try:
        assert client.post(f"/api/runs/{run.id}/cancel").status_code == 403
        assert not run.cancel.is_set()
    finally:
        runs.finish(run.id)


def test_cancel_unknown_run_is_404(client, lola_unlocked):
    assert client.post("/api/runs/nope/cancel").status_code == 404


def test_cancel_requires_session(client):
    assert client.post("/api/runs/nope/cancel").status_code == 401


def test_disconnect_mid_run_still_saves(client, con, lola_unlocked, slow_agent):
    """EZ-D-017: the run is its own task, so a client that goes away does not stop it."""
    from kapiling.main import app

    cookie = client.cookies.get("kapiling_s")

    async def main():
        call = AsgiCall("POST", "/api/runs", run_data(lola_unlocked), cookie)
        task = call.start(app)
        await call.wait_for(lambda e: e["type"] == "TEXT_MESSAGE_CONTENT")
        call.disconnected.set()
        await asyncio.wait_for(task, 5)  # the response ends once the client is gone
        assert call.events[-1]["type"] != "RUN_FINISHED"
        tid, rid = call.events[0]["threadId"], call.events[0]["runId"]
        await _wait_until(lambda: runs.get(rid) is None)
        return tid

    tid = asyncio.run(main())
    row = con.execute("select content, status from messages where conversation_id=? and role='assistant'",
                      (tid,)).fetchone()
    assert row["status"] == "complete" and row["content"] == "Partial.........."
