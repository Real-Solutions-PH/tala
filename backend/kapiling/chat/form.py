"""Answer a clinic form from a photo using only what is on record (Task 17).

Two model calls, both under a JSON schema: the vision model reads the form's fields, then the model maps each field
to an answer plus the dotted record key it came from. Python then checks every answer against the record: a source
that does not resolve, or a value that is not in the resolved record value, becomes null. That check, not the
prompt, is what keeps made-up answers off the form.
"""

import asyncio
import json
import re
from collections.abc import Callable
from datetime import date

from kapiling.docs import vision
from kapiling.records import repo

MAP_PROMPT = (
    "You fill in a clinic form for a patient, using ONLY the patient record below. For each form field give:\n"
    "field: the field label exactly as given.\n"
    "answer: the value copied exactly as written in the record (same spelling and format; for a name part such as "
    "last name, copy just that part of full_name; for a list such as allergies or medicines, join the items with "
    "', '). For a checkbox, answer 'yes' only when the record shows it, otherwise null. For a choice, answer with "
    "one of the options. Use null when the record does not have the answer. Never guess or infer.\n"
    "source: the dotted key in the record the answer was copied from, for example profile.blood_type, "
    "allergies[0].substance, allergies, contacts[0].phone or observations.fbs.value. null when answer is null.\n\n"
)
MAP_SCHEMA = {
    "type": "object",
    "properties": {"answers": {"type": "array", "maxItems": vision.MAX_FORM_FIELDS, "items": {
        "type": "object",
        "properties": {"field": {"type": "string"}, "answer": {"type": ["string", "null"]},
                       "source": {"type": ["string", "null"]}},
        "required": ["field", "answer", "source"],
    }}},
    "required": ["answers"],
}

CHECKBOX = {"en": ("Yes", "No"), "tl": ("Oo", "Hindi")}
_YES = {"yes", "oo", "y", "true", "checked", "x"}
SUMMARY = {
    "en": "Answered {n} of {t}. {m} aren't on record.",
    "tl": "Nasagot ang {n} sa {t}. Ang {m} ay wala sa record.",
}
# Words that never ground a checkbox on their own.
_STOP = {"allergic", "allergy", "allergies", "with", "have", "history", "does", "were", "your", "from", "that",
         "this", "what", "when", "patient", "taking", "currently", "ever", "been", "high", "disease", "problem"}


# ---------------------------------------------------------------- the record

def _age(birth: str | None) -> int | None:
    try:
        b = date.fromisoformat(birth or "")
    except ValueError:
        return None
    t = date.today()
    return t.year - b.year - ((t.month, t.day) < (b.month, b.day))


def _pick(row, keys) -> dict:
    return {k: row[k] for k in keys}


def build_record(con, pid: int) -> dict:
    """The structured record the mapping call sees and every source is resolved against."""
    p = repo.get_profile(con, pid)
    if p is None:
        raise KeyError(pid)
    profile = _pick(p, ["full_name", "nickname", "birth_date", "blood_type", "address", "phone", "philhealth_no",
                        "senior_id_no"])
    profile["sex"] = {"F": "Female", "M": "Male"}.get(p["sex"])
    profile["age"] = _age(p["birth_date"])
    meds = []
    for m in repo.list_meds(con, pid):
        d = _pick(m, ["name", "strength", "form", "purpose", "prescriber"])
        d["schedule"] = json.loads(m["schedule"] or "[]")
        meds.append(d)
    return {
        "profile": profile,
        "contacts": [_pick(c, ["name", "relation", "phone", "specialty", "clinic"])
                     | {"is_emergency": bool(c["is_emergency"]), "is_doctor": bool(c["is_doctor"])}
                     for c in repo.list_contacts(con, pid)],
        "conditions": [_pick(c, ["name", "since", "notes"]) for c in repo.list_conditions(con, pid)],
        "allergies": [_pick(a, ["substance", "reaction", "severity"]) for a in repo.list_allergies(con, pid)],
        "meds": meds,
        "vaccines": [_pick(v, ["name", "dose", "date", "next_due", "facility"]) for v in repo.list_vaccines(con, pid)],
        "family_history": [_pick(f, ["relation", "condition"]) for f in con.execute(
            "select relation, condition from family_history where profile_id=? order by id", (pid,))],
        "observations": {code: _pick(o, ["label", "value", "value_text", "unit", "date"])
                         for code, o in repo.latest_observations(con, pid).items()},
    }


# ---------------------------------------------------------------- validation

_TOKEN = re.compile(r"\[(\d+)\]|([^.\[\]]+)")
_MISSING = object()


