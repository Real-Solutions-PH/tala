"""Fixed safety blocks (spec section 2). Their text lives in the client's i18n catalogue (safety.*), never in
model output: the server only decides that a block is shown."""

import re

DISCLAIMER = {"type": "disclaimer"}
REFUSAL_KINDS = ("diagnosis", "medication")

# A deterministic pre-check, so a refusal is shown even when the model fails to call decline_medical_advice.
# Lower-case substrings, English and Tagalog. Kept short on purpose: Task 19's eval measures it.
_MEDICATION = ("itigil", "ihinto", "doblehin", "stop taking", "double my", "increase my dose")
_DIAGNOSIS = ("ano ang sakit ko", "do i have", "diagnose")


def refusal(kind: str) -> dict:
    return {"type": "refusal", "kind": kind if kind in REFUSAL_KINDS else "medication"}


def precheck(text: str) -> str | None:
    """'medication' or 'diagnosis' when the request asks for medicine changes or a diagnosis, else None."""
    t = re.sub(r"\s+", " ", (text or "").lower())
    if any(k in t for k in _MEDICATION):
        return "medication"
    if any(k in t for k in _DIAGNOSIS):
        return "diagnosis"
    return None
