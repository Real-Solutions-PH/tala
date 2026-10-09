"""Fictional demo persona for Kapiling. Every name, number and date here is made up.

Demo-only PINs: owner 123456 (both profiles), representative Ana 246810 (for Lola).
"""
import json
import shutil
import sqlite3
from pathlib import Path

from kapiling import config
from kapiling.auth.lock import hash_pin

ASSETS = Path(__file__).resolve().parent / "assets"

OWNER_PIN = "123456"
REP_PIN = "246810"

LAB_FACILITY = "Marikina Valley Diagnostic Center"
CLINIC = "Marikina Valley Medical Clinic"
DOCTOR = "Dr. Jose Reyes"

# 8 quarterly-ish checkups, 2024-07 .. 2026-07: (date, fbs, systolic, diastolic)
CHECKUPS = [
    ("2024-07-02", 118, 128, 80),
    ("2024-12-03", 121, 130, 80),
    ("2025-03-04", 123, 132, 82),
    ("2025-06-03", 125, 134, 82),
    ("2025-09-02", 126, 136, 84),
    ("2025-12-02", 128, 138, 86),
    ("2026-03-02", 130, 140, 86),
    ("2026-07-07", 132, 142, 88),
]
HBA1C = [("2025-09-02", 6.9), ("2026-03-02", 7.2)]
LIPID_DATE = "2025-12-02"
LIPID = {"total_chol": 212, "ldl": 131, "hdl": 46, "trig": 175}

# Lab sheets shared with make_images so the pictures match the seeded values.
CREATININE_DATE = "2025-09-02"
CBC_DATE = "2026-03-02"

CARDS = [  # kind, label, number, expires, asset stem
    ("philhealth", "PhilHealth", "00-000000000-0", None, "philhealth"),
    ("senior", "Senior Citizen ID", "0000-SAMPLE", None, "senior"),
    ("hmo", "HMO (CareFirst Health)", "HMO-000-000-000", "2027-12-31", "hmo"),
    ("vaccination", "Vaccination card", None, None, "vaccination"),
]


def _copy(rel_dir: str, name: str) -> str:
    """Copy an asset into data_dir/files/<rel_dir>/ and return the path relative to data_dir."""
    src = ASSETS / name
    if not src.is_file():
        raise FileNotFoundError(f"missing seed asset {src}; run: uv run python -m seed.make_images")
    dest_rel = Path("files") / rel_dir / name
    dest = config.settings.data_dir / dest_rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)
    return dest_rel.as_posix()


def _profile(con, **f) -> int:
    cols = ", ".join(f)
    cur = con.execute(f"insert into profiles ({cols}) values ({', '.join('?' * len(f))})", tuple(f.values()))
    pid = cur.lastrowid
    con.execute("insert into emergency_fields (profile_id) values (?)", (pid,))
    con.execute("insert into owner_lock (profile_id, pin_hash) values (?, ?)", (pid, hash_pin(OWNER_PIN)))
    return pid


def _obs(con, pid, code, label, value, unit, lo, hi, date, facility=LAB_FACILITY):
    con.execute(
        "insert into observations (profile_id, code, label, value, unit, ref_low, ref_high, date, facility, status)"
        " values (?,?,?,?,?,?,?,?,?, 'confirmed')",
        (pid, code, label, value, unit, lo, hi, date, facility),
    )