def resolve(record: dict, source) -> object:
    """The value at a dotted key such as allergies[0].substance, or _MISSING when it does not resolve."""
    if not isinstance(source, str) or not source.strip():
        return _MISSING
    s = source.strip()
    pos, cur = 0, record
    for m in _TOKEN.finditer(s):
        if m.start() != pos and s[pos:m.start()] != ".":
            return _MISSING
        pos = m.end()
        idx, key = m.group(1), m.group(2)
        if idx is not None:
            if not isinstance(cur, list) or int(idx) >= len(cur):
                return _MISSING
            cur = cur[int(idx)]
        else:
            if not isinstance(cur, dict) or key not in cur:
                return _MISSING
            cur = cur[key]
    if pos != len(s) or cur is None or cur == [] or cur == {}:
        return _MISSING
    return cur


def _scalars(v) -> list[str]:
    if isinstance(v, dict):
        return [s for x in v.values() for s in _scalars(x)]
    if isinstance(v, list):
        return [s for x in v for s in _scalars(x)]
    if v is None or isinstance(v, bool):
        return []
    if isinstance(v, float):
        return [f"{v:g}"]
    return [str(v)]


def _norm(s: str) -> str:
    return " ".join(re.sub(r"[:|()\"]", " ", s.casefold()).split())


def _contains(haystack: str, needle: str) -> bool:
    return bool(needle) and re.search(r"(?<!\w)" + re.escape(needle) + r"(?!\w)", haystack) is not None


def check(field: dict, answer, source, record: dict, lang: str) -> str | None:
    """The answer to put on the form, or None when the record does not back it."""
    if not isinstance(answer, str) or not answer.strip():
        return None
    value = resolve(record, source)
    if value is _MISSING:
        return None
    text = _norm(" ".join(_scalars(value)))
    if field["type"] == "checkbox":
        if _norm(answer) not in _YES:
            return None  # a missing entry is not a recorded "no"
        words = [w for w in re.findall(r"[a-z0-9]+", field["label"].casefold()) if len(w) >= 4 and w not in _STOP]
        if not any(_contains(text, w) for w in words):
            return None  # the cited entry must name what the box asks about
        return CHECKBOX.get(lang, CHECKBOX["en"])[0]
    if field["type"] == "choice" and field["options"] and _norm(answer) not in {_norm(o) for o in field["options"]}:
        return None
    parts = [_norm(p) for p in re.split(r"[,;\n]", answer)]
    parts = [p for p in parts if p]
    if not parts or not all(_contains(text, p) for p in parts):
        return None
    return answer.strip()


# ---------------------------------------------------------------- the two calls

async def _map(fields: list[dict], record: dict) -> list[dict]:
    content = await vision._chat({
        "messages": [{"role": "user", "content": MAP_PROMPT + "Patient record:\n" + json.dumps(record, ensure_ascii=False)
                      + "\n\nForm fields:\n" + json.dumps(fields, ensure_ascii=False)}],
        "response_format": {"type": "json_schema", "json_schema": {"name": "form_answers", "schema": MAP_SCHEMA}},
        "max_tokens": 4096,
    })
    try:
        raw = json.loads(content)
    except json.JSONDecodeError:
        return []
    items = raw.get("answers") if isinstance(raw, dict) else None
    return [a for a in items if isinstance(a, dict)] if isinstance(items, list) else []


def answer_form(con, profile_id: int, image_bytes: bytes, mime: str, lang: str,
                on_step: Callable[[str], None] | None = None) -> tuple[dict, list[dict]]:
    """Read the form in the photo and answer each field from the record. Returns (result_for_model, blocks).
    Sync, for a threadpool. Raises vision.VisionUnavailable when the model server is down."""
    step = on_step or (lambda _name: None)
    lang = lang if lang in SUMMARY else "en"
    step("reading_form")
    fields = asyncio.run(vision.read_form_fields(image_bytes, mime))
    step("answering_form")
    record = build_record(con, profile_id)
    mapped = asyncio.run(_map(fields, record)) if fields else []
    by_label: dict[str, dict] = {}
    for a in mapped:
        key = _norm(str(a.get("field") or ""))
        by_label.setdefault(key, a)
    items = []
    for f in fields:
        a = by_label.get(_norm(f["label"]), {})
        answer = check(f, a.get("answer"), a.get("source"), record, lang)
        items.append({"field": f["label"], "answer": answer, "source": a["source"].strip() if answer else None})
    answered = sum(1 for i in items if i["answer"] is not None)
    missing = [i["field"] for i in items if i["answer"] is None]
    result = {
        "answered": answered, "total": len(items), "not_on_record": missing,
        "summary": SUMMARY[lang].format(n=answered, t=len(items), m=len(missing)),
        "note": "The answers are shown to the user in a form_answers block. Reply only with the summary; "
                "do not list or add answers.",
    }
    return result, [{"type": "form_answers", "items": items}]
