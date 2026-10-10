"""Task 17: answering a clinic form from a photo, only from what is on record. Model calls are scripted fakes."""
import json
from pathlib import Path

import httpx
import pytest

from kapiling.chat import form
from kapiling.docs import vision

FORM_IMG = Path(__file__).parent.parent / "seed" / "assets" / "intake_form.png"


class FakeVision:
    """Answers the field-reading call and the mapping call by their json_schema name."""

    def __init__(self, fields, answers):
        self.fields, self.answers = fields, answers
        self.payloads: list[dict] = []

    async def post(self, url, payload, timeout):
        self.payloads.append(payload)
        name = payload["response_format"]["json_schema"]["name"]
        body = {"fields": self.fields} if name == "form_fields" else {"answers": self.answers}
        return {"choices": [{"message": {"content": json.dumps(body)}}]}


def _run(monkeypatch, con, pid, fields, answers, lang="en"):
    fv = FakeVision(fields, answers)
    monkeypatch.setattr(vision, "_post", fv.post)
    result, blocks = form.answer_form(con, pid, b"\x89PNG fake", "image/png", lang)
    return result, blocks, fv


def _items(blocks):
    (b,) = [b for b in blocks if b["type"] == "form_answers"]
    return {i["field"]: i for i in b["items"]}


F = lambda label, type="text", options=None: {"label": label, "type": type, "options": options or []}  # noqa: E731


def test_answer_with_nonexistent_source_becomes_null(monkeypatch, con, lola):
    fields = [F("Blood type"), F("Occupation")]
    answers = [
        {"field": "Blood type", "answer": "O+", "source": "profile.blood_type"},
        {"field": "Occupation", "answer": "Retired teacher", "source": "profile.occupation"},  # no such key
    ]
    result, blocks, _ = _run(monkeypatch, con, lola, fields, answers)
    items = _items(blocks)
    assert items["Blood type"] == {"field": "Blood type", "answer": "O+", "source": "profile.blood_type"}
    assert items["Occupation"] == {"field": "Occupation", "answer": None, "source": None}
    assert (result["answered"], result["total"]) == (1, 2)
    assert result["not_on_record"] == ["Occupation"]


def test_out_of_range_index_source_becomes_null(monkeypatch, con, lola):
    fields = [F("Allergies")]
    answers = [{"field": "Allergies", "answer": "Penicillin", "source": "allergies[7].substance"}]
    _, blocks, _ = _run(monkeypatch, con, lola, fields, answers)
    assert _items(blocks)["Allergies"]["answer"] is None


def test_answer_value_differing_from_record_becomes_null(monkeypatch, con, lola):
    fields = [F("Blood type"), F("Contact number"), F("Allergies")]
    answers = [
        {"field": "Blood type", "answer": "A+", "source": "profile.blood_type"},          # record says O+
        {"field": "Contact number", "answer": "0917-000-0001", "source": "profile.phone"},
        {"field": "Allergies", "answer": "Penicillin, Aspirin", "source": "allergies"},   # Aspirin is not on record
    ]
    _, blocks, _ = _run(monkeypatch, con, lola, fields, answers)
    items = _items(blocks)
    assert items["Blood type"]["answer"] is None
    assert items["Contact number"]["answer"] == "0917-000-0001"
    assert items["Allergies"]["answer"] is None


def test_value_check_normalises_case_and_whitespace(monkeypatch, con, lola):
    fields = [F("Last name"), F("Allergies")]
    answers = [
        {"field": "Last name", "answer": "  dela   CRUZ ", "source": "profile.full_name"},
        {"field": "Allergies", "answer": "penicillin;  SHRIMP", "source": "allergies"},
    ]
    _, blocks, _ = _run(monkeypatch, con, lola, fields, answers)
    items = _items(blocks)
    assert items["Last name"]["answer"] == "dela   CRUZ".strip()
    assert items["Allergies"]["answer"] == "penicillin;  SHRIMP"


def test_choice_must_match_whole_word(monkeypatch, con, lola):
    """'Male' is inside 'Female': a substring check would let a wrong choice through."""
    fields = [F("Sex", "choice", ["Male", "Female"])]
    _, blocks, _ = _run(monkeypatch, con, lola, fields, [{"field": "Sex", "answer": "Male", "source": "profile.sex"}])
    assert _items(blocks)["Sex"]["answer"] is None
    _, blocks, _ = _run(monkeypatch, con, lola, fields, [{"field": "Sex", "answer": "Female", "source": "profile.sex"}])
    assert _items(blocks)["Sex"]["answer"] == "Female"


