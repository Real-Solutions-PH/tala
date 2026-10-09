"""Tasks and habits tools — same contract as tools.py: (result for the model, block for the UI)."""

import datetime as dt
from typing import Any

from db import connect
from tools import Block, _date, _fn, today


def _tasks(where: str = "1", params: list[Any] | None = None) -> list[dict[str, Any]]:
    rows = connect().execute(
        f"SELECT id, title, due, done_on FROM tasks WHERE {where} "
        "ORDER BY done_on IS NOT NULL, due IS NULL, due, id",
        params or [],
    ).fetchall()
    return [dict(r) for r in rows]


def add_tasks(args: dict[str, Any], source: str) -> tuple[Any, Block | None]:
    con = connect()
    ids = []
    for it in args.get("items") or []:
        title = str(it.get("title") or "").strip()
        if not title:
            continue
        due = _date(it["due"]) if it.get("due") else None
        ids.append(con.execute("INSERT INTO tasks (title, due) VALUES (?, ?)", (title, due)).lastrowid)
    con.commit()
    if not ids:
        return {"error": "nothing added: every task needs a title"}, None
    rows = _tasks(f"id IN ({','.join('?' * len(ids))})", ids)
    return {"added": rows}, {"type": "tasks", "title": f"Added {len(rows)} task{'s' * (len(rows) != 1)}", "rows": rows, "changed": True}


def list_tasks(args: dict[str, Any], source: str) -> tuple[Any, Block | None]:
    status = args.get("status") or "open"
    where = {"open": "done_on IS NULL", "done": "done_on IS NOT NULL"}.get(status, "1")
    rows = _tasks(where)[:50]
    return {"tasks": rows}, ({"type": "tasks", "title": f"Tasks · {status}", "rows": rows} if rows else None)


def complete_tasks(args: dict[str, Any], source: str) -> tuple[Any, Block | None]:
    ids = [int(i) for i in args.get("ids") or [] if str(i).isdigit()]
    if not ids:
        return {"error": "pass the task ids from list_tasks"}, None
    con = connect()
    marks = ",".join("?" * len(ids))
    con.execute(f"UPDATE tasks SET done_on = ? WHERE id IN ({marks}) AND done_on IS NULL", [today().isoformat(), *ids])
    con.commit()
    rows = _tasks(f"id IN ({marks})", ids)
    if not rows:
        return {"error": f"no tasks with ids {ids}"}, None
    return {"completed": rows}, {"type": "tasks", "title": "Done ✓", "rows": rows, "changed": True}


def log_habits(args: dict[str, Any], source: str) -> tuple[Any, Block | None]:
    con = connect()
    logged = []
    for it in args.get("items") or []:
        name = str(it.get("name") or "").strip().capitalize()
        if not name:
            continue
        con.execute("INSERT OR IGNORE INTO habits (name) VALUES (?)", (name,))
        hid, real = con.execute("SELECT id, name FROM habits WHERE name = ?", (name,)).fetchone()
        day = _date(it.get("date"))
        con.execute("INSERT OR IGNORE INTO habit_logs (habit_id, date) VALUES (?, ?)", (hid, day))
        logged.append({"habit": real, "date": day})
    con.commit()
    if not logged:
        return {"error": "nothing logged: every item needs a habit name"}, None
    result, block = habit_summary({"days": 14}, source)
    result["logged"] = logged
    if block:
        block["title"] = "Logged " + ", ".join(x["habit"] for x in logged)
        block["changed"] = True
    return result, block


def habit_summary(args: dict[str, Any], source: str) -> tuple[Any, Block | None]:
    days = max(7, min(int(args.get("days") or 30), 120))
    end = today()
    start = end - dt.timedelta(days=days - 1)
    con = connect()
    out = []
    for h in con.execute("SELECT id, name FROM habits ORDER BY name").fetchall():
        dates = {r[0] for r in con.execute("SELECT date FROM habit_logs WHERE habit_id = ?", (h["id"],))}
        streak, d = 0, end
        if d.isoformat() not in dates:  # today not done yet doesn't break the streak
            d -= dt.timedelta(days=1)
        while d.isoformat() in dates:
            streak, d = streak + 1, d - dt.timedelta(days=1)
        last7 = [(end - dt.timedelta(days=i)).isoformat() in dates for i in range(6, -1, -1)]
        done = sum(1 for x in dates if start.isoformat() <= x <= end.isoformat())
        out.append({"habit": h["name"], "done": done, "days": days, "streak": streak, "last7": last7})
    if not out:
        return {"habits": [], "note": "no habits yet"}, None
    return {"habits": out, "start": start.isoformat(), "end": end.isoformat()}, {
        "type": "habits",
        "title": f"Habits · last {days} days",
        "rows": out,
    }


RUN = {f.__name__: f for f in (add_tasks, list_tasks, complete_tasks, log_habits, habit_summary)}

SCHEMAS = [
    _fn(
        "add_tasks",
        "Add to-dos the user needs to do (e.g. 'remind me to pay Meralco Friday', 'kailangan ko bumili ng gatas').",
        {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Short imperative, e.g. 'Pay Meralco'"},
                        "due": {"type": "string", "description": '"today", "yesterday", or YYYY-MM-DD; omit if none'},
                    },
                    "required": ["title"],
                },
            }
        },
        ["items"],
    ),
    _fn(
        "list_tasks",
        "List tasks with their ids. Use before completing tasks, or when asked what to do.",
        {"status": {"type": "string", "enum": ["open", "done", "all"]}},
    ),
    _fn("complete_tasks", "Mark tasks done by id.", {"ids": {"type": "array", "items": {"type": "integer"}}}, ["ids"]),
    _fn(
        "log_habits",
        "Check off habits the user did (workout, read, meditate, 8 glasses of water...). Creates the habit if new.",
        {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Short habit name, e.g. Workout, Read, Meditate, Water"},
                        "date": {"type": "string", "description": '"today", "yesterday", or YYYY-MM-DD'},
                    },
                    "required": ["name"],
                },
            }
        },
        ["items"],
    ),
    _fn(
        "habit_summary",
        "Habit streaks and completion over the last N days. Use for questions about habits, consistency, streaks.",
        {"days": {"type": "integer"}},
    ),
]
