import dataclasses

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


@pytest.fixture
def lola_unlocked(lola):
    # Task 6 replaces this with a real unlock (cookie session).
    return lola
