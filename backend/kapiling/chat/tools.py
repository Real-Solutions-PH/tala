"""Record tools for the agent. Each returns (result for the model, blocks for the client, step name).

Tools are sync and run in the threadpool (search_records calls retrieve.search, which uses asyncio.run).
Safety blocks are added here, never by the model: plan_meals and suggest_activities always end with the
disclaimer, decline_medical_advice always yields the refusal.
"""

import json
import logging
import sqlite3
from collections.abc import Callable
from dataclasses import asdict
from datetime import date
from typing import Any

from kapiling.chat import safety
from kapiling.docs import ingest, retrieve
from kapiling.records import repo
from kapiling.records.summary import _age

ToolResult = tuple[dict, list[dict], str | None]
log = logging.getLogger("kapiling.chat")

CHART_MIN_POINTS = 4
SEARCH_K = 6
PROFILE_FIELDS = ("full_name", "nickname", "birth_date", "age", "sex", "blood_type", "address", "phone",
                  "philhealth_no", "senior_id_no", "allergies", "conditions", "meds", "contacts", "doctor")
LAB_CODES = ("fbs", "hba1c", "bp_systolic", "bp_diastolic", "total_chol", "ldl", "hdl", "trig", "creatinine",
             "weight", "hemoglobin")
_ALIASES = {"bp": ["bp_systolic", "bp_diastolic"], "blood_pressure": ["bp_systolic", "bp_diastolic"],
            "blood_sugar": ["fbs"], "glucose": ["fbs"], "sugar": ["fbs"], "a1c": ["hba1c"],
            "cholesterol": ["total_chol", "ldl", "hdl", "trig"], "lipid": ["total_chol", "ldl", "hdl", "trig"]}
CARD_KINDS = ("philhealth", "senior", "hmo", "pwd", "vaccination", "national_id", "other")
SEARCH_UNAVAILABLE = {"error": "search_unavailable",
                      "message": "The records search is unavailable right now. Tell the person you could not "
                                 "search their documents at the moment; answer only from the RECORD if it has it."}


def schedule_list(raw: str | None) -> list[str]:
    """medications.schedule is stored as JSON text; C2 and the blocks want a list of "HH:MM"."""
    try:
        v = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []
    return [str(s) for s in v] if isinstance(v, list) else []


def _num(v: float) -> str:
    return f"{v:g}"


def _ref(lo, hi) -> str | None:
    if lo is not None and hi is not None:
        return f"{_num(lo)}–{_num(hi)}"
    if hi is not None:
        return f"≤ {_num(hi)}"
    if lo is not None:
        return f"≥ {_num(lo)}"
    return None


def _flag(o) -> str | None:
    v = o["value"]
    if v is None:
        return None
    if o["ref_high"] is not None and v > o["ref_high"]:
        return "high"
    if o["ref_low"] is not None and v < o["ref_low"]:
        return "low"
    return None


# --- profile ---------------------------------------------------------------------------

def _profile_values(con, pid: int) -> dict[str, str]:
    p = repo.get_profile(con, pid)
    if p is None:
        return {}
    out = {k: p[k] for k in ("full_name", "nickname", "birth_date", "blood_type", "address", "phone",
                             "philhealth_no", "senior_id_no")}
    age = _age(p["birth_date"])
    out["age"] = str(age) if age is not None else None
    out["sex"] = p["sex"]
    out["allergies"] = "; ".join(
        a["substance"] + (f" ({', '.join(x for x in (a['reaction'], a['severity']) if x)})" if a["reaction"] or a["severity"] else "")
        for a in repo.list_allergies(con, pid)) or None
    out["conditions"] = "; ".join(c["name"] for c in repo.list_conditions(con, pid)) or None
    out["meds"] = "; ".join(" ".join(x for x in (m["name"], m["strength"]) if x) for m in repo.list_meds(con, pid)) or None
    contacts = repo.list_contacts(con, pid)
    out["contacts"] = "; ".join(f"{c['name']} ({c['relation']}) {c['phone']}" if c["relation"] else f"{c['name']} {c['phone']}"
                                for c in contacts if c["is_emergency"]) or None
    out["doctor"] = "; ".join(", ".join(x for x in (c["name"], c["clinic"], c["phone"]) if x)
                              for c in contacts if c["is_doctor"]) or None
    return out


