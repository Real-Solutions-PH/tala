"""SPA fallback: deep links and reloads serve index.html; unknown /api paths stay 404 JSON."""

import pytest
from fastapi.testclient import TestClient
from starlette.routing import Mount

from kapiling import config, main

INDEX = "<!doctype html><title>Kapiling</title><div id=app></div>"
JS = "console.log('kapiling')"


@pytest.fixture
def static_app(tmp_path):
    (tmp_path / "index.html").write_text(INDEX)
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "x.js").write_text(JS)
    routes = main.app.router.routes
    saved = list(routes)
    routes[:] = [r for r in routes if not (isinstance(r, Mount) and r.name == "static")]
    routes.append(Mount("/", app=main.spa(tmp_path), name="static"))
    yield main.app
    routes[:] = saved


def test_deep_link_serves_index_html(static_app):
    with TestClient(static_app, client=("127.0.0.1", 50000)) as c:
        for path in ("/chat", "/records/labs/fbs", "/"):
            r = c.get(path)
            assert r.status_code == 200 and r.text == INDEX, path
            assert r.headers["content-type"].startswith("text/html")


def test_unknown_api_path_is_404_json(static_app):
    with TestClient(static_app, client=("127.0.0.1", 50000)) as c:
        for path in ("/api/nope", "/api/records/zzz/nothing", "/api"):
            r = c.get(path)
            assert r.status_code == 404, path
            assert r.headers["content-type"] == "application/json" and r.json() == {"detail": "Not Found"}


def test_existing_static_file_is_served(static_app):
    with TestClient(static_app, client=("127.0.0.1", 50000)) as c:
        r = c.get("/assets/x.js")
        assert r.status_code == 200 and r.text == JS


def test_non_get_is_not_answered_with_index(static_app):
    with TestClient(static_app, client=("127.0.0.1", 50000)) as c:
        assert c.post("/chat").status_code == 405


def test_unpaired_lan_client_is_still_blocked(static_app, monkeypatch):
    import dataclasses

    monkeypatch.setattr(config, "settings", dataclasses.replace(config.settings, pair_key="k123"))
    with TestClient(static_app, base_url="https://testserver", client=("192.168.1.20", 50000)) as c:
        for path in ("/chat", "/", "/assets/x.js"):
            r = c.get(path)
            assert r.status_code == 403 and INDEX not in r.text, path
        assert c.get("/chat?k=k123").text == INDEX       # the pairing link still works
        assert c.get("/records/labs/fbs").text == INDEX  # and then the cookie does