def _seed_lola(con) -> int:
    pid = _profile(
        con, full_name="Remedios Santos Dela Cruz", nickname="Lola Remy", birth_date="1953-04-12", sex="F",
        blood_type="O+", address="Marikina City, Metro Manila", phone="0917-000-0001",
        philhealth_no="00-000000000-0", senior_id_no="0000-SAMPLE", language="tl",
        photo_path=_copy("profile", "avatar_lola.png"),
    )
    for name, since, notes in [
        ("Hypertension", "2011", None),
        ("Type 2 diabetes", "2016", None),
        ("Osteoarthritis of the knee", None, "Both knees, worse on stairs"),
    ]:
        con.execute("insert into conditions (profile_id, name, since, notes) values (?,?,?,?)", (pid, name, since, notes))
    con.executemany(
        "insert into allergies (profile_id, substance, reaction, severity) values (?,?,?,?)",
        [(pid, "Penicillin", "Rash", "moderate"), (pid, "Shrimp", "Hives", "mild")],
    )
    for name, strength, purpose, sched, supply in [
        ("Losartan", "50 mg", "Blood pressure", ["08:00"], 24),
        ("Metformin", "500 mg", "Blood sugar", ["08:00", "20:00"], 40),
        ("Amlodipine", "5 mg", "Blood pressure", ["20:00"], 18),
    ]:
        con.execute(
            "insert into medications (profile_id, name, strength, form, purpose, prescriber, schedule, start_date, supply_left, active)"
            " values (?,?,?,?,?,?,?,?,?,1)",
            (pid, name, strength, "tablet", purpose, DOCTOR, json.dumps(sched), "2024-01-10", supply),
        )
    con.executemany(
        "insert into vaccines (profile_id, name, dose, date, next_due, facility) values (?,?,?,?,?,?)",
        [
            (pid, "Influenza", "Annual", "2025-04-10", "2026-04", CLINIC),
            (pid, "PCV13", "1", "2023-06-02", None, CLINIC),
            (pid, "COVID-19 booster", "Booster", "2023-01-15", None, "Marikina City Health Office"),
        ],
    )
    con.executemany(
        "insert into contacts (profile_id, name, relation, phone, is_emergency, is_doctor, specialty, clinic) values (?,?,?,?,?,?,?,?)",
        [
            (pid, "Ana Dela Cruz", "Daughter", "0917-000-0002", 1, 0, None, None),
            (pid, DOCTOR, "Doctor", "02-8000-0000", 0, 1, "Internal Medicine", CLINIC),
        ],
    )
    con.executemany(
        "insert into family_history (profile_id, relation, condition) values (?,?,?)",
        [(pid, "Mother", "Stroke"), (pid, "Father", "Diabetes")],
    )
    for date, fbs, sys_, dia in CHECKUPS:
        _obs(con, pid, "fbs", "Fasting blood sugar", fbs, "mg/dL", 70, 100, date)
        _obs(con, pid, "bp_systolic", "Blood pressure (systolic)", sys_, "mmHg", 90, 120, date, CLINIC)
        _obs(con, pid, "bp_diastolic", "Blood pressure (diastolic)", dia, "mmHg", 60, 80, date, CLINIC)
        con.execute(
            "insert into visits (profile_id, date, facility, doctor, reason, notes) values (?,?,?,?,?,?)",
            (pid, date, CLINIC, DOCTOR, "Maintenance check-up", f"BP {sys_}/{dia}, FBS {fbs} mg/dL"),
        )
    for date, v in HBA1C:
        _obs(con, pid, "hba1c", "HbA1c", v, "%", 4.0, 5.6, date)
    _obs(con, pid, "total_chol", "Total cholesterol", LIPID["total_chol"], "mg/dL", None, 200, LIPID_DATE)
    _obs(con, pid, "ldl", "LDL cholesterol", LIPID["ldl"], "mg/dL", None, 130, LIPID_DATE)
    _obs(con, pid, "hdl", "HDL cholesterol", LIPID["hdl"], "mg/dL", 40, None, LIPID_DATE)
    _obs(con, pid, "trig", "Triglycerides", LIPID["trig"], "mg/dL", None, 150, LIPID_DATE)
    for i, (kind, label, number, expires, stem) in enumerate(CARDS):
        con.execute(
            "insert into cards (profile_id, kind, label, number, front_path, back_path, expires, sort) values (?,?,?,?,?,?,?,?)",
            (pid, kind, label, number, _copy("cards", f"card_{stem}_front.png"),
             _copy("cards", f"card_{stem}_back.png"), expires, i),
        )
    con.execute(
        "insert into representatives (profile_id, name, relation, pin_hash) values (?,?,?,?)",
        (pid, "Ana Dela Cruz", "Daughter", hash_pin(REP_PIN)),
    )
    return pid


def _seed_mika(con) -> int:
    pid = _profile(
        con, full_name="Mika Dela Cruz", nickname="Mika", birth_date="2020-02-03", sex="F",
        blood_type="A+", address="Marikina City, Metro Manila", phone="0917-000-0002", language="tl",
        photo_path=_copy("profile", "avatar_mika.png"),
    )
    con.execute(
        "insert into contacts (profile_id, name, relation, phone, is_emergency) values (?,?,?,?,1)",
        (pid, "Ana Dela Cruz", "Mother", "0917-000-0002"),
    )
    f = "Marikina City Health Office"
    # DOH routine childhood immunization (Expanded Program on Immunization)
    rows = [
        ("BCG", "1", "2020-02-03", None),
        ("Hepatitis B", "Birth dose", "2020-02-03", None),
        ("Pentavalent (DPT-HepB-Hib)", "1", "2020-03-16", None),
        ("Pentavalent (DPT-HepB-Hib)", "2", "2020-04-13", None),
        ("Pentavalent (DPT-HepB-Hib)", "3", "2020-05-11", None),
        ("OPV", "1", "2020-03-16", None),
        ("OPV", "2", "2020-04-13", None),
        ("OPV", "3", "2020-05-11", None),
        ("IPV", "1", "2020-05-11", None),
        ("IPV", "2", "2020-09-14", None),
        ("PCV", "1", "2020-03-16", None),
        ("PCV", "2", "2020-04-13", None),
        ("PCV", "3", "2020-05-11", None),
        ("MMR", "1", "2021-02-03", None),
        ("MMR", "2", "2021-08-03", None),
        ("Td (Grade 1 booster)", "Booster", "2026-07-20", None),
        # age-6 school booster, overdue and not yet given
        ("MR (Grade 1 booster)", "Booster", None, "2026-08-01"),
    ]
    con.executemany(
        "insert into vaccines (profile_id, name, dose, date, next_due, facility) values (?,?,?,?,?,?)",
        [(pid, n, d, dt, nd, f) for n, d, dt, nd in rows],
    )
    return pid


def seed(con: sqlite3.Connection) -> dict[str, int]:
    lola = _seed_lola(con)
    mika = _seed_mika(con)
    con.commit()
    return {"lola": lola, "mika": mika}


def main() -> None:
    """Seed the configured database once; do nothing if it already has profiles."""
    from kapiling import db

    con = db.connect()
    try:
        if con.execute("select count(*) from profiles").fetchone()[0]:
            print("Database already has profiles; nothing seeded.")
        else:
            seed(con)
            print("Seeded the demo persona (Lola Remy and Mika).")
    finally:
        con.close()


if __name__ == "__main__":
    main()
