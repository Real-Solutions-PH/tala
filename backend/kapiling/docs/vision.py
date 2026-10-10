"""Local vision model (Qwen3-VL on llama-server): transcribe a photo to Markdown, extract lab values as JSON."""

import asyncio
import base64
import json
import re
from datetime import date as _date

import httpx

from kapiling import config

TIMEOUT = 120.0  # seconds per page

TRANSCRIBE_PROMPT = (
    "Transcribe this medical document exactly into Markdown. Use '#' for the facility or document title, "
    "'##' for sections, and Markdown tables for results with columns Test | Result | Unit | Reference range. "
    "Do not add anything that is not on the page. Write [unreadable] for parts you cannot read."
    # Added after the live check: Qwen3-VL 8B turned eGFR's "≥ 60" into unit "mL/min/1.73m² = 60" and range "60".
    " Copy the comparison signs in reference ranges (<, >, <=, >=) exactly, and keep each value in its own column."
)

EXTRACT_PROMPT = (
    "Below is a transcribed medical document. List each test result that is written on it, once, as an observation. "
    "Do not invent results; a document with no test results has an empty list.\n"
    "label: the test name exactly as written.\n"
    "code: 'fbs' for fasting blood sugar or fasting glucose; 'hba1c' for HbA1c; 'total_chol' for total cholesterol; "
    "'ldl' for LDL; 'hdl' for HDL; 'trig' for triglycerides; 'creatinine' for creatinine; 'hemoglobin' for "
    "hemoglobin (not HbA1c); 'weight' for body weight; a blood pressure written as systolic/diastolic is two "
    "observations, 'bp_systolic' and 'bp_diastolic', unit mmHg. Any other test is 'other'.\n"
    "value: the result as a number. value_text: null when value is a number, otherwise the result as written.\n"
    "ref_low and ref_high: the limits of the reference range. 'A - B' gives ref_low A and ref_high B; "
    "'< B' gives only ref_high B; '> A' or '>= A' gives only ref_low A.\n"
    "Dates are YYYY-MM-DD. Also give the document's title, kind, date and facility. "
    "Use null for anything not on the document.\n\n"
)

CODES = ["bp_systolic", "bp_diastolic", "fbs", "hba1c", "total_chol", "ldl", "hdl", "trig", "creatinine", "weight",
         "hemoglobin", "other"]
MAX_OBSERVATIONS = 40   # bounds a repetition loop under the grammar (seen live with a worse prompt)
KINDS = ["lab", "record", "prescription", "discharge", "imaging", "other"]

_str = {"type": ["string", "null"]}
_num = {"type": ["number", "null"]}
SCHEMA = {
    "type": "object",
    "properties": {
        "title": _str, "kind": {"type": "string", "enum": KINDS}, "date": _str, "facility": _str,
        "observations": {"type": "array", "maxItems": MAX_OBSERVATIONS, "items": {
            "type": "object",
            "properties": {"code": {"type": "string", "enum": CODES}, "label": {"type": "string"},
                           "value": _num, "value_text": _str, "unit": _str, "ref_low": _num, "ref_high": _num,
                           "date": _str, "facility": _str},
            "required": ["code", "label", "value", "value_text", "unit", "ref_low", "ref_high", "date", "facility"],
        }},
    },
    "required": ["title", "kind", "date", "facility", "observations"],
}


class VisionUnavailable(Exception):
    """The vision server could not be reached, timed out or answered with an error."""


