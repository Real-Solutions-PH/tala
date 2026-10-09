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

