"""Task 15: WebAuthn (platform authenticator, user verification) for biometric unlock.

The py_webauthn verify calls are mocked at ONE seam, `kapiling.auth.webauthn._verify`; everything else
(rp_id, challenge store, sign counter, session, logging) runs for real.
"""
import base64
import json
from types import SimpleNamespace

import pytest

from kapiling.auth import lock
from kapiling.auth import webauthn as wa_mod
from seed import persona

LOCAL = {"host": "localhost:5173"}


def b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def fake_credential(challenge: str, kind: str = "get", cred_id: str = "Y3JlZC0x", attachment: str = "platform") -> dict:
    client_data = b64(json.dumps({"type": f"webauthn.{kind}", "challenge": challenge,
                                  "origin": "http://localhost:5173"}).encode())
    response = {"clientDataJSON": client_data}
    response |= ({"attestationObject": b64(b"att")} if kind == "create" else
                 {"authenticatorData": b64(b"auth"), "signature": b64(b"sig"), "userHandle": None})
    return {"id": cred_id, "rawId": cred_id, "type": "public-key", "response": response,
            "authenticatorAttachment": attachment, "clientExtensionResults": {}}


@pytest.fixture
def mock_verify(monkeypatch):
    calls = []
    result = {"sign_count": 1}

    def fake(kind, **kw):
        calls.append((kind, kw))
        if kind == "registration":
            return SimpleNamespace(credential_id=b"cred-1", credential_public_key=b"pk", sign_count=0)
        return SimpleNamespace(credential_id=b"cred-1", new_sign_count=result["sign_count"])

    monkeypatch.setattr(wa_mod, "_verify", fake)
    return SimpleNamespace(calls=calls, result=result)


@pytest.fixture
def enrolled(con, lola):
    con.execute("update owner_lock set webauthn=? where profile_id=?",
                (json.dumps([{"id": "Y3JlZC0x", "public_key": b64(b"pk"), "sign_count": 3}]), lola))
    con.commit()
    return lola


def login_options(client, pid, headers=LOCAL):
    return client.post("/api/webauthn/login/options", json={"profile_id": pid}, headers=headers)


# --- rp_id and host rules ----------------------------------------------------------------

@pytest.mark.parametrize("host", ["192.168.1.5", "192.168.1.5:8915", "[::1]:8915", "10.0.0.2"])
def test_ip_host_is_refused(client, lola_unlocked, enrolled, host):
    for r in (client.post("/api/webauthn/register/options", headers={"host": host}),
              login_options(client, lola_unlocked, {"host": host})):
        assert r.status_code == 400 and r.json()["detail"] == "lock.biometricNeedsDomain"


def test_localhost_options_require_platform_and_user_verification(client, lola_unlocked):
    r = client.post("/api/webauthn/register/options", headers=LOCAL)
    assert r.status_code == 200
    opts = r.json()
    assert opts["rp"]["id"] == "localhost"  # port stripped
    sel = opts["authenticatorSelection"]
    assert sel["authenticatorAttachment"] == "platform" and sel["userVerification"] == "required"
    assert opts["timeout"] <= 120_000


def test_domain_host_sets_rp_id(client, lola_unlocked):
    r = client.post("/api/webauthn/register/options", headers={"host": "kapiling.example.ph"})
    assert r.json()["rp"]["id"] == "kapiling.example.ph"


def test_login_options_need_an_enrolled_credential(client, lola, mika, enrolled):
    r = login_options(client, mika)
    assert r.status_code == 404 and r.json()["detail"] == "settings.biometricNotSet"
    r = login_options(client, lola)
    assert r.status_code == 200
    opts = r.json()
    assert opts["rpId"] == "localhost" and opts["userVerification"] == "required"
    assert [c["id"] for c in opts["allowCredentials"]] == ["Y3JlZC0x"]


# --- owner only -------------------------------------------------------------------------------

def test_enrolment_is_owner_only(client, con, lola):
    assert client.post("/api/webauthn/register/options", headers=LOCAL).status_code == 401
    client.post("/api/unlock", json={"profile_id": lola, "pin": persona.REP_PIN})
    for r in (client.post("/api/webauthn/register/options", headers=LOCAL),
              client.post("/api/webauthn/register/verify", json={"credential": {}}, headers=LOCAL),
              client.delete("/api/webauthn/credentials", headers=LOCAL)):
        assert r.status_code == 403 and r.json()["detail"] == "settings.ownerOnly"


# --- registration -------------------------------------------------------------------------------

def test_register_stores_credential_and_is_logged(client, con, lola_unlocked, mock_verify):
    chal = client.post("/api/webauthn/register/options", headers=LOCAL).json()["challenge"]
    r = client.post("/api/webauthn/register/verify", json={"credential": fake_credential(chal, "create")}, headers=LOCAL)
    assert r.status_code == 204, r.text
    kind, kw = mock_verify.calls[0]
    assert kind == "registration" and kw["require_user_verification"] is True
    assert kw["expected_rp_id"] == "localhost" and kw["expected_origin"] == "http://localhost:5173"
    assert kw["expected_challenge"] == base64.urlsafe_b64decode(chal + "==")
    creds = json.loads(con.execute("select webauthn from owner_lock where profile_id=?", (lola_unlocked,)).fetchone()[0])
    assert creds[0]["id"] == b64(b"cred-1") and creds[0]["sign_count"] == 0
    assert con.execute("select action from access_log order by id desc").fetchone()[0] == "enrol_biometric"
    assert {p["id"]: p for p in client.get("/api/profiles").json()}[lola_unlocked]["has_biometric"] is True


