"""Agent tools. Every number the user sees comes from SQL here, never from the model."""

import datetime as dt
from typing import Any

from db import CATEGORIES, connect, to_cents, to_pesos

Block = dict[str, Any]


def today() -> dt.date:
    # ponytail: laptop clock is the user's clock (Asia/Manila on the demo machine)
    return dt.date.today()


def _date(s: Any, default: dt.date | None = None) -> str:
    word = str(s or "").strip().lower()
    if word in ("yesterday", "kahapon"):
        return (today() - dt.timedelta(days=1)).isoformat()
    if word in ("today", "kanina", "ngayon"):
        return today().isoformat()
    try:
        return dt.date.fromisoformat(str(s)[:10]).isoformat()
    except (TypeError, ValueError):
        return (default or today()).isoformat()


def _category(s: Any) -> str:
    s = str(s or "").strip().lower()
    return next((c for c in CATEGORIES if c.lower() == s), "Others")


def _range(args: dict[str, Any]) -> tuple[str, str]:
    end = _date(args.get("end"))
    start = _date(args.get("start"), dt.date.fromisoformat(end).replace(day=1))
    return (start, end) if start <= end else (end, start)


def _rows_out(rows: list[Any]) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        d = dict(r)
        d["amount"] = to_pesos(d.pop("cents"))
        out.append(d)
    return out


def add_expenses(args: dict[str, Any], source: str) -> tuple[Any, Block | None]:
    items = args.get("items") or []
    con = connect()
    ids = []
    for it in items:
        try:
            cents = to_cents(it["amount"])
        except (KeyError, TypeError, ValueError):
            continue
        if cents <= 0:
            continue
        cur = con.execute(
            "INSERT INTO expenses (date, cents, category, merchant, note, source) VALUES (?,?,?,?,?,?)",
            (
                _date(it.get("date")),
                cents,
                _category(it.get("category")),
                (it.get("merchant") or None),
                (it.get("note") or None),
                source,
            ),
        )
        ids.append(cur.lastrowid)
    con.commit()
    if not ids:
        return {"error": "nothing logged: every item needs a positive amount"}, None
    marks = ",".join("?" * len(ids))
    rows = _rows_out(
        con.execute(f"SELECT * FROM expenses WHERE id IN ({marks})", ids).fetchall()
    )
    total = sum(r["amount"] for r in rows)
    return {"logged": rows, "total": total}, {
        "type": "table",
        "title": f"Logged {len(rows)} expense{'s' * (len(rows) != 1)}",
        "rows": rows,
        "changed": True,
    }


GROUPS = {
    "category": ("category", "doughnut"),
    "merchant": ("COALESCE(merchant, 'Unknown')", "bar"),
    "day": ("date", "line"),
    "week": ("strftime('%Y-W%W', date)", "bar"),
    "month": ("substr(date, 1, 7)", "bar"),
}


def query_spending(args: dict[str, Any], source: str) -> tuple[Any, Block | None]:
    start, end = _range(args)
    key = args.get("group_by") if args.get("group_by") in GROUPS else "category"
    expr, kind = GROUPS[key]
    where, params = "date BETWEEN ? AND ?", [start, end]
    if args.get("category"):
        where += " AND category = ?"
        params.append(_category(args["category"]))
    order = "1" if key in ("day", "week", "month") else "2 DESC"
    rows = connect().execute(
        f"SELECT {expr} AS label, SUM(cents) AS cents, COUNT(*) AS n FROM expenses WHERE {where} GROUP BY 1 ORDER BY {order} LIMIT 40",
        params,
    ).fetchall()
    data = [
        {"label": r["label"], "amount": to_pesos(r["cents"]), "count": r["n"]}
        for r in rows
    ]
    total = round(sum(d["amount"] for d in data), 2)
    scope = f" on {_category(args['category'])}" if args.get("category") else ""
    title = f"Spending{scope} by {key} · {start} to {end}"
    result = {"start": start, "end": end, "group_by": key, "rows": data, "total": total}
    if not data:
        return result, None
    return result, {
        "type": "chart",
        "kind": kind,
        "title": title,
        "labels": [d["label"] for d in data],
        "values": [d["amount"] for d in data],
        "total": total,
    }


def list_expenses(args: dict[str, Any], source: str) -> tuple[Any, Block | None]:
    start, end = _range(args)
    where, params = "date BETWEEN ? AND ?", [start, end]
    if args.get("category"):
        where += " AND category = ?"
        params.append(_category(args["category"]))
    if args.get("search"):
        where += " AND (merchant LIKE ? OR note LIKE ?)"
        params += [f"%{args['search']}%"] * 2
    limit = min(int(args.get("limit") or 20), 100)
    rows = _rows_out(
        connect()
        .execute(
            f"SELECT * FROM expenses WHERE {where} ORDER BY date DESC, id DESC LIMIT ?",
            [*params, limit],
        )
        .fetchall()
    )
    return {"rows": rows}, (
        {"type": "table", "title": f"Expenses · {start} to {end}", "rows": rows}
        if rows
        else None
    )


def edit_expense(args: dict[str, Any], source: str) -> tuple[Any, Block | None]:
    con = connect()
    row = con.execute("SELECT * FROM expenses WHERE id = ?", [args.get("id")]).fetchone()
    if not row:
        return {"error": f"no expense with id {args.get('id')}"}, None
    new = dict(row)
    if "amount" in args and to_cents(args["amount"]) > 0:
        new["cents"] = to_cents(args["amount"])
    if "date" in args:
        new["date"] = _date(args["date"], dt.date.fromisoformat(row["date"]))
    if "category" in args:
        new["category"] = _category(args["category"])
    for f in ("merchant", "note"):
        if f in args:
            new[f] = args[f] or None
    con.execute(
        "UPDATE expenses SET date=?, cents=?, category=?, merchant=?, note=? WHERE id=?",
        (new["date"], new["cents"], new["category"], new["merchant"], new["note"], row["id"]),
    )
    con.commit()
    rows = _rows_out([new])
    return {"updated": rows[0]}, {"type": "table", "title": "Updated", "rows": rows, "changed": True}


