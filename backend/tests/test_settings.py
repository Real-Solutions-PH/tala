"""Task 15: settings, representatives, PIN change, emergency fields, profile extras."""
import json

import pytest

from kapiling.auth.lock import verify_pin
from seed import persona


def _unlock(client, pid, pin):
    assert client.post("/api/unlock", json={"profile_id": pid, "pin": pin}).status_code == 204


@pytest.fixture
def ana_unlocked(client, lola):
    _unlock(client, lola, persona.REP_PIN)
    return lola


def _actions(con, pid):
    return [r[0] for r in con.execute("select action from access_log where profile_id=? order by id", (pid,))]


# --- settings overview ------------------------------------------------------------

def test_settings_overview_for_owner(client, lola_unlocked):
    r = client.get(f"/api/profiles/{lola_unlocked}/settings")
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "owner" and body["actor"] == "Lola Remy"
    assert [x["name"] for x in body["representatives"]] == ["Ana Dela Cruz"]
    assert set(body["representatives"][0]) == {"id", "name", "relation"}  # never a hash
    assert "photo" in body["emergency_fields"] and body["has_biometric"] is False


def test_settings_overview_for_representative_hides_representatives(client, ana_unlocked):
    body = client.get(f"/api/profiles/{ana_unlocked}/settings").json()
    assert body["role"] == "representative" and body["representatives"] == []


def test_settings_overview_is_locked_and_owned(client, lola, mika_unlocked):
    assert client.get(f"/api/profiles/{lola}/settings").status_code == 403
    client.post("/api/lock")
    assert client.get(f"/api/profiles/{lola}/settings").status_code == 401


# --- representatives ----------------------------------------------------------------

def test_owner_adds_a_representative_who_can_unlock(client, con, lola_unlocked):
    r = client.post(f"/api/profiles/{lola_unlocked}/representatives",
                    json={"name": "Jun Dela Cruz", "relation": "Son", "pin": "135790"})
    assert r.status_code == 201
    assert set(r.json()) == {"id", "name", "relation"}
    row = con.execute("select pin_hash from representatives where name='Jun Dela Cruz'").fetchone()
    assert verify_pin("135790", row[0]) and "135790" not in row[0]
    assert _actions(con, lola_unlocked)[-1] == "add_representative"
    assert "135790" not in json.dumps([dict(x) for x in con.execute("select * from access_log")])
    client.post("/api/lock")
    _unlock(client, lola_unlocked, "135790")


@pytest.mark.parametrize("pin", [persona.OWNER_PIN, persona.REP_PIN])
def test_representative_pin_must_be_unique(client, con, lola_unlocked, pin):
    r = client.post(f"/api/profiles/{lola_unlocked}/representatives", json={"name": "X", "relation": "", "pin": pin})
    assert r.status_code == 409 and r.json()["detail"] == "settings.pinInUse"
    assert con.execute("select count(*) from representatives where profile_id=?", (lola_unlocked,)).fetchone()[0] == 1


@pytest.mark.parametrize("pin", ["12345", "1234567", "abcdef", "12 456"])
def test_representative_pin_must_be_six_digits(client, lola_unlocked, pin):
    r = client.post(f"/api/profiles/{lola_unlocked}/representatives", json={"name": "X", "pin": pin})
    assert r.status_code == 422


def test_owner_removes_a_representative(client, con, lola_unlocked):
    rid = con.execute("select id from representatives where profile_id=?", (lola_unlocked,)).fetchone()[0]
    assert client.delete(f"/api/profiles/{lola_unlocked}/representatives/{rid}").status_code == 204
    assert con.execute("select count(*) from representatives").fetchone()[0] == 0
    assert _actions(con, lola_unlocked)[-1] == "remove_representative"
    client.post("/api/lock")
    assert client.post("/api/unlock", json={"profile_id": lola_unlocked, "pin": persona.REP_PIN}).status_code == 401


def test_removing_another_profiles_representative_is_404(client, con, lola, mika_unlocked):
    rid = con.execute("select id from representatives where profile_id=?", (lola,)).fetchone()[0]
    assert client.delete(f"/api/profiles/{mika_unlocked}/representatives/{rid}").status_code == 404
    assert con.execute("select count(*) from representatives").fetchone()[0] == 1


def test_representative_cannot_manage_representatives(client, con, ana_unlocked):
    pid = ana_unlocked
    rid = con.execute("select id from representatives where profile_id=?", (pid,)).fetchone()[0]
    r = client.post(f"/api/profiles/{pid}/representatives", json={"name": "Y", "pin": "112233"})
    assert r.status_code == 403 and r.json()["detail"] == "settings.ownerOnly"
    r = client.delete(f"/api/profiles/{pid}/representatives/{rid}")
    assert r.status_code == 403 and r.json()["detail"] == "settings.ownerOnly"
    assert con.execute("select count(*) from representatives").fetchone()[0] == 1
    assert _actions(con, pid)[-2:] == ["denied", "denied"]


# --- owner PIN ------------------------------------------------------------------------