@pytest.mark.parametrize("lang,expected", [("tl", "Oo"), ("en", "Yes")])
def test_checkbox_penicillin_allergy_answers_in_run_language(monkeypatch, con, lola, lang, expected):
    fields = [F("Allergic to penicillin?", "checkbox")]
    answers = [{"field": "Allergic to penicillin?", "answer": "yes", "source": "allergies[0]"}]
    _, blocks, _ = _run(monkeypatch, con, lola, fields, answers, lang=lang)
    assert _items(blocks)["Allergic to penicillin?"] == {
        "field": "Allergic to penicillin?", "answer": expected, "source": "allergies[0]"}


def test_checkbox_yes_needs_the_record_to_name_the_thing(monkeypatch, con, lola):
    fields = [F("Allergic to latex?", "checkbox"), F("Do you smoke?", "checkbox")]
    answers = [
        {"field": "Allergic to latex?", "answer": "yes", "source": "allergies[0]"},  # allergies[0] is penicillin
        {"field": "Do you smoke?", "answer": "no", "source": "conditions"},           # absence is not a recorded no
    ]
    _, blocks, _ = _run(monkeypatch, con, lola, fields, answers)
    items = _items(blocks)
    assert items["Allergic to latex?"]["answer"] is None
    assert items["Do you smoke?"]["answer"] is None


def test_made_up_answers_never_survive(monkeypatch, con, lola):
    """Fails if the Python guard is removed: every answer here is invented or misattributed."""
    fields = [F("Occupation"), F("Civil status", "choice", ["Single", "Married", "Widowed"]), F("Blood type"),
              F("Religion"), F("Hypertension?", "checkbox")]
    answers = [
        {"field": "Occupation", "answer": "Retired teacher", "source": "profile.full_name"},
        {"field": "Civil status", "answer": "Widowed", "source": "profile.civil_status"},
        {"field": "Blood type", "answer": "B+", "source": "profile.blood_type"},
        {"field": "Religion", "answer": "Catholic", "source": None},
        {"field": "Hypertension?", "answer": "yes", "source": "allergies[1]"},
    ]
    result, blocks, _ = _run(monkeypatch, con, lola, fields, answers)
    assert all(i["answer"] is None and i["source"] is None for i in _items(blocks).values())
    assert result["answered"] == 0


def test_items_follow_form_order_and_missing_fields_are_null(monkeypatch, con, lola):
    fields = [F("First name"), F("Middle name"), F("Philhealth no.")]
    answers = [{"field": "Philhealth no.", "answer": "00-000000000-0", "source": "profile.philhealth_no"},
               {"field": "First name", "answer": "Remedios", "source": "profile.full_name"}]
    result, blocks, _ = _run(monkeypatch, con, lola, fields, answers, lang="tl")
    (b,) = blocks
    assert [i["field"] for i in b["items"]] == ["First name", "Middle name", "Philhealth no."]
    assert [i["answer"] for i in b["items"]] == ["Remedios", None, "00-000000000-0"]
    assert result["summary"] == "Nasagot ang 2 sa 3. Ang 1 ay wala sa record."


def test_observations_and_family_history_resolve(monkeypatch, con, lola):
    fields = [F("Latest FBS"), F("Family history"), F("Age")]
    answers = [{"field": "Latest FBS", "answer": "132", "source": "observations.fbs.value"},
               {"field": "Family history", "answer": "Mother: Stroke", "source": "family_history[0]"},
               {"field": "Age", "answer": "73", "source": "profile.age"}]
    _, blocks, _ = _run(monkeypatch, con, lola, fields, answers)
    items = _items(blocks)
    assert items["Latest FBS"]["answer"] == "132"
    assert items["Family history"]["answer"] == "Mother: Stroke"
    assert items["Age"]["answer"] == "73"


