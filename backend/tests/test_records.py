import io

from PIL import Image

from kapiling.records.repo import list_meds, mark_taken, meds_today
from kapiling.records.summary import emergency_card, essential_summary


def test_meds_today_lists_each_slot(con, lola):
    today = meds_today(con, lola, "2026-10-10")
    assert {(t["name"], t["slot"]) for t in today} == {("Losartan", "08:00"), ("Metformin", "08:00"), ("Metformin", "20:00"), ("Amlodipine", "20:00")}


def test_mark_taken_is_idempotent(con, lola):
    mid = list_meds(con, lola)[0]["id"]
    mark_taken(con, mid, "2026-10-10", "08:00"); mark_taken(con, mid, "2026-10-10", "08:00")
    assert sum(1 for t in meds_today(con, lola, "2026-10-10") if t["taken_at"]) == 1


def test_essential_summary_has_the_hospital_questions(con, lola):
    s = essential_summary(con, lola, "en")
    for must in ["O+", "Penicillin", "Losartan 50 mg", "Hypertension", "Ana", "FBS"]:
        assert must in s
    assert len(s) < 6000


def test_essential_summary_tagalog_headings(con, lola):
    s = essential_summary(con, lola, "tl")
    assert "Allergies" not in s and "Penicillin" in s


def test_emergency_card_respects_field_choice(con, lola):
    con.execute("update emergency_fields set fields='[\"blood_type\"]' where profile_id=?", (lola,))
    card = emergency_card(con, lola)
    assert card["blood_type"] == "O+" and card["allergies"] == [] and card["philhealth_last4"] is None
    assert card["photo_url"] is None and card["doctor"] is None


def test_emergency_card_full(con, lola):
    card = emergency_card(con, lola)
    assert card["philhealth_last4"] == "0000"
    assert card["doctor"]["name"] == "Dr. Jose Reyes"
    assert [c["name"] for c in card["contacts"]] == ["Ana Dela Cruz"]
    assert len(card["qr_text"]) < 600 and "Penicillin" in card["qr_text"]


def test_card_numbers_are_masked_in_list(client, lola_unlocked):
    cards = client.get(f"/api/profiles/{lola_unlocked}/cards").json()
    by_kind = {c["kind"]: c["number_masked"] for c in cards}
    assert by_kind["philhealth"] == "••••0000"
    assert by_kind["hmo"] == "••••0000"
    assert by_kind["vaccination"] is None


def test_mask_rules():
    from kapiling.records.routes import _mask
    assert _mask("1234") == "••••" and _mask("12") == "••••"
    assert _mask("AB-12345-C") == "••••2345" and _mask(None) is None and _mask("ABCDEFG") == "••••"


def test_card_file_served_with_content_type(client, lola_unlocked, con):
    cid = con.execute("select id from cards where profile_id=? order by sort", (lola_unlocked,)).fetchone()[0]
    r = client.get(f"/api/files/{cid}/front")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert client.get(f"/api/files/{cid}/side").status_code == 404
    assert client.get("/api/files/99999/front").status_code == 404
    con.execute("update cards set back_path=NULL where id=?", (cid,)); con.commit()
    assert client.get(f"/api/files/{cid}/back").status_code == 404


def test_profile_photo_public(client, lola):
    r = client.get(f"/api/profiles/{lola}/photo")
    assert r.status_code == 200 and r.headers["content-type"].startswith("image/")
    assert client.get("/api/profiles/9999/photo").status_code == 404


def _jpeg():
    b = io.BytesIO(); Image.new("RGB", (8, 8), "white").save(b, "JPEG"); return b.getvalue()


def test_post_card_creates_and_serves(client, lola_unlocked):
    r = client.post(f"/api/profiles/{lola_unlocked}/cards",
                    data={"kind": "pwd", "label": "PWD ID", "number": "PWD-1234567"},
                    files={"front": ("f.jpg", _jpeg(), "image/jpeg"), "back": ("b.jpg", _jpeg(), "image/jpeg")})
    assert r.status_code == 200
    card = r.json()
    assert card["number_masked"] == "••••4567" and card["back_url"]
    assert client.get(card["front_url"]).headers["content-type"] == "image/jpeg"
    assert client.post(f"/api/profiles/{lola_unlocked}/cards", data={"kind": "bogus", "label": "x"},
                       files={"front": ("f.jpg", _jpeg(), "image/jpeg")}).status_code == 422


