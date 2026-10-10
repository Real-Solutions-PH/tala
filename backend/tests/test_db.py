from kapiling import config
from kapiling.auth.lock import verify_pin


def test_schema_applies_and_vec_loads(con):
    assert con.execute("PRAGMA user_version").fetchone()[0] == 1
    assert con.execute("select vec_version()").fetchone()[0]


def test_seed_has_two_profiles_with_essentials(con):
    lola = con.execute("select * from profiles where nickname='Lola Remy'").fetchone()
    assert lola["blood_type"] == "O+"
    assert con.execute("select count(*) from allergies where profile_id=?", (lola["id"],)).fetchone()[0] >= 1
    assert con.execute("select count(*) from medications where profile_id=? and active=1", (lola["id"],)).fetchone()[0] == 3
    assert con.execute("select count(*) from cards where profile_id=?", (lola["id"],)).fetchone()[0] == 4
    assert con.execute("select count(*) from observations where code='fbs' and profile_id=?", (lola["id"],)).fetchone()[0] >= 6


def test_profile_delete_cascades(con):
    pid = con.execute("select id from profiles where nickname='Mika'").fetchone()[0]
    con.execute("delete from profiles where id=?", (pid,))
    assert con.execute("select count(*) from vaccines where profile_id=?", (pid,)).fetchone()[0] == 0


def test_seed_pins_and_files(con, lola, mika):
    h = con.execute("select pin_hash from owner_lock where profile_id=?", (lola,)).fetchone()[0]
    assert h.startswith("scrypt$") and verify_pin("123456", h) and not verify_pin("000000", h)
    r = con.execute("select pin_hash from representatives where profile_id=?", (lola,)).fetchone()[0]
    assert verify_pin("246810", r)
    for row in con.execute("select front_path, back_path from cards where profile_id=?", (lola,)):
        assert (config.settings.data_dir / row[0]).is_file()
        assert (config.settings.data_dir / row[1]).is_file()
    photo = con.execute("select photo_path from profiles where id=?", (lola,)).fetchone()[0]
    assert (config.settings.data_dir / photo).is_file()
    assert con.execute("select count(*) from documents").fetchone()[0] == 0


def test_mika_has_one_overdue_vaccine(con, mika):
    rows = con.execute("select * from vaccines where profile_id=? and date is null and next_due < date('now')", (mika,)).fetchall()
    assert len(rows) == 1


def test_get_con_is_one_connection_per_request(con):
    """R17: a shared connection let one request's commit/rollback interleave with another's."""
    import sqlite3
    from typing import Annotated

    import pytest
    from fastapi import Depends, FastAPI
    from fastapi.testclient import TestClient

    from kapiling.db import get_con

    seen: list[sqlite3.Connection] = []
    app = FastAPI()

    @app.get("/w")
    def write(c: Annotated[sqlite3.Connection, Depends(get_con)]):
        seen.append(c)
        c.execute("insert into access_log (profile_id, actor, action) values (1, 'a', 'kept')")
        c.commit()

    @app.get("/r")
    def rollback(c: Annotated[sqlite3.Connection, Depends(get_con)]):
        seen.append(c)
        c.execute("insert into access_log (profile_id, actor, action) values (1, 'a', 'dropped')")
        c.rollback()

    with TestClient(app) as tc:
        tc.get("/w")
        tc.get("/r")
        tc.get("/w")
    assert len({id(c) for c in seen}) == 3
    for c in seen:  # each one was closed when its request ended
        with pytest.raises(sqlite3.ProgrammingError):
            c.execute("select 1")
    acts = [r[0] for r in con.execute("select action from access_log where actor='a'")]
    assert acts == ["kept", "kept"]


def test_connect_twice_does_not_rerun_migrations(con, monkeypatch):
    from kapiling import db

    monkeypatch.setattr(db, "MIGRATIONS", ["this is not sql"])  # would raise if executed again
    db.connect().close()