def test_both_calls_use_json_schema_and_mapping_sees_the_record(monkeypatch, con, lola):
    _, _, fv = _run(monkeypatch, con, lola, [F("Blood type")], [])
    assert [p["response_format"]["type"] for p in fv.payloads] == ["json_schema", "json_schema"]
    assert [p["response_format"]["json_schema"]["name"] for p in fv.payloads] == ["form_fields", "form_answers"]
    first = fv.payloads[0]["messages"][0]["content"]
    assert first[0]["image_url"]["url"].startswith("data:image/png;base64,")
    assert "Penicillin" in json.dumps(fv.payloads[1]["messages"])


def test_steps_are_reported_in_order(monkeypatch, con, lola):
    monkeypatch.setattr(vision, "_post", FakeVision([F("Blood type")], []).post)
    steps = []
    form.answer_form(con, lola, b"x", "image/png", "en", on_step=steps.append)
    assert steps == ["reading_form", "answering_form"]


def test_no_fields_read_gives_empty_block(monkeypatch, con, lola):
    result, blocks, fv = _run(monkeypatch, con, lola, [], [])
    assert blocks == [{"type": "form_answers", "items": []}]
    assert result["total"] == 0 and len(fv.payloads) == 1  # no mapping call for an empty form


def test_malformed_model_json_reads_as_no_fields(monkeypatch, con, lola):
    async def junk(url, payload, timeout):
        return {"choices": [{"message": {"content": "not json"}}]}

    monkeypatch.setattr(vision, "_post", junk)
    assert asyncio_run(vision.read_form_fields(b"x", "image/png")) == []


def test_vision_down_raises_unavailable(monkeypatch, con, lola):
    async def boom(url, payload, timeout):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(vision, "_post", boom)
    with pytest.raises(vision.VisionUnavailable):
        form.answer_form(con, lola, b"x", "image/png", "en")


def test_seed_intake_form_image_exists():
    from PIL import Image

    with Image.open(FORM_IMG) as im:
        assert im.width >= 1000 and im.height >= 1200


def test_seed_intake_form_scripted_end_to_end(monkeypatch, con, lola):
    fields = [F("Last name"), F("First name"), F("Middle name"), F("Date of birth (YYYY-MM-DD)", "date"), F("Age"),
              F("Sex", "choice", ["Male", "Female"]),
              F("Civil status", "choice", ["Single", "Married", "Widowed", "Separated"]), F("Home address"),
              F("Contact number"), F("PhilHealth no."), F("Blood type"), F("Contact person"), F("Relationship"),
              F("Mobile number"), F("Known allergies"), F("Current medications"), F("Hypertension?", "checkbox"),
              F("Do you smoke?", "checkbox")]
    a = lambda f, ans, src: {"field": f, "answer": ans, "source": src}  # noqa: E731
    answers = [
        a("Last name", "Dela Cruz", "profile.full_name"), a("First name", "Remedios", "profile.full_name"),
        a("Middle name", "Santos", "profile.full_name"),
        a("Date of birth (YYYY-MM-DD)", "1953-04-12", "profile.birth_date"),
        a("Age", "73", "profile.age"), a("Sex", "Female", "profile.sex"), a("Civil status", "Widowed", None),
        a("Home address", "Marikina City, Metro Manila", "profile.address"),
        a("Contact number", "0917-000-0001", "profile.phone"),
        a("PhilHealth no.", "00-000000000-0", "profile.philhealth_no"),
        a("Blood type", "O+", "profile.blood_type"), a("Contact person", "Ana Dela Cruz", "contacts[0].name"),
        a("Relationship", "Daughter", "contacts[0].relation"), a("Mobile number", "0917-000-0002", "contacts[0].phone"),
        a("Known allergies", "Penicillin, Shrimp", "allergies"),
        a("Current medications", "Losartan 50 mg, Metformin 500 mg, Amlodipine 5 mg", "meds"),
        a("Hypertension?", "yes", "conditions[0]"), a("Do you smoke?", "no", None),
    ]
    result, blocks, _ = _run(monkeypatch, con, lola, fields, answers, lang="tl")
    items = _items(blocks)
    assert result["not_on_record"] == ["Civil status", "Do you smoke?"]
    assert items["Hypertension?"]["answer"] == "Oo"
    assert result["summary"] == "Nasagot ang 16 sa 18. Ang 2 ay wala sa record."


def asyncio_run(coro):
    import asyncio

    return asyncio.run(coro)
