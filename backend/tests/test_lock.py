import dataclasses

import pytest
from fastapi.testclient import TestClient

from kapiling import config
from kapiling.auth import lock
from kapiling.auth.lock import hash_pin, verify_pin


def test_hash_and_verify():
    h = hash_pin("1234")
    assert h.startswith("scrypt$") and h.count("$") == 2
    assert verify_pin("1234", h) and not verify_pin("1235", h)
    assert hash_pin("1234") != h
    assert not verify_pin("1234", "garbage")


def test_wrong_pin_is_refused_and_logged(client, con, lola):
    r = client.post("/api/unlock", json={"profile_id": lola, "pin": "000000"})
    assert r.status_code == 401
    assert con.execute("select action from access_log order by id desc").fetchone()[0] == "unlock_failed"


def test_representative_unlock_is_attributed(client, con, lola):
    assert client.post("/api/unlock", json={"profile_id": lola, "pin": "246810"}).status_code == 204
    client.get(f"/api/profiles/{lola}/cards")
    actors = {r[0] for r in con.execute("select actor from access_log where action='view_cards'")}
    # Brief said {"Ana"}; the seeded representative's name is "Ana Dela Cruz", logged in full.
    assert actors == {"Ana Dela Cruz"}


def test_locked_routes_refuse_without_session(client, lola):
    assert client.get(f"/api/profiles/{lola}/summary").status_code == 401


def test_emergency_is_public(client, lola):
    r = client.get(f"/api/emergency/{lola}")
    assert r.status_code == 200 and r.json()["blood_type"] == "O+"


def test_session_cannot_read_another_profile(client, lola, mika):
    client.post("/api/unlock", json={"profile_id": mika, "pin": "123456"})
    assert client.get(f"/api/profiles/{lola}/summary").status_code == 403


def test_five_failures_back_off(client, lola):
    for _ in range(5):
        client.post("/api/unlock", json={"profile_id": lola, "pin": "000000"})
    assert client.post("/api/unlock", json={"profile_id": lola, "pin": "123456"}).status_code == 429


# --- extra tests -------------------------------------------------------------

def test_owner_unlock_logs_and_sets_cookie(client, con, lola):
    r = client.post("/api/unlock", json={"profile_id": lola, "pin": "123456"})
    assert r.status_code == 204
    sc = r.headers["set-cookie"].lower()
    assert "kapiling_s=" in sc and "httponly" in sc and "samesite=strict" in sc and "path=/" in sc
    assert "secure" not in sc  # plain http in tests
    row = con.execute("select actor, action from access_log order by id desc").fetchone()
    assert tuple(row) == ("Lola Remy", "unlock")


def test_failed_unlock_actor_is_unknown_and_no_pin_logged(client, con, lola):
    client.post("/api/unlock", json={"profile_id": lola, "pin": "999999"})
    row = con.execute("select actor, target from access_log order by id desc").fetchone()
    assert row["actor"] == "unknown" and "999999" not in (row["target"] or "")


def test_unlock_unknown_profile_is_401(client):
    assert client.post("/api/unlock", json={"profile_id": 9999, "pin": "123456"}).status_code == 401