def get_profile(con, pid: int, args: dict, ctx) -> ToolResult:
    asked = args.get("fields") or list(PROFILE_FIELDS)
    if isinstance(asked, str):
        asked = [asked]
    keys = [k for k in PROFILE_FIELDS if k in set(asked)]  # unknown names (and any column not listed) are ignored
    values = _profile_values(con, pid)
    shown = {k: values[k] for k in keys if values.get(k)}
    result: dict[str, Any] = dict(shown)
    missing = [k for k in keys if k not in shown]
    if missing and args.get("fields"):
        result["not_on_record"] = missing
    blocks = [{"type": "profile_fields", "fields": [{"key": k, "value": v} for k, v in shown.items()]}] if shown else []
    return result, blocks, "check_profile"


# --- medicines --------------------------------------------------------------------------

def get_medications(con, pid: int, args: dict, ctx) -> ToolResult:
    meds = repo.list_meds(con, pid)
    block = [{"name": m["name"], "strength": m["strength"], "schedule": schedule_list(m["schedule"]),
              "purpose": m["purpose"]} for m in meds]
    result = {"medications": [b | {"form": m["form"], "supply_left": m["supply_left"]} for b, m in zip(block, meds)]}
    if not meds:
        result["not_on_record"] = True
    return result, ([{"type": "med_list", "meds": block}] if meds else []), "check_meds"


# --- lab results ---------------------------------------------------------------------------

def _row(o) -> dict:
    return {"label": o["label"], "value": _num(o["value"]) if o["value"] is not None else (o["value_text"] or ""),
            "unit": o["unit"], "ref": _ref(o["ref_low"], o["ref_high"]), "date": o["date"], "flag": _flag(o)}


def get_lab_results(con, pid: int, args: dict, ctx) -> ToolResult:
    code = str(args.get("code") or "").strip().lower().replace(" ", "_")
    since = str(args.get("since") or "")
    if code:
        codes = _ALIASES.get(code, [code])
        per_code = {c: [o for o in repo.observations(con, pid, c) if o["date"] >= since] for c in codes}
        rows = [o for c in codes for o in per_code[c]]
    else:
        per_code = {}
        rows = [o for o in repo.latest_observations(con, pid).values() if o["date"] >= since]
    blocks: list[dict] = []
    if rows:
        blocks.append({"type": "lab_table", "rows": [_row(o) for o in rows]})
    for c, obs in per_code.items():
        pts = [o for o in obs if o["value"] is not None]
        if len(pts) >= CHART_MIN_POINTS:
            last = pts[-1]
            blocks.append({"type": "chart", "code": c, "label": last["label"], "unit": last["unit"],
                           "points": [{"date": o["date"], "value": o["value"]} for o in pts],
                           "ref_low": last["ref_low"], "ref_high": last["ref_high"]})
    result: dict[str, Any] = {"results": [{"code": o["code"], **_row(o)} for o in rows]}
    if not rows:
        result["not_on_record"] = True
    return result, blocks, "check_labs"


# --- cards and vaccines ----------------------------------------------------------------------

def show_card(con, pid: int, args: dict, ctx) -> ToolResult:
    kind = str(args.get("kind") or "").strip().lower()
    card = next((c for c in repo.list_cards(con, pid) if c["kind"] == kind), None)
    if card is None:
        return {"not_on_record": True, "kind": kind}, [], "check_cards"
    block = {"type": "card", "card_id": card["id"], "label": card["label"],
             "front_url": f"/api/files/{card['id']}/front",
             "back_url": f"/api/files/{card['id']}/back" if card["back_path"] else None}
    # The model gets what it needs to talk about the card, not its number.
    return {"shown": card["label"], "kind": kind, "expires": card["expires"]}, [block], "check_cards"