async def _post(url: str, payload: dict, timeout: float) -> dict:
    """The one seam for model calls (tests substitute it)."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, json=payload)
        r.raise_for_status()
        return r.json()


async def _chat(payload: dict, timeout: float = TIMEOUT) -> str:
    url = f"{config.settings.llm_url}/v1/chat/completions"
    try:
        body = await _post(url, {"temperature": 0, **payload}, timeout)
        return body["choices"][0]["message"]["content"] or ""
    except BaseException as e:
        if isinstance(e, asyncio.CancelledError) or not isinstance(e, Exception):
            raise  # cancellation (and interpreter exits) must propagate
        raise VisionUnavailable(type(e).__name__) from e


async def transcribe(image_bytes: bytes, mime: str) -> str:
    data_url = f"data:{mime};base64,{base64.b64encode(image_bytes).decode()}"
    md = await _chat({"messages": [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": data_url}},
        {"type": "text", "text": TRANSCRIBE_PROMPT},
    ]}]})
    return _strip_fence(md)


def _strip_fence(md: str) -> str:
    m = re.fullmatch(r"\s*```(?:markdown|md)?\s*\n(.*?)\n?```\s*", md, re.S)
    return (m.group(1) if m else md).strip() + "\n"


async def extract(markdown: str) -> dict:
    """Title, kind, date, facility and validated observations. Malformed model output gives no observations."""
    content = await _chat({
        "messages": [{"role": "user", "content": EXTRACT_PROMPT + markdown}],
        "response_format": {"type": "json_schema", "json_schema": {"name": "lab_document", "schema": SCHEMA}},
        "max_tokens": 4096,
    })
    try:
        raw = json.loads(content)
    except json.JSONDecodeError:
        raw = {}
    if not isinstance(raw, dict):
        raw = {}
    meta = {
        "title": _text(raw.get("title")),
        "kind": raw.get("kind") if raw.get("kind") in KINDS else None,
        "date": iso_date(raw.get("date")),
        "facility": _text(raw.get("facility")),
    }
    obs = raw.get("observations") if isinstance(raw.get("observations"), list) else []
    written = numbers_in(markdown)
    seen, meta["observations"] = set(), []
    for o in (validate(x, written) for x in obs if isinstance(x, dict)):
        key = o and tuple(o.values())
        if o and key not in seen:  # drop exact repeats
            seen.add(key)
            meta["observations"].append(o)
    return meta


async def extract_observations(markdown: str) -> list[dict]:
    return (await extract(markdown))["observations"]


def _text(v) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def number(v) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v.strip().replace(",", ""))
        except ValueError:
            return None
    return None


def iso_date(v) -> str | None:
    try:
        return _date.fromisoformat(str(v).strip()[:10]).isoformat() if v else None
    except ValueError:
        return None


# A known code is kept only when the label names that test (live check: the model labelled a whole CBC 'hemoglobin').
LABEL_PATTERNS = {
    "fbs": r"fasting|\bfbs\b",   # random, post-prandial or urine glucose is not FBS
    "hba1c": r"a1c",
    "total_chol": r"total.*cholesterol|cholesterol.*total|^cholesterol$",
    "ldl": r"\bldl\b|low.density",
    "hdl": r"\bhdl\b|high.density",
    "trig": r"triglycerides?|\btg\b",
    "creatinine": r"creatinine",
    "hemoglobin": r"^(?!.*a1c).*(hemoglobin|haemoglobin|\bhgb\b|\bhb\b)",
    "weight": r"weight",
    "bp_systolic": r"\bbp\b|blood pressure|systolic",
    "bp_diastolic": r"\bbp\b|blood pressure|diastolic",
}


_NUMBER = re.compile(r"(?<![\d.])(?:\d{1,3}(?:,\d{3})+|\d+)?(?:\.\d+)?(?![\d])")


def _ref(v, written: set[float]) -> float | None:
    n = number(v)
    return n if _grounded(n, written) else None


def numbers_in(text: str) -> set[float]:
    """Every number written in the text ('132', '7.2', '.9', '1,200'), as floats."""
    out = set()
    for m in _NUMBER.finditer(text or ""):
        tok = m.group(0)
        if tok and tok != ".":
            out.add(round(float(tok.replace(",", "")), 6))
    return out


def _grounded(v: float | None, written: set[float]) -> bool:
    return v is not None and round(v, 6) in written


def validate(o: dict, written: set[float]) -> dict | None:
    """Python-side checks on one model observation: label required, numbers parse, ISO date, known code, and
    grounding: a numeric value that is not written in the transcript is rejected (the model invented it), and an
    unwritten reference limit is dropped. `written` is numbers_in(transcript)."""
    label = _text(o.get("label"))
    if not label:
        return None
    code = o.get("code")
    value = number(o.get("value"))
    if value is not None and not _grounded(value, written):
        return None
    # known codes are charted numbers: one without a number, or whose label names another test, becomes other:<label>
    if code not in LABEL_PATTERNS or value is None or not re.search(LABEL_PATTERNS[code], label, re.I):
        code = f"other:{label}"
    value_text = None if value is not None else _text(o.get("value_text"))  # a number needs no text copy
    if value is None and value_text is None:
        value_text = _text(o.get("value"))
    if value is None and value_text is None:
        return None
    return {"code": code, "label": label, "value": value, "value_text": value_text, "unit": _text(o.get("unit")),
            "ref_low": _ref(o.get("ref_low"), written), "ref_high": _ref(o.get("ref_high"), written),
            "date": iso_date(o.get("date")), "facility": _text(o.get("facility"))}


# ---------------------------------------------------------------- Task 17: reading a form's fields

FORM_FIELD_TYPES = ["text", "date", "checkbox", "choice"]
MAX_FORM_FIELDS = 60  # bounds a repetition loop under the grammar
FORM_FIELDS_PROMPT = (
    "This is a photo of a blank form to be filled in. List every field the person filling it in must answer, in "
    "reading order (top to bottom, left to right), once each. label: the field's label exactly as printed. "
    "type: 'checkbox' for a yes/no tick box or question, 'choice' for pick-one options (list them in options, "
    "exactly as printed), 'date' for a date, otherwise 'text'. options is empty unless type is 'choice'. "
    "Skip headings, instructions, signatures and the parts for clinic staff only. Do not fill anything in."
)
FORM_FIELDS_SCHEMA = {
    "type": "object",
    "properties": {"fields": {"type": "array", "maxItems": MAX_FORM_FIELDS, "items": {
        "type": "object",
        "properties": {"label": {"type": "string"}, "type": {"type": "string", "enum": FORM_FIELD_TYPES},
                       "options": {"type": "array", "items": {"type": "string"}}},
        "required": ["label", "type", "options"],
    }}},
    "required": ["fields"],
}


async def read_form_fields(image_bytes: bytes, mime: str) -> list[dict]:
    """The form's fields in reading order: [{label, type, options}]. Malformed model output gives no fields."""
    data_url = f"data:{mime};base64,{base64.b64encode(image_bytes).decode()}"
    content = await _chat({
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": data_url}},
            {"type": "text", "text": FORM_FIELDS_PROMPT},
        ]}],
        "response_format": {"type": "json_schema", "json_schema": {"name": "form_fields", "schema": FORM_FIELDS_SCHEMA}},
        "max_tokens": 4096,
    })
    try:
        raw = json.loads(content)
    except json.JSONDecodeError:
        return []
    items = raw.get("fields") if isinstance(raw, dict) else None
    out, seen = [], set()
    for f in items if isinstance(items, list) else []:
        label = _text(f.get("label")) if isinstance(f, dict) else None
        if not label or label.casefold() in seen:  # one entry per label: answers are matched back by label
            continue
        seen.add(label.casefold())
        kind = f.get("type") if f.get("type") in FORM_FIELD_TYPES else "text"
        raw_opts = f.get("options") if isinstance(f.get("options"), list) else []
        opts = [o for o in (_text(x) for x in raw_opts) if o]
        out.append({"label": label, "type": kind, "options": opts if kind == "choice" else []})
    return out[:MAX_FORM_FIELDS]
