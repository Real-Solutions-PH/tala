import dataclasses
import os

# Before kapiling is imported: no ingestion worker in tests, and no Hugging Face network calls.
os.environ.setdefault("KAPILING_WORKER", "0")
os.environ.setdefault("HF_HUB_OFFLINE", "1")

import pytest

from kapiling import config, db
from seed import persona


@pytest.fixture
def con(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "settings", dataclasses.replace(config.settings, data_dir=tmp_path))
    c = db.connect()
    persona.seed(c)
    yield c
    c.close()


@pytest.fixture
def lola(con):
    return con.execute("select id from profiles where nickname='Lola Remy'").fetchone()[0]


@pytest.fixture
def mika(con):
    return con.execute("select id from profiles where nickname='Mika'").fetchone()[0]


@pytest.fixture
def client(con):
    from fastapi.testclient import TestClient

    from kapiling.db import get_con
    from kapiling.main import app

    app.dependency_overrides[get_con] = lambda: con
    # Loopback client address so the pairing middleware lets requests through.
    with TestClient(app, client=("127.0.0.1", 50000)) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _fresh_auth_state():
    """Sessions and unlock backoff live in process memory; isolate them per test."""
    from kapiling.auth import lock

    lock.reset_state()
    yield
    lock.reset_state()


def _unlock(client, pid):
    r = client.post("/api/unlock", json={"profile_id": pid, "pin": persona.OWNER_PIN})
    assert r.status_code == 204, r.text
    assert "kapiling_s" in client.cookies
    return pid


@pytest.fixture
def lola_unlocked(client, lola):
    return _unlock(client, lola)


@pytest.fixture
def mika_unlocked(client, mika):
    return _unlock(client, mika)


# --- Task 8: chat run seams -------------------------------------------------

async def _echo_stream_run(ctx):
    """The echo agent, pinned here so the run tests keep working after Task 12 replaces the real one."""
    import uuid

    from kapiling.chat import agui

    yield agui.step_started("check_profile")
    yield agui.step_finished("check_profile")
    mid = uuid.uuid4().hex
    yield agui.text_start(mid)
    yield agui.text_delta(mid, ctx.user_text)
    yield agui.text_end(mid)


@pytest.fixture
def echo_agent(monkeypatch):
    from kapiling.chat import agent

    monkeypatch.setattr(agent, "stream_run", _echo_stream_run)


@pytest.fixture
def slow_agent(monkeypatch):
    """Streams 'Partial' then one '.' every 50 ms, 10 times (about half a second), then finishes."""
    import asyncio
    import uuid

    from kapiling.chat import agent, agui

    async def slow(ctx):
        yield agui.step_started("search_records")
        mid = uuid.uuid4().hex
        yield agui.text_start(mid)
        yield agui.text_delta(mid, "Partial")
        for _ in range(10):
            await asyncio.sleep(0.05)
            yield agui.text_delta(mid, ".")
        yield agui.text_end(mid)
        yield agui.step_finished("search_records")

    monkeypatch.setattr(agent, "stream_run", slow)


@pytest.fixture
def lola_conversation(con, lola):
    from kapiling.chat import conversations

    cid = conversations.create(con, lola, "Ano ang gamot ko?")
    conversations.append(con, cid, "user", "Ano ang gamot ko?")
    conversations.append(con, cid, "assistant", "Losartan po.")
    return cid