def get_vaccines(con, pid: int, args: dict, ctx) -> ToolResult:
    today = date.today().isoformat()
    vs = repo.list_vaccines(con, pid)
    rows, out = [], []
    for v in vs:
        overdue = bool(v["next_due"]) and v["next_due"] < today[: len(v["next_due"])]
        label = v["name"] + (f" ({v['dose']})" if v["dose"] else "")
        rows.append({"label": label, "value": v["facility"] or "", "unit": None, "ref": v["next_due"],
                     "date": v["date"] or "", "flag": "high" if overdue else None})
        out.append({"name": v["name"], "dose": v["dose"], "date": v["date"], "next_due": v["next_due"],
                    "overdue": overdue, "facility": v["facility"]})
    result: dict[str, Any] = {"vaccines": out}
    if not vs:
        result["not_on_record"] = True
    return result, ([{"type": "lab_table", "rows": rows}] if rows else []), "check_profile"


# --- document search ----------------------------------------------------------------------------

def search_records(con, pid: int, args: dict, ctx) -> ToolResult:
    query = str(args.get("query") or "").strip()
    if not query:
        return {"error": "bad_arguments", "message": "query is required"}, [], "search_records"
    try:
        hits = retrieve.search(con, pid, query, SEARCH_K)
    except (ingest.EmbedUnavailable, retrieve.RerankUnavailable) as e:
        log.warning("search_records: %s", type(e).__name__)
        return dict(SEARCH_UNAVAILABLE), [], "search_records"
    if not hits:
        return {"passages": [], "not_on_record": True}, [], "search_records"
    offset = len(getattr(ctx, "sources", None) or [])  # numbering continues across searches in one reply
    sources = [asdict(s) | {"n": s.n + offset} for s in retrieve.to_sources(hits, query)]
    blocks, seen = [], set()
    for h in hits:
        if h.document_id in seen:
            continue
        seen.add(h.document_id)
        d = con.execute("select date from documents where id=?", (h.document_id,)).fetchone()
        blocks.append({"type": "document", "document_id": h.document_id, "title": h.title,
                       "date": d["date"] if d else None, "thumb_url": f"/api/documents/{h.document_id}/page/1.png"})
    passages = [{"n": s["n"], "title": h.title, "page": h.page, "text": h.text} for s, h in zip(sources, hits)]
    # "_sources" is taken off by the agent and sent as the CUSTOM sources event; the model never sees it.
    return {"passages": passages, "_sources": sources}, blocks, "search_records"


# --- forms (Task 17) ------------------------------------------------------------------------------

def answer_form(con, pid: int, args: dict, ctx) -> ToolResult:
    return {"error": "not_ready"}, [], "reading_form"


# --- plans, always with the fixed disclaimer -------------------------------------------------------

def _health_context(con, pid: int) -> dict:
    return {"conditions": [c["name"] for c in repo.list_conditions(con, pid)],
            "allergies": [a["substance"] for a in repo.list_allergies(con, pid)],
            "medications": [m["name"] for m in repo.list_meds(con, pid)]}


def plan_meals(con, pid: int, args: dict, ctx) -> ToolResult:
    try:
        days = min(7, max(1, int(args.get("days") or 3)))
    except (TypeError, ValueError):
        days = 3
    result = _health_context(con, pid) | {
        "goal": args.get("goal"), "days": days,
        "instructions": f"Write a short, simple Filipino meal plan for {days} day(s) that suits these conditions and "
                        "avoids every allergy listed. No medicine advice. A fixed disclaimer card is shown, so do "
                        "not write your own disclaimer."}
    return result, [safety.DISCLAIMER], "planning_meals"


