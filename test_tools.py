"""Run: uv run python test_tools.py"""

import tempfile
from pathlib import Path

import db

db.DB_PATH = Path(tempfile.mkdtemp()) / "t.db"
import tools  # noqa: E402

r, b = tools.add_expenses(
    {"items": [
        {"amount": 15, "category": "transport", "date": "2026-10-01", "merchant": "Jeep"},
        {"amount": 120.5, "category": "Food", "date": "2026-10-02"},
        {"amount": 99, "category": "made-up", "date": "not a date"},
        {"amount": -5, "category": "Food"},
        {"category": "Food"},
    ]},
    "chat",
)
assert len(r["logged"]) == 3, r
assert r["logged"][0]["category"] == "Transport"
assert r["logged"][2]["category"] == "Others"
assert r["logged"][2]["date"] == tools.today().isoformat()

q, chart = tools.query_spending({"start": "2026-10-02", "end": "2026-10-01", "group_by": "category"}, "")
assert q["total"] == 135.5 and chart and chart["labels"] == ["Food", "Transport"], q

q, _ = tools.query_spending({"start": "2026-10-01", "end": "2026-10-31", "group_by": "nope", "category": "food"}, "")
assert q["group_by"] == "category" and q["total"] == 120.5, q

tools.set_budget({"category": "Food", "amount": 100}, "")
s, _ = tools.budget_status({"month": "2026-10"}, "")
assert s["budgets"][0]["left"] == -20.5, s

eid = r["logged"][1]["id"]
tools.edit_expense({"id": eid, "amount": 200}, "")
assert tools.query_spending({"start": "2026-10-02", "end": "2026-10-02", "group_by": "day"}, "")[0]["total"] == 200
tools.delete_expense({"id": eid}, "")
assert "error" in tools.delete_expense({"id": eid}, "")[0]
import life  # noqa: E402

r, _ = life.add_tasks({"items": [{"title": "Pay rent", "due": "2026-10-15"}, {"title": " "}]}, "")
assert len(r["added"]) == 1
tid = r["added"][0]["id"]
life.complete_tasks({"ids": [tid]}, "")
assert life.list_tasks({"status": "open"}, "")[0]["tasks"] == []
assert "error" in life.complete_tasks({"ids": []}, "")[0]

life.log_habits({"items": [{"name": "workout", "date": "yesterday"}, {"name": "Workout"}]}, "")
h = life.habit_summary({}, "")[0]["habits"]
assert [x["habit"] for x in h] == ["Workout"] and h[0]["streak"] == 2, h
print("ok")
