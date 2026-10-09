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