def test_backoff_is_per_profile_and_expires(client, lola, mika, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(lock, "_now", lambda: now[0])
    for _ in range(5):
        assert client.post("/api/unlock", json={"profile_id": lola, "pin": "000000"}).status_code == 401
    assert client.post("/api/unlock", json={"profile_id": lola, "pin": "123456"}).status_code == 429
    assert client.post("/api/unlock", json={"profile_id": mika, "pin": "123456"}).status_code == 204
    now[0] += 61
    assert client.post("/api/unlock", json={"profile_id": lola, "pin": "123456"}).status_code == 204


def test_backoff_does_not_verify_pin(client, lola, monkeypatch):
    for _ in range(5):
        client.post("/api/unlock", json={"profile_id": lola, "pin": "000000"})
    called = []
    monkeypatch.setattr(lock, "verify_pin", lambda *a: called.append(1) or True)
    assert client.post("/api/unlock", json={"profile_id": lola, "pin": "123456"}).status_code == 429
    assert called == []


def test_failures_outside_window_do_not_count(client, lola, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(lock, "_now", lambda: now[0])
    for _ in range(4):
        client.post("/api/unlock", json={"profile_id": lola, "pin": "000000"})
    now[0] += 301
    client.post("/api/unlock", json={"profile_id": lola, "pin": "000000"})
    assert client.post("/api/unlock", json={"profile_id": lola, "pin": "123456"}).status_code == 204


def test_session_expires_when_idle_and_refreshes(client, lola, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(lock, "_now", lambda: now[0])
    monkeypatch.setattr(lock, "IDLE_TIMEOUT", 300)
    client.post("/api/unlock", json={"profile_id": lola, "pin": "123456"})
    now[0] += 250
    assert client.get(f"/api/profiles/{lola}/summary").status_code == 200
    now[0] += 250  # 500 s since unlock, 250 s since last use: still alive
    assert client.get(f"/api/profiles/{lola}/summary").status_code == 200
    now[0] += 301
    assert client.get(f"/api/profiles/{lola}/summary").status_code == 401


def test_lock_ends_session(client, lola_unlocked):
    assert client.get(f"/api/profiles/{lola_unlocked}/summary").status_code == 200
    token = client.cookies.get("kapiling_s")
    r = client.post("/api/lock")
    assert r.status_code == 204
    assert client.get(f"/api/profiles/{lola_unlocked}/summary").status_code == 401
    client.cookies.set("kapiling_s", token)  # replaying the old token does not work
    assert client.get(f"/api/profiles/{lola_unlocked}/summary").status_code == 401


def test_bogus_cookie_is_401(client, lola):
    client.cookies.set("kapiling_s", "nope")
    assert client.get(f"/api/profiles/{lola}/summary").status_code == 401


def test_mika_cannot_fetch_lolas_card_file(client, con, lola, mika_unlocked):
    cid = con.execute("select id from cards where profile_id=? order by sort", (lola,)).fetchone()[0]
    assert client.get(f"/api/files/{cid}/front").status_code == 403
    assert con.execute("select count(*) from access_log where action='view_cards'").fetchone()[0] == 0


def test_every_pid_route_enforces_ownership(client, lola, mika_unlocked):
    p = f"/api/profiles/{lola}"
    assert client.get(p).status_code == 403
    assert client.put(p, json={"phone": "x"}).status_code == 403
    assert client.get(f"{p}/cards").status_code == 403
    assert client.get(f"{p}/meds").status_code == 403
    assert client.get(f"{p}/timeline").status_code == 403
    assert client.get(f"{p}/observations").status_code == 403
    assert client.post(f"{p}/meds/1/taken", json={"date": "2026-10-10", "slot": "08:00"}).status_code == 403
    assert client.post(f"{p}/cards", data={"kind": "pwd", "label": "x"},
                       files={"front": ("f.jpg", b"x", "image/jpeg")}).status_code == 403
    assert client.get(f"/api/access-log?profile_id={lola}").status_code == 403


def test_summary_and_cards_are_logged(client, con, lola_unlocked):
    client.get(f"/api/profiles/{lola_unlocked}/summary")
    client.get(f"/api/profiles/{lola_unlocked}/cards")
    acts = [r[0] for r in con.execute("select action from access_log order by id")]
    assert acts == ["unlock", "view_summary", "view_cards"]


def test_access_log_owner_only(client, con, lola):
    client.post("/api/unlock", json={"profile_id": lola, "pin": "000000"})
    client.post("/api/unlock", json={"profile_id": lola, "pin": "246810"})
    assert client.get(f"/api/access-log?profile_id={lola}").status_code == 403  # representative
    client.post("/api/lock")
    client.post("/api/unlock", json={"profile_id": lola, "pin": "123456"})
    r = client.get(f"/api/access-log?profile_id={lola}")
    assert r.status_code == 200
    rows = r.json()
    assert set(rows[0]) == {"actor", "action", "target", "at"}
    assert [(x["actor"], x["action"]) for x in rows][:4] == [  # Task 15: the refused read is logged too
        ("Lola Remy", "unlock"), ("Ana Dela Cruz", "denied"), ("Ana Dela Cruz", "unlock"), ("unknown", "unlock_failed")]


def test_access_log_requires_session(client, lola):
    assert client.get(f"/api/access-log?profile_id={lola}").status_code == 401


def test_profiles_list_is_public(client, lola, mika):
    r = client.get("/api/profiles")
    assert r.status_code == 200
    rows = {p["id"]: p for p in r.json()}
    assert set(rows) == {lola, mika}
    assert set(rows[lola]) == {"id", "nickname", "full_name", "photo_url", "has_biometric"}
    assert rows[lola]["nickname"] == "Lola Remy"


def test_emergency_qr_svg_is_public(client, lola):
    r = client.get(f"/api/emergency/{lola}/qr.svg")
    assert r.status_code == 200 and r.headers["content-type"].startswith("image/svg+xml")
    assert r.text.lstrip().startswith("<?xml") or "<svg" in r.text[:200]
    assert client.get("/api/emergency/9999").status_code == 404
    assert client.get("/api/emergency/9999/qr.svg").status_code == 404


@pytest.fixture
def remote(con, monkeypatch):
    from kapiling.db import get_con
    from kapiling.main import app

    monkeypatch.setattr(config, "settings", dataclasses.replace(config.settings, pair_key="secret-pair"))
    app.dependency_overrides[get_con] = lambda: con
    with TestClient(app, client=("192.168.1.50", 50000)) as c:
        yield c
    app.dependency_overrides.clear()


def test_pairing_blocks_remote_locked_routes(remote, lola):
    r = remote.get(f"/api/profiles/{lola}/summary")
    assert r.status_code == 403 and "pairing" in r.json()["detail"].lower()
    assert remote.get(f"/api/profiles/{lola}").status_code == 403
    assert remote.get(f"/api/profiles/{lola}/cards").status_code == 403
    assert remote.get("/api/access-log").status_code == 403
    assert remote.post("/api/lock").status_code == 403
    assert remote.get(f"/api/profiles/{lola}/photo/x").status_code == 403
    assert remote.get(f"/api/emergency/{lola}/other").status_code == 403


def test_pairing_opens_only_public_routes(remote, lola):
    assert remote.get(f"/api/emergency/{lola}").status_code == 200
    assert remote.get(f"/api/emergency/{lola}/qr.svg").status_code == 200
    assert remote.get("/api/profiles").status_code == 200
    assert remote.get(f"/api/profiles/{lola}/photo").status_code == 200
    assert remote.post("/api/unlock", json={"profile_id": lola, "pin": "000000"}).status_code == 401


def test_is_open_matching():
    from kapiling.main import is_open
    for p in ["/api/health", "/api/profiles", "/api/profiles/1/photo", "/api/emergency/1",
              "/api/emergency/12/qr.svg", "/api/unlock"]:
        assert is_open(p), p
    for p in ["/api/profiles/", "/api/profiles/1", "/api/profiles/1/summary", "/api/profiles/x/photo",
              "/api/emergency/1/qr.svgx", "/api/emergency/", "/api/unlockx", "/api/lock", "/api/files/1/front",
              "/api/access-log", "/api/healthz"]:
        assert not is_open(p), p


PUBLIC_ROUTES = {("GET", "/api/health"), ("GET", "/api/profiles"), ("POST", "/api/unlock"), ("POST", "/api/lock"),
                 ("GET", "/api/profiles/{pid}/photo"), ("GET", "/api/emergency/{pid}"),
                 ("GET", "/api/emergency/{pid}/qr.svg"),
                 # Task 15: biometric unlock starts from the lock screen, like POST /unlock.
                 ("POST", "/api/webauthn/login/options"), ("POST", "/api/webauthn/login/verify"),
                 # Task 21: cloud demo status and reset (reset is a 404 unless KAPILING_DEMO=1).
                 ("GET", "/api/demo"), ("POST", "/api/demo/reset")}
# Locked routes whose path has no {pid}: the handler must compare the actor's profile itself (tested above).
HANDLER_CHECKED = {("GET", "/api/files/{card_id}/{side}"), ("GET", "/api/access-log"),
                   ("GET", "/api/documents/{doc_id}"), ("GET", "/api/documents/{doc_id}/file"),
                   ("GET", "/api/documents/{doc_id}/page/{n}.png"),
                   ("POST", "/api/documents/{doc_id}/observations/confirm"),
                   # Task 15: these act only on the session's own profile and are owner-only (test_webauthn.py).
                   ("POST", "/api/webauthn/register/options"), ("POST", "/api/webauthn/register/verify"),
                   ("DELETE", "/api/webauthn/credentials")}
# Task 8: conversations are keyed by id, runs take profile_id as a form field (tested in test_agui/test_conversations).
HANDLER_CHECKED |= {("GET", "/api/conversations/{cid}"), ("PATCH", "/api/conversations/{cid}"),
                    ("DELETE", "/api/conversations/{cid}"), ("POST", "/api/runs"), ("POST", "/api/runs/{run_id}/cancel")}
HANDLER_CHECKED |= {("DELETE", "/api/documents/{doc_id}/observations/{oid}"), ("POST", "/api/speak")}  # Task 12: _doc_or_404 owner check; speak reads no profile data


def test_every_route_is_public_or_locked():
    from fastapi.routing import APIRoute

    from kapiling.auth.deps import require_unlocked
    from kapiling.main import app

    def deps(d):
        for sub in d.dependencies:
            yield sub.call
            yield from deps(sub)

    def walk(routes):
        # FastAPI >= 0.143 wraps included routers; APIRouter(prefix=...) is already baked into route.path.
        for r in routes:
            if hasattr(r, "original_router"):
                yield from walk(r.original_router.routes)
            elif isinstance(r, APIRoute):
                yield r

    seen = set()
    for r in walk(app.routes):
        for m in r.methods - {"HEAD"}:
            key = (m, r.path)
            seen.add(key)
            if key in PUBLIC_ROUTES:
                continue
            assert require_unlocked in set(deps(r.dependant)), f"{key} is neither public nor locked"
            assert "{pid}" in r.path or key in HANDLER_CHECKED, f"{key} has no ownership check"
    assert PUBLIC_ROUTES <= seen
