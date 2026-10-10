"""Task 15 security review: credential changes revoke sessions, and current-PIN checks are throttled."""
import json

from kapiling.auth import lock
from seed import persona

LOCAL = {"host": "localhost:5173"}
COOKIE = "kapiling_s"


def token_for(client, pid, pin):
    """A fresh session as if from another browser (the cookie jar is cleared first)."""
    client.cookies.clear()
    assert client.post("/api/unlock", json={"profile_id": pid, "pin": pin}).status_code == 204
    return client.cookies.get(COOKIE)


def use(client, token):
    client.cookies.clear()
    client.cookies.set(COOKIE, token)


def alive(client, token, pid):
    use(client, token)
    return client.get(f"/api/profiles/{pid}/summary").status_code == 200


def actions(con, pid):
    return [r[0] for r in con.execute("select action from access_log where profile_id=? order by id", (pid,))]


# --- 1. revocation --------------------------------------------------------------------------------

def test_actor_carries_the_representative_id(con, lola):
    rid = con.execute("select id from representatives where profile_id=?", (lola,)).fetchone()[0]
    assert lock.check_pin(con, lola, persona.REP_PIN)["rep_id"] == rid
    assert lock.check_pin(con, lola, persona.OWNER_PIN)["rep_id"] is None


def test_end_sessions_only_touches_matching_sessions_of_that_profile(client, lola, mika):
    a = token_for(client, lola, persona.OWNER_PIN)
    b = token_for(client, lola, persona.REP_PIN)
    m = token_for(client, mika, persona.OWNER_PIN)
    assert lock.end_sessions(lola, lambda _t, actor: actor["role"] == "representative") == 1
    assert alive(client, a, lola) and not alive(client, b, lola) and alive(client, m, mika)


def test_removing_a_representative_ends_their_sessions(client, con, lola):
    rep = token_for(client, lola, persona.REP_PIN)
    assert alive(client, rep, lola)
    owner = token_for(client, lola, persona.OWNER_PIN)
    rid = con.execute("select id from representatives where profile_id=?", (lola,)).fetchone()[0]
    assert client.delete(f"/api/profiles/{lola}/representatives/{rid}").status_code == 204
    assert not alive(client, rep, lola)  # 401 on the next request, no idle-timeout grace
    use(client, rep)
    assert client.get(f"/api/profiles/{lola}/summary").status_code == 401
    assert alive(client, owner, lola)


def test_removing_one_representative_keeps_another(client, con, lola):
    owner = token_for(client, lola, persona.OWNER_PIN)
    client.post(f"/api/profiles/{lola}/representatives", json={"name": "Jun", "pin": "135790"})
    jun = token_for(client, lola, "135790")
    ana = token_for(client, lola, persona.REP_PIN)
    use(client, owner)
    rid = con.execute("select id from representatives where name='Ana Dela Cruz'").fetchone()[0]
    assert client.delete(f"/api/profiles/{lola}/representatives/{rid}").status_code == 204
    assert not alive(client, ana, lola) and alive(client, jun, lola) and alive(client, owner, lola)


def test_changing_the_owner_pin_ends_every_other_session(client, lola, mika):
    other_owner = token_for(client, lola, persona.OWNER_PIN)
    rep = token_for(client, lola, persona.REP_PIN)
    m = token_for(client, mika, persona.OWNER_PIN)
    me = token_for(client, lola, persona.OWNER_PIN)
    r = client.put(f"/api/profiles/{lola}/pin", json={"current_pin": persona.OWNER_PIN, "new_pin": "654321"})
    assert r.status_code == 204
    assert not alive(client, other_owner, lola) and not alive(client, rep, lola)
    assert alive(client, me, lola)  # the caller keeps working
    assert alive(client, m, mika)   # other profiles are untouched


def test_removing_biometrics_ends_every_other_session(client, con, lola):
    con.execute("update owner_lock set webauthn=? where profile_id=?",
                (json.dumps([{"id": "Y3JlZC0x", "public_key": "cGs", "sign_count": 0}]), lola))
    con.commit()
    other = token_for(client, lola, persona.OWNER_PIN)
    me = token_for(client, lola, persona.OWNER_PIN)
    assert client.delete("/api/webauthn/credentials", headers=LOCAL).status_code == 204
    assert not alive(client, other, lola)
    assert alive(client, me, lola)