def test_owner_changes_pin_with_current_pin(client, con, lola_unlocked):
    r = client.put(f"/api/profiles/{lola_unlocked}/pin", json={"current_pin": persona.OWNER_PIN, "new_pin": "654321"})
    assert r.status_code == 204
    assert _actions(con, lola_unlocked)[-1] == "change_pin"
    client.post("/api/lock")
    assert client.post("/api/unlock", json={"profile_id": lola_unlocked, "pin": persona.OWNER_PIN}).status_code == 401
    _unlock(client, lola_unlocked, "654321")


def test_change_pin_needs_the_current_pin(client, con, lola_unlocked):
    r = client.put(f"/api/profiles/{lola_unlocked}/pin", json={"current_pin": "000000", "new_pin": "654321"})
    assert r.status_code == 403 and r.json()["detail"] == "settings.wrongCurrentPin"
    assert _actions(con, lola_unlocked)[-1] == "change_pin_failed"
    h = con.execute("select pin_hash from owner_lock where profile_id=?", (lola_unlocked,)).fetchone()[0]
    assert verify_pin(persona.OWNER_PIN, h)


def test_owner_pin_cannot_equal_a_representative_pin(client, lola_unlocked):
    r = client.put(f"/api/profiles/{lola_unlocked}/pin", json={"current_pin": persona.OWNER_PIN, "new_pin": persona.REP_PIN})
    assert r.status_code == 409 and r.json()["detail"] == "settings.pinInUse"


def test_representative_cannot_change_the_owner_pin(client, con, ana_unlocked):
    r = client.put(f"/api/profiles/{ana_unlocked}/pin", json={"current_pin": persona.OWNER_PIN, "new_pin": "654321"})
    assert r.status_code == 403 and r.json()["detail"] == "settings.ownerOnly"
    h = con.execute("select pin_hash from owner_lock where profile_id=?", (ana_unlocked,)).fetchone()[0]
    assert verify_pin(persona.OWNER_PIN, h)


# --- access log ----------------------------------------------------------------------

def test_reading_the_access_log_is_logged(client, con, lola_unlocked):
    rows = client.get("/api/access-log").json()
    assert rows[0]["action"] == "unlock"  # the read is logged after it is answered
    assert _actions(con, lola_unlocked)[-1] == "view_access_log"


# --- emergency fields and language ------------------------------------------------------

def test_emergency_fields_toggle(client, con, lola_unlocked):
    r = client.put(f"/api/profiles/{lola_unlocked}/emergency-fields", json={"fields": ["photo", "blood_type"]})
    assert r.status_code == 200 and r.json() == {"fields": ["photo", "blood_type"]}
    card = client.get(f"/api/emergency/{lola_unlocked}").json()
    assert card["blood_type"] == "O+" and card["allergies"] == [] and card["contacts"] == []
    assert _actions(con, lola_unlocked)[-1] == "change_emergency_fields"


def test_emergency_fields_rejects_unknown(client, lola_unlocked):
    assert client.put(f"/api/profiles/{lola_unlocked}/emergency-fields", json={"fields": ["password"]}).status_code == 422


def test_language_persists(client, con, lola_unlocked):
    assert client.put(f"/api/profiles/{lola_unlocked}", json={"language": "en"}).status_code == 200
    assert con.execute("select language from profiles where id=?", (lola_unlocked,)).fetchone()[0] == "en"


# --- profile: family history and contacts ---------------------------------------------------

def test_family_history_crud(client, con, lola_unlocked):
    pid = lola_unlocked
    before = client.get(f"/api/profiles/{pid}/family-history").json()
    r = client.post(f"/api/profiles/{pid}/family-history", json={"relation": "Kapatid", "condition": "Hika"})
    assert r.status_code == 201
    fid = r.json()["id"]
    after = client.get(f"/api/profiles/{pid}/family-history").json()
    assert len(after) == len(before) + 1
    assert client.delete(f"/api/profiles/{pid}/family-history/{fid}").status_code == 204
    assert len(client.get(f"/api/profiles/{pid}/family-history").json()) == len(before)


def test_contacts_add_and_remove(client, con, lola_unlocked):
    pid = lola_unlocked
    r = client.post(f"/api/profiles/{pid}/contacts", json={"name": "Jun", "relation": "Son", "phone": "09171234567"})
    assert r.status_code == 201
    cid = r.json()["id"]
    assert any(c["id"] == cid for c in client.get(f"/api/profiles/{pid}/summary").json()["contacts"])
    assert client.delete(f"/api/profiles/{pid}/contacts/{cid}").status_code == 204


def test_family_history_and_contacts_are_owned(client, con, lola, mika_unlocked):
    fid = con.execute("select id from family_history where profile_id=?", (lola,)).fetchone()[0]
    cid = con.execute("select id from contacts where profile_id=?", (lola,)).fetchone()[0]
    assert client.get(f"/api/profiles/{lola}/family-history").status_code == 403
    assert client.delete(f"/api/profiles/{mika_unlocked}/family-history/{fid}").status_code == 404
    assert client.delete(f"/api/profiles/{mika_unlocked}/contacts/{cid}").status_code == 404


def test_profiles_list_reports_has_biometric(client, con, lola, mika):
    con.execute("update owner_lock set webauthn=? where profile_id=?",
                (json.dumps([{"id": "abc", "public_key": "def", "sign_count": 0}]), lola))
    con.commit()
    rows = {p["id"]: p for p in client.get("/api/profiles").json()}
    assert rows[lola]["has_biometric"] is True and rows[mika]["has_biometric"] is False