def test_meds_summary_timeline_observations_routes(client, lola_unlocked):
    p = f"/api/profiles/{lola_unlocked}"
    m = client.get(f"{p}/meds?date=2026-10-10").json()
    assert len(m["meds"]) == 3 and len(m["today"]) == 4
    mid = m["meds"][0]["id"]
    assert client.post(f"{p}/meds/{mid}/taken", json={"date": "2026-10-10", "slot": "08:00"}).status_code == 204
    t = client.get(f"{p}/meds?date=2026-10-10").json()["today"]
    assert sum(1 for x in t if x["taken_at"]) == 1
    assert client.request("DELETE", f"{p}/meds/{mid}/taken", json={"date": "2026-10-10", "slot": "08:00"}).status_code == 204
    obs = client.get(f"{p}/observations?code=fbs").json()
    assert [o["date"] for o in obs] == sorted(o["date"] for o in obs) and len(obs) == 8
    tl = client.get(f"{p}/timeline").json()
    assert [x["date"] for x in tl] == sorted((x["date"] for x in tl), reverse=True)
    assert all(x["kind"] == "visit" for x in client.get(f"{p}/timeline?kind=visit").json())
    s = client.get(f"{p}/summary").json()
    assert s["latest"]["fbs"]["value"] == 132 and s["profile"]["id"] == lola_unlocked
    assert client.put(p, json={"phone": "0917-111-1111"}).json()["phone"] == "0917-111-1111"
    assert client.get("/api/profiles/9999/summary").status_code == 403  # not this session's profile


def _post(client, pid, front, back=None, ct="image/jpeg"):
    files = {"front": ("f.jpg", front, ct)}
    if back is not None:
        files["back"] = ("b.jpg", back, ct)
    return client.post(f"/api/profiles/{pid}/cards", data={"kind": "pwd", "label": "x"}, files=files)


def _card_files(pid):
    from kapiling import config
    d = config.settings.data_dir / "files/cards"
    return {p.name for p in d.glob(f"{pid}-*")}


def test_upload_rejects_fake_image_with_lying_content_type(client, lola_unlocked):
    lola = lola_unlocked
    before = _card_files(lola)
    r = _post(client, lola, b"not an image at all")
    assert r.status_code == 415 and r.json()["detail"] == "errors.unsupportedImage"
    assert _card_files(lola) == before


def test_upload_rejects_oversize(client, lola_unlocked):
    lola = lola_unlocked
    r = _post(client, lola, _jpeg() + b"\0" * (10 * 1024 * 1024))
    assert r.status_code == 413 and r.json()["detail"] == "errors.fileTooLarge"


def test_bad_back_leaves_no_files(client, lola_unlocked):
    lola = lola_unlocked
    before = _card_files(lola)
    r = _post(client, lola, _jpeg(), back=b"junk")
    assert r.status_code == 415 and _card_files(lola) == before


def test_extension_comes_from_real_format(client, lola_unlocked):
    lola = lola_unlocked
    b = io.BytesIO(); Image.new("RGB", (8, 8)).save(b, "PNG")
    r = _post(client, lola, b.getvalue(), ct="image/jpeg")
    assert r.status_code == 200 and client.get(r.json()["front_url"]).headers["content-type"] == "image/png"


def test_philhealth_last4_uses_digits_only(con, lola):
    con.execute("update profiles set philhealth_no='12-345678901-2' where id=?", (lola,))
    assert emergency_card(con, lola)["philhealth_last4"] == "9012"
    con.execute("update profiles set philhealth_no='--' where id=?", (lola,))
    assert emergency_card(con, lola)["philhealth_last4"] is None


def test_qr_text_is_emergency_first_and_cut_by_whole_lines(con, lola):
    card = emergency_card(con, lola)
    lines = card["qr_text"].split("\n")
    prefixes = [ln.split(":")[0] for ln in lines[1:]]
    assert prefixes == ["Blood", "Allergy", "Call", "Conditions", "Meds", "Dr", "PhilHealth"]
    assert lines[-1] == "PhilHealth: ****0000"
    # Bloat the low-priority sections: contacts and allergies must survive, lines stay whole.
    for i in range(40):
        con.execute("insert into conditions (profile_id, name) values (?, ?)", (lola, f"Condition number {i}"))
    card = emergency_card(con, lola)
    qr = card["qr_text"]
    assert len(qr) <= 600 and "Penicillin" in qr and "Ana Dela Cruz" in qr and "O+" in qr
    assert all(ln.split(":")[0] in {"Blood", "Allergy", "Call", "Conditions", "Meds", "Dr", "PhilHealth"}
               for ln in qr.split("\n")[1:])
    assert "Condition number 39" not in qr
