import dataclasses

from fastapi.testclient import TestClient

from kapiling import config, db
from kapiling.demo import NoPairing


def _demo(monkeypatch, on):
    monkeypatch.setattr(config, "settings", dataclasses.replace(config.settings, demo=on))


def test_reset_is_404_when_demo_is_off(client, monkeypatch):
    _demo(monkeypatch, False)
    assert client.post("/api/demo/reset").status_code == 404
    assert client.get("/api/demo").json() == {"demo": False}


def test_reset_wipes_and_reseeds_only_the_data_dir(client, con, monkeypatch, tmp_path):
    _demo(monkeypatch, True)
    con.execute("update profiles set full_name='Edited' where nickname='Lola Remy'")
    con.commit()
    upload = config.settings.data_dir / "files" / "upload.txt"
    upload.parent.mkdir(exist_ok=True)
    upload.write_text("x")
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("keep")
    assert client.get("/api/demo").json() == {"demo": True}
    assert client.post("/api/demo/reset").status_code == 204
    c = db.connect()
    try:
        names = [r[0] for r in c.execute("select full_name from profiles")]
    finally:
        c.close()
    assert "Edited" not in names and len(names) == 2
    assert not upload.exists()
    assert outside.read_text() == "keep"


def test_demo_wrapper_lets_remote_clients_past_pairing(con):
    from kapiling.main import app

    remote = TestClient(app, client=("10.0.0.5", 5000))
    assert remote.get("/api/access-log").status_code == 403  # no pairing key
    wrapped = TestClient(NoPairing(app), client=("10.0.0.5", 5000))
    assert wrapped.get("/api/access-log").status_code == 401  # past pairing, stopped by the PIN lock