# --- 2. throttled current-PIN checks ------------------------------------------------------------------

def test_change_pin_current_pin_is_throttled(client, con, lola_unlocked):
    pid = lola_unlocked
    for _ in range(5):
        r = client.put(f"/api/profiles/{pid}/pin", json={"current_pin": "000000", "new_pin": "654321"})
        assert r.status_code == 403
    r = client.put(f"/api/profiles/{pid}/pin", json={"current_pin": persona.OWNER_PIN, "new_pin": "654321"})
    assert r.status_code == 429 and r.json()["detail"] == "errors.tooManyAttempts"
    h = con.execute("select pin_hash from owner_lock where profile_id=?", (pid,)).fetchone()[0]
    assert lock.verify_pin(persona.OWNER_PIN, h)  # unchanged


def test_change_pin_throttle_shares_the_unlock_window(client, lola):
    for _ in range(4):
        client.post("/api/unlock", json={"profile_id": lola, "pin": "000000"})
    token_for(client, lola, persona.OWNER_PIN)  # success does not clear earlier failures
    client.put(f"/api/profiles/{lola}/pin", json={"current_pin": "000000", "new_pin": "654321"})
    r = client.put(f"/api/profiles/{lola}/pin", json={"current_pin": persona.OWNER_PIN, "new_pin": "654321"})
    assert r.status_code == 429


# --- 3. biometric enrolment needs the owner PIN; PIN clashes logged; language validated ----------------

def test_enrolment_options_need_the_current_pin(client, con, lola_unlocked):
    assert client.post("/api/webauthn/register/options", headers=LOCAL).status_code == 422
    r = client.post("/api/webauthn/register/options", json={"pin": "000000"}, headers=LOCAL)
    assert r.status_code == 403 and r.json()["detail"] == "settings.wrongCurrentPin"
    assert actions(con, lola_unlocked)[-1] == "enrol_biometric_failed"
    r = client.post("/api/webauthn/register/options", json={"pin": persona.OWNER_PIN}, headers=LOCAL)
    assert r.status_code == 200 and r.json()["rp"]["id"] == "localhost"


def test_enrolment_pin_is_throttled(client, lola_unlocked):
    for _ in range(5):
        client.post("/api/webauthn/register/options", json={"pin": "000000"}, headers=LOCAL)
    r = client.post("/api/webauthn/register/options", json={"pin": persona.OWNER_PIN}, headers=LOCAL)
    assert r.status_code == 429 and r.json()["detail"] == "errors.tooManyAttempts"


def test_ip_host_is_refused_before_a_pin_attempt_is_spent(client, lola_unlocked, monkeypatch):
    called = []
    monkeypatch.setattr(lock, "check_owner_pin", lambda *a: called.append(1) or True)
    r = client.post("/api/webauthn/register/options", json={"pin": persona.OWNER_PIN}, headers={"host": "192.168.1.5"})
    assert r.status_code == 400 and called == []


def test_pin_clash_is_logged_without_the_pin(client, con, lola_unlocked):
    client.post(f"/api/profiles/{lola_unlocked}/representatives", json={"name": "X", "pin": persona.OWNER_PIN})
    client.put(f"/api/profiles/{lola_unlocked}/pin", json={"current_pin": persona.OWNER_PIN, "new_pin": persona.REP_PIN})
    rows = con.execute("select action, target from access_log where action='pin_clash' order by id").fetchall()
    assert [tuple(r) for r in rows] == [("pin_clash", "add_representative"), ("pin_clash", "change_pin")]
    dump = json.dumps([dict(r) for r in con.execute("select * from access_log")])
    assert persona.OWNER_PIN not in dump and persona.REP_PIN not in dump


def test_language_is_validated(client, con, lola_unlocked):
    r = client.put(f"/api/profiles/{lola_unlocked}", json={"language": "fr"})
    assert r.status_code == 422 and r.json()["detail"] == "settings.invalidLanguage"
    assert con.execute("select language from profiles where id=?", (lola_unlocked,)).fetchone()[0] == "tl"
    assert client.put(f"/api/profiles/{lola_unlocked}", json={"language": "en"}).status_code == 200
