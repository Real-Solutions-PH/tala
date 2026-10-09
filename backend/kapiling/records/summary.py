import json
from datetime import date

from kapiling.records import repo

_H = {
    "en": {"profile": "Profile", "allergies": "Allergies", "conditions": "Conditions",
           "meds": "Maintenance medicines", "results": "Latest results", "vaccines": "Vaccines",
           "contact": "Emergency contact", "doctor": "Doctor", "none": "none recorded",
           "born": "born", "blood": "blood type", "sex": {"F": "female", "M": "male"}},
    "tl": {"profile": "Profile", "allergies": "Mga allergy", "conditions": "Mga karamdaman",
           "meds": "Mga maintenance na gamot", "results": "Pinakabagong resulta", "vaccines": "Mga bakuna",
           "contact": "Contact sa emergency", "doctor": "Doktor", "none": "wala pang nakatala",
           "born": "ipinanganak", "blood": "blood type", "sex": {"F": "babae", "M": "lalaki"}},
}
_CODES = {"fbs": "FBS", "hba1c": "HbA1c", "bp_systolic": "BP systolic", "bp_diastolic": "BP diastolic",
          "total_chol": "Total cholesterol", "ldl": "LDL", "hdl": "HDL", "trig": "Triglycerides",
          "creatinine": "Creatinine", "weight": "Weight", "hemoglobin": "Hemoglobin"}
_DEFAULT_FIELDS = ["photo", "age", "blood_type", "allergies", "conditions", "meds", "contacts", "doctor", "philhealth_last4"]


def _age(birth: str, today: date | None = None) -> int | None:
    try:
        b = date.fromisoformat(birth)
    except (TypeError, ValueError):
        return None
    t = today or date.today()
    return t.year - b.year - ((t.month, t.day) < (b.month, b.day))


def _num(v: float) -> str:
    return f"{v:g}"


def _med(m) -> str:
    return " ".join(x for x in (m["name"], m["strength"]) if x)


def essential_summary(con, pid: int, lang: str = "en") -> str:
    h = _H.get(lang, _H["en"])
    p = repo.get_profile(con, pid)
    if p is None:
        raise KeyError(pid)
    age = _age(p["birth_date"])
    bits = [p["full_name"], f"{h['born']} {p['birth_date']}" + (f" ({age})" if age is not None else "")]
    if p["sex"]:
        bits.append(h["sex"][p["sex"]])
    if p["blood_type"]:
        bits.append(f"{h['blood']} {p['blood_type']}")
    lines = [f"{h['profile']}: " + ", ".join(bits)]

    def section(title, items):
        lines.append(f"{title}: " + ("; ".join(items) if items else h["none"]))

    section(h["allergies"], [" ".join(x for x in (a["substance"], f"({a['reaction']}, {a['severity']})" if a["reaction"] else "") if x)
                             for a in repo.list_allergies(con, pid)])
    section(h["conditions"], [c["name"] + (f" (since {c['since']})" if c["since"] else "") for c in repo.list_conditions(con, pid)])
    section(h["meds"], [f"{_med(m)} at {', '.join(json.loads(m['schedule'] or '[]'))}".strip() for m in repo.list_meds(con, pid)])
    section(h["results"], [
        f"{_CODES.get(code, o['label'])} {_num(o['value']) if o['value'] is not None else o['value_text']}"
        f"{' ' + o['unit'] if o['unit'] else ''} ({o['date']})"
        for code, o in repo.latest_observations(con, pid).items() if o["value"] is not None or o["value_text"]])
    section(h["vaccines"], [f"{v['name']} {v['dose'] or ''} ({v['date'] or 'due ' + str(v['next_due'])})".replace("  ", " ")
                            for v in repo.list_vaccines(con, pid)][:12])
    contacts = repo.list_contacts(con, pid)
    section(h["contact"], [f"{c['name']} ({c['relation']}) {c['phone']}" for c in contacts if c["is_emergency"]])
    section(h["doctor"], [f"{c['name']}, {c['clinic'] or ''} {c['phone']}".replace(" ,", ",") for c in contacts if c["is_doctor"]])
    return "\n".join(lines)


def _fields(con, pid: int) -> set[str]:
    row = con.execute("select fields from emergency_fields where profile_id=?", (pid,)).fetchone()
    return set(json.loads(row["fields"])) if row else set(_DEFAULT_FIELDS)


def emergency_card(con, pid: int) -> dict:
    p = repo.get_profile(con, pid)
    if p is None:
        raise KeyError(pid)
    f = _fields(con, pid)
    contacts = repo.list_contacts(con, pid)
    doc = next((c for c in contacts if c["is_doctor"]), None)
    card = {
        "profile_id": pid,
        "name": p["nickname"] or p["full_name"],
        "photo_url": f"/api/profiles/{pid}/photo" if "photo" in f and p["photo_path"] else None,
        "age": _age(p["birth_date"]) if "age" in f else None,
        "blood_type": p["blood_type"] if "blood_type" in f else None,
        "allergies": [{"substance": a["substance"], "reaction": a["reaction"], "severity": a["severity"]}
                      for a in repo.list_allergies(con, pid)] if "allergies" in f else [],
        "conditions": [c["name"] for c in repo.list_conditions(con, pid)] if "conditions" in f else [],
        "meds": [{"name": m["name"], "strength": m["strength"], "schedule": json.loads(m["schedule"] or "[]")}
                 for m in repo.list_meds(con, pid)] if "meds" in f else [],
        "contacts": [{"name": c["name"], "relation": c["relation"], "phone": c["phone"]}
                     for c in contacts if c["is_emergency"]] if "contacts" in f else [],
        "doctor": {"name": doc["name"], "clinic": doc["clinic"], "phone": doc["phone"]} if doc and "doctor" in f else None,
        "philhealth_last4": _last4_digits(p["philhealth_no"]) if "philhealth_last4" in f else None,
    }
    card["qr_text"] = _qr_text(card)
    return card


def _last4_digits(number: str | None) -> str | None:
    digits = "".join(ch for ch in number or "" if ch.isdigit())
    return digits[-4:] if digits else None


QR_MAX = 600


def _qr_text(c: dict) -> str:
    """Emergency-first lines; when over QR_MAX, lines that do not fit are dropped whole, lowest priority losing out."""
    lines = [f"{c['name']}" + (f", {c['age']}" if c["age"] is not None else "")]
    if c["blood_type"]:
        lines.append(f"Blood: {c['blood_type']}")
    if c["allergies"]:
        lines.append("Allergy: " + ", ".join(a["substance"] for a in c["allergies"]))
    if c["contacts"]:
        lines.append("Call: " + "; ".join(f"{x['name']} {x['phone']}" for x in c["contacts"]))
    if c["conditions"]:
        lines.append("Conditions: " + ", ".join(c["conditions"]))
    if c["meds"]:
        lines.append("Meds: " + ", ".join(" ".join(x for x in (m["name"], m["strength"]) if x) for m in c["meds"]))
    if c["doctor"]:
        lines.append(f"Dr: {c['doctor']['name']} {c['doctor']['phone']}")
    if c["philhealth_last4"]:
        lines.append(f"PhilHealth: ****{c['philhealth_last4']}")
    out: list[str] = []
    size = 0
    for line in lines:
        add = len(line) + (1 if out else 0)
        if size + add <= QR_MAX:
            out.append(line)
            size += add
    if not out:  # a name longer than the whole budget
        out = [lines[0][:QR_MAX]]
    return "\n".join(out)
