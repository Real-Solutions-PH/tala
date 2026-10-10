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
