import dataclasses

from kapiling import config, db
from seed import persona


def test_main_seeds_once_and_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "settings", dataclasses.replace(config.settings, data_dir=tmp_path))
    persona.main()
    persona.main()
    con = db.connect()
    assert con.execute("select count(*) from profiles").fetchone()[0] == 2
    con.close()