def suggest_activities(con, pid: int, args: dict, ctx) -> ToolResult:
    result = _health_context(con, pid) | {
        "goal": args.get("goal"),
        "instructions": "Suggest a few gentle, safe activities that suit these conditions (mind joint problems). "
                        "No medicine advice. A fixed disclaimer card is shown, so do not write your own disclaimer."}
    return result, [safety.DISCLAIMER], "planning_activities"


def decline_medical_advice(con, pid: int, args: dict, ctx) -> ToolResult:
    block = safety.refusal(str(args.get("kind") or ""))
    return ({"shown": "refusal", "kind": block["kind"],
             "instructions": "A fixed refusal card is shown. Add at most one short polite sentence pointing them to "
                             "their doctor, plus plain facts on record that would help that conversation."},
            [block], None)


TOOLS: dict[str, Callable[[sqlite3.Connection, int, dict, Any], ToolResult]] = {
    "get_profile": get_profile, "get_medications": get_medications, "get_lab_results": get_lab_results,
    "show_card": show_card, "get_vaccines": get_vaccines, "search_records": search_records,
    "answer_form": answer_form, "plan_meals": plan_meals, "suggest_activities": suggest_activities,
    "decline_medical_advice": decline_medical_advice,
}
# The step shown while a tool runs (announced before it starts, so the client sees it live).
STEPS: dict[str, str | None] = {
    "get_profile": "check_profile", "get_medications": "check_meds", "get_lab_results": "check_labs",
    "show_card": "check_cards", "get_vaccines": "check_profile", "search_records": "search_records",
    "answer_form": "reading_form", "plan_meals": "planning_meals", "suggest_activities": "planning_activities",
    "decline_medical_advice": None,
}


def _fn(name: str, description: str, properties: dict | None = None, required: list[str] | None = None) -> dict:
    return {"type": "function", "function": {"name": name, "description": description, "parameters": {
        "type": "object", "properties": properties or {}, "required": required or []}}}


SCHEMAS: list[dict] = [
    _fn("get_profile", "Profile details: name, birthday, age, sex, blood type, address, phone, PhilHealth and senior "
                       "ID numbers, allergies, conditions, maintenance medicines, emergency contacts, doctor.",
        {"fields": {"type": "array", "items": {"type": "string", "enum": list(PROFILE_FIELDS)},
                    "description": "Only these fields; omit for all."}}),
    _fn("get_medications", "The person's maintenance medicines with strength, schedule and purpose."),
    _fn("get_lab_results", "Lab results and vital signs over time (blood sugar, HbA1c, blood pressure, cholesterol...). "
                           "With a code: that result's history and a chart. Without: the latest of each.",
        {"code": {"type": "string", "description": "One of: " + ", ".join(LAB_CODES) + ", or bp, cholesterol."},
         "since": {"type": "string", "description": "YYYY-MM-DD; only results on or after this date."}}),
    _fn("show_card", "Show an ID or insurance card image (PhilHealth, senior citizen ID, HMO, PWD, vaccination...).",
        {"kind": {"type": "string", "enum": list(CARD_KINDS)}}, ["kind"]),
    _fn("get_vaccines", "Vaccines received and the next due dates."),
    _fn("search_records", "Search the person's scanned documents (lab sheets, discharge summaries, prescriptions).",
        {"query": {"type": "string", "description": "What to look for, in the person's words."}}, ["query"]),
    _fn("answer_form", "Fill in a clinic form from the attached photo using only what is on record."),
    _fn("plan_meals", "Required first for any meal, diet or nutrition question. Returns what the plan must respect.",
        {"goal": {"type": "string"}, "days": {"type": "integer", "minimum": 1, "maximum": 7}}),
    _fn("suggest_activities", "Required first for any exercise or activity question. Returns what to respect.",
        {"goal": {"type": "string"}}),
    _fn("decline_medical_advice", "Call when asked for a diagnosis or medicine advice (dose, interactions, stopping, "
                                  "starting). Shows a fixed refusal card.",
        {"kind": {"type": "string", "enum": list(safety.REFUSAL_KINDS)}}, ["kind"]),
]