def test_register_refuses_a_roaming_authenticator(client, lola_unlocked, mock_verify):
    chal = client.post("/api/webauthn/register/options", headers=LOCAL).json()["challenge"]
    cred = fake_credential(chal, "create", attachment="cross-platform")
    assert client.post("/api/webauthn/register/verify", json={"credential": cred}, headers=LOCAL).status_code == 400


def test_remove_biometrics(client, con, enrolled, lola_unlocked):
    assert client.delete("/api/webauthn/credentials", headers=LOCAL).status_code == 204
    assert json.loads(con.execute("select webauthn from owner_lock where profile_id=?", (enrolled,)).fetchone()[0]) == []
    assert con.execute("select action from access_log order by id desc").fetchone()[0] == "remove_biometric"


# --- login ------------------------------------------------------------------------------------

def test_login_verify_creates_a_session_like_pin_unlock(client, con, enrolled, mock_verify, monkeypatch):
    made = []
    mock_verify.result["sign_count"] = 4
    real = lock.new_session
    monkeypatch.setattr(lock, "new_session", lambda actor: made.append(actor) or real(actor))
    chal = login_options(client, enrolled).json()["challenge"]
    r = client.post("/api/webauthn/login/verify", json={"profile_id": enrolled, "credential": fake_credential(chal)},
                    headers=LOCAL)
    assert r.status_code == 204, r.text
    assert made == [{"profile_id": enrolled, "name": "Lola Remy", "role": "owner"}]
    sc = r.headers["set-cookie"].lower()
    assert "kapiling_s=" in sc and "httponly" in sc and "samesite=strict" in sc
    assert client.get(f"/api/profiles/{enrolled}/summary").status_code == 200
    kind, kw = mock_verify.calls[0]
    assert kind == "authentication" and kw["require_user_verification"] is True
    assert kw["credential_current_sign_count"] == 3 and kw["credential_public_key"] == b"pk"
    stored = json.loads(con.execute("select webauthn from owner_lock where profile_id=?", (enrolled,)).fetchone()[0])
    assert stored[0]["sign_count"] == 4
    row = con.execute("select actor, action, target from access_log where action='unlock' order by id desc").fetchone()
    assert tuple(row) == ("Lola Remy", "unlock", "biometric")


def test_challenge_is_single_use(client, enrolled, mock_verify):
    mock_verify.result["sign_count"] = 4
    chal = login_options(client, enrolled).json()["challenge"]
    body = {"profile_id": enrolled, "credential": fake_credential(chal)}
    assert client.post("/api/webauthn/login/verify", json=body, headers=LOCAL).status_code == 204
    client.post("/api/lock")
    mock_verify.result["sign_count"] = 5
    r = client.post("/api/webauthn/login/verify", json=body, headers=LOCAL)
    assert r.status_code == 400 and r.json()["detail"] == "settings.biometricFailed"
    assert client.get(f"/api/profiles/{enrolled}/summary").status_code == 401


def test_challenge_expires_after_two_minutes(client, enrolled, mock_verify, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(wa_mod, "_now", lambda: now[0])
    chal = login_options(client, enrolled).json()["challenge"]
    now[0] += 121
    body = {"profile_id": enrolled, "credential": fake_credential(chal)}
    assert client.post("/api/webauthn/login/verify", json=body, headers=LOCAL).status_code == 400
    assert mock_verify.calls == []


def test_challenge_is_bound_to_its_profile_and_purpose(client, con, enrolled, mika, mock_verify, lola_unlocked):
    reg = client.post("/api/webauthn/register/options", headers=LOCAL).json()["challenge"]
    client.post("/api/lock")
    # a registration challenge cannot log in
    body = {"profile_id": enrolled, "credential": fake_credential(reg)}
    assert client.post("/api/webauthn/login/verify", json=body, headers=LOCAL).status_code == 400
    # a challenge issued for Lola cannot unlock Mika
    chal = login_options(client, enrolled).json()["challenge"]
    body = {"profile_id": mika, "credential": fake_credential(chal)}
    assert client.post("/api/webauthn/login/verify", json=body, headers=LOCAL).status_code == 400
    assert mock_verify.calls == []


def test_sign_counter_must_increase(client, con, enrolled, mock_verify):
    mock_verify.result["sign_count"] = 2  # stored is 3: a cloned authenticator
    chal = login_options(client, enrolled).json()["challenge"]
    r = client.post("/api/webauthn/login/verify", json={"profile_id": enrolled, "credential": fake_credential(chal)},
                    headers=LOCAL)
    assert r.status_code == 400 and r.json()["detail"] == "settings.biometricFailed"
    assert "kapiling_s" not in client.cookies
    assert con.execute("select action from access_log order by id desc").fetchone()[0] == "unlock_failed"


def test_library_rejection_is_a_400_without_session(client, enrolled, monkeypatch):
    def boom(kind, **kw):
        raise wa_mod.InvalidAuthenticationResponse("bad signature")

    monkeypatch.setattr(wa_mod, "_verify", boom)
    chal = login_options(client, enrolled).json()["challenge"]
    r = client.post("/api/webauthn/login/verify", json={"profile_id": enrolled, "credential": fake_credential(chal)},
                    headers=LOCAL)
    assert r.status_code == 400 and "kapiling_s" not in client.cookies


def test_unknown_credential_is_refused(client, enrolled, mock_verify):
    chal = login_options(client, enrolled).json()["challenge"]
    body = {"profile_id": enrolled, "credential": fake_credential(chal, cred_id="b3RoZXI")}
    assert client.post("/api/webauthn/login/verify", json=body, headers=LOCAL).status_code == 400
    assert mock_verify.calls == []