def delete_expense(args: dict[str, Any], source: str) -> tuple[Any, Block | None]:
    con = connect()
    row = con.execute("SELECT * FROM expenses WHERE id = ?", [args.get("id")]).fetchone()
    if not row:
        return {"error": f"no expense with id {args.get('id')}"}, None
    con.execute("DELETE FROM expenses WHERE id = ?", [row["id"]])
    con.commit()
    rows = _rows_out([row])
    return {"deleted": rows[0]}, {"type": "table", "title": "Deleted", "rows": rows, "changed": True}


def set_budget(args: dict[str, Any], source: str) -> tuple[Any, Block | None]:
    try:
        cents = to_cents(args["amount"])
    except (KeyError, TypeError, ValueError):
        return {"error": "amount is required"}, None
    if cents <= 0:
        return {"error": "amount must be positive"}, None
    cat = _category(args.get("category"))
    con = connect()
    con.execute(
        "INSERT INTO budgets (category, cents) VALUES (?, ?) ON CONFLICT(category) DO UPDATE SET cents = excluded.cents",
        (cat, cents),
    )
    con.commit()
    return budget_status({}, source)


def budget_status(args: dict[str, Any], source: str) -> tuple[Any, Block | None]:
    month = str(args.get("month") or today().isoformat()[:7])[:7]
    rows = connect().execute(
        """SELECT b.category, b.cents AS budget,
                  COALESCE((SELECT SUM(cents) FROM expenses e
                            WHERE e.category = b.category AND substr(e.date, 1, 7) = ?), 0) AS spent
           FROM budgets b ORDER BY b.category""",
        [month],
    ).fetchall()
    data = [
        {
            "category": r["category"],
            "budget": to_pesos(r["budget"]),
            "spent": to_pesos(r["spent"]),
            "left": to_pesos(r["budget"] - r["spent"]),
        }
        for r in rows
    ]
    if not data:
        return {"month": month, "budgets": [], "note": "no budgets set"}, None
    return {"month": month, "budgets": data}, {
        "type": "budget",
        "title": f"Budgets · {month}",
        "rows": data,
        "changed": True,
    }


def open_ledger(args: dict[str, Any], source: str) -> tuple[Any, Block | None]:
    view = {k: args[k] for k in ("category", "start", "end", "search") if args.get(k)}
    if "category" in view:
        view["category"] = _category(view["category"])
    return {"opened": view or "all"}, {"type": "view", "filter": view}


RUN = {
    f.__name__: f
    for f in (
        add_expenses,
        query_spending,
        list_expenses,
        edit_expense,
        delete_expense,
        set_budget,
        budget_status,
        open_ledger,
    )
}

_date_prop = {"type": "string", "description": "YYYY-MM-DD"}
_cat_prop = {"type": "string", "enum": CATEGORIES}


def _fn(name: str, desc: str, props: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": desc,
            "parameters": {"type": "object", "properties": props, "required": required or []},
        },
    }


SCHEMAS = [
    _fn(
        "add_expenses",
        "Log one or more expenses the user spent. Use for anything they bought or paid, from speech, chat, receipt photos or statements.",
        {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "amount": {"type": "number", "description": "Pesos, positive"},
                        "category": _cat_prop,
                        "date": {"type": "string", "description": '"today", "yesterday", or YYYY-MM-DD'},
                        "merchant": {"type": "string"},
                        "note": {"type": "string", "description": "What it was, short"},
                    },
                    "required": ["amount", "category"],
                },
            }
        },
        ["items"],
    ),
    _fn(
        "query_spending",
        "Total spending grouped for a date range; the app draws a chart from the result. Use for any question about how much, where money went, trends, comparisons.",
        {
            "start": _date_prop,
            "end": _date_prop,
            "group_by": {"type": "string", "enum": list(GROUPS)},
            "category": _cat_prop,
        },
        ["start", "end", "group_by"],
    ),
    _fn(
        "list_expenses",
        "List individual expenses (with their ids) for a date range, optionally filtered. Use before editing or deleting, or when the user wants to see entries.",
        {
            "start": _date_prop,
            "end": _date_prop,
            "category": _cat_prop,
            "search": {"type": "string", "description": "Matches merchant or note"},
            "limit": {"type": "integer"},
        },
        ["start", "end"],
    ),
    _fn(
        "edit_expense",
        "Change fields of one expense by id.",
        {
            "id": {"type": "integer"},
            "amount": {"type": "number"},
            "category": _cat_prop,
            "date": _date_prop,
            "merchant": {"type": "string"},
            "note": {"type": "string"},
        },
        ["id"],
    ),
    _fn("delete_expense", "Delete one expense by id.", {"id": {"type": "integer"}}, ["id"]),
    _fn(
        "set_budget",
        "Set the monthly budget for a category.",
        {"category": _cat_prop, "amount": {"type": "number", "description": "Pesos per month"}},
        ["category", "amount"],
    ),
    _fn(
        "budget_status",
        "Budget vs spent per category for a month.",
        {"month": {"type": "string", "description": "YYYY-MM"}},
    ),
    _fn(
        "open_ledger",
        "Open the ledger panel in the app, filtered. Use when the user asks to open, go to or show the ledger/list.",
        {"category": _cat_prop, "start": _date_prop, "end": _date_prop, "search": {"type": "string"}},
    ),
]
