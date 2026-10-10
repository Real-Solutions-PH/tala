"""Record tools (Task 12) against the seeded database."""

import json

from kapiling.chat import tools


def call(con, pid, name, args=None):
    return tools.TOOLS[name](con, pid, args or {}, None)


def test_get_lab_results_fbs_has_eight_points_and_a_chart(con, lola):
    result, blocks, step = call(con, lola, "get_lab_results", {"code": "fbs"})
    assert step == "check_labs"
    table = next(b for b in blocks if b["type"] == "lab_table")
    chart = next(b for b in blocks if b["type"] == "chart")
    assert len(table["rows"]) == 8 and len(chart["points"]) == 8
    assert chart["code"] == "fbs" and chart["ref_high"] == 100 and chart["ref_low"] == 70 and chart["unit"] == "mg/dL"
    assert chart["points"][-1] == {"date": "2026-07-07", "value": 132}
    assert table["rows"][-1]["flag"] == "high" and table["rows"][-1]["ref"] == "70–100"
    assert len(result["results"]) == 8


def test_lab_results_under_four_points_have_no_chart(con, lola):
    _, blocks, _ = call(con, lola, "get_lab_results", {"code": "hba1c"})
    assert [b["type"] for b in blocks] == ["lab_table"]


def test_lab_results_since_filters(con, lola):
    result, _, _ = call(con, lola, "get_lab_results", {"code": "fbs", "since": "2026-01-01"})
    assert [r["date"] for r in result["results"]] == ["2026-03-02", "2026-07-07"]


def test_lab_results_without_code_is_latest_per_code(con, lola):
    result, blocks, _ = call(con, lola, "get_lab_results")
    codes = [r["code"] for r in result["results"]]
    assert len(codes) == len(set(codes)) and "fbs" in codes and "ldl" in codes
    assert [b["type"] for b in blocks] == ["lab_table"]


def test_lab_results_unknown_code_is_not_on_record(con, lola):
    result, blocks, _ = call(con, lola, "get_lab_results", {"code": "psa"})
    assert result["results"] == [] and blocks == [] and "not_on_record" in result


def test_show_card_philhealth_returns_front_url(con, lola):
    result, blocks, step = call(con, lola, "show_card", {"kind": "philhealth"})
    assert step == "check_cards"
    assert blocks[0]["type"] == "card" and blocks[0]["front_url"].startswith("/api/files/")
    assert blocks[0]["front_url"].endswith("/front") and blocks[0]["label"] == "PhilHealth"
    assert "number" not in json.dumps(result)  # the full number is never handed to the model


def test_show_card_missing_kind(con, lola):
    result, blocks, _ = call(con, lola, "show_card", {"kind": "pwd"})
    assert blocks == [] and "not_on_record" in result


def test_get_profile_only_the_asked_field(con, lola):
    result, blocks, step = call(con, lola, "get_profile", {"fields": ["blood_type"]})
    assert step == "check_profile"
    assert blocks == [{"type": "profile_fields", "fields": [{"key": "blood_type", "value": "O+"}]}]
    assert result == {"blood_type": "O+"}


def test_get_profile_all_fields(con, lola):
    result, blocks, _ = call(con, lola, "get_profile")
    keys = [f["key"] for f in blocks[0]["fields"]]
    assert "full_name" in keys and "allergies" in keys and "age" in keys
    assert "Penicillin" in result["allergies"]


def test_get_profile_ignores_unknown_fields(con, lola):
    result, blocks, _ = call(con, lola, "get_profile", {"fields": ["pin_hash", "blood_type"]})
    assert result == {"blood_type": "O+"}


def test_get_medications_schedule_is_a_list(con, lola):
    result, blocks, step = call(con, lola, "get_medications")
    assert step == "check_meds"
    meds = blocks[0]["meds"]
    assert blocks[0]["type"] == "med_list" and len(meds) == 3
    met = next(m for m in meds if m["name"] == "Metformin")
    assert met == {"name": "Metformin", "strength": "500 mg", "schedule": ["08:00", "20:00"], "purpose": "Blood sugar"}
    assert result["medications"][1]["schedule"] == ["08:00", "20:00"]


def test_get_vaccines_rows_with_next_due(con, lola):
    result, blocks, step = call(con, lola, "get_vaccines")
    assert step == "check_profile" and blocks[0]["type"] == "lab_table"
    flu = next(r for r in blocks[0]["rows"] if r["label"].startswith("Influenza"))
    assert flu["date"] == "2025-04-10" and "2026-04" in (flu["ref"] or "")
    assert any(v["next_due"] == "2026-04" for v in result["vaccines"])


def test_plan_meals_and_activities_always_disclaim(con, lola):
    for name, step in (("plan_meals", "planning_meals"), ("suggest_activities", "planning_activities")):
        result, blocks, s = call(con, lola, name, {})
        assert s == step and blocks[-1] == {"type": "disclaimer"}
        assert "conditions" in result and "allergies" in result


def test_decline_medical_advice(con, lola):
    result, blocks, step = call(con, lola, "decline_medical_advice", {"kind": "medication"})
    assert blocks == [{"type": "refusal", "kind": "medication"}] and step is None


def test_answer_form_stub(con, lola):
    assert call(con, lola, "answer_form") == ({"error": "not_ready"}, [], "reading_form")


def test_schemas_match_tools():
    assert {s["function"]["name"] for s in tools.SCHEMAS} == set(tools.TOOLS)
    assert all(s["type"] == "function" for s in tools.SCHEMAS)


# --- REST: medication schedule as a list (C2) -------------------------------------------

def test_meds_and_summary_routes_return_schedule_lists(client, lola_unlocked):
    p = f"/api/profiles/{lola_unlocked}"
    meds = client.get(f"{p}/meds").json()["meds"]
    assert all(isinstance(m["schedule"], list) for m in meds)
    assert next(m for m in meds if m["name"] == "Metformin")["schedule"] == ["08:00", "20:00"]
    summary = client.get(f"{p}/summary").json()["meds"]
    assert all(isinstance(m["schedule"], list) for m in summary)
