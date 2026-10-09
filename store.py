"""Store tools: sales, inventory and insights. Every number shown comes from SQL here, never from the model."""

import datetime as dt
from typing import Any

from db import connect, to_cents, to_pesos
from tools import Block, _date, _fn, today

CATEGORIES = ["Noodles & Canned", "Drinks", "Coffee & Milk", "Snacks", "Rice & Basics", "Condiments", "Toiletries", "Household", "Others"]


def _category(s: Any) -> str:
    s = str(s or "").strip().lower()
    return next((c for c in CATEGORIES if c.lower() == s), "Others")


def _find(con: Any, name: Any) -> Any:
    name = str(name or "").strip()
    if not name:
        return None
    row = con.execute("SELECT * FROM products WHERE name = ?", (name,)).fetchone()
    if row:
        return row
    rows = con.execute("SELECT * FROM products WHERE name LIKE ? ORDER BY length(name)", (f"%{name}%",)).fetchall()
    if len(rows) == 1:
        return rows[0]
    # every word of the spoken name appears in the product name ("canton" -> "Lucky Me Pancit Canton")
    words = [w for w in name.lower().split() if len(w) > 2]
    hits = [r for r in con.execute("SELECT * FROM products").fetchall() if words and all(w in r["name"].lower() for w in words)]
    return hits[0] if len(hits) == 1 else None


def product_names() -> list[str]:
    return [r[0] for r in connect().execute("SELECT name FROM products ORDER BY name")]


def _low(con: Any) -> list[dict[str, Any]]:
    rows = con.execute("SELECT name, stock, reorder_at, unit FROM products WHERE reorder_at > 0 AND stock <= reorder_at ORDER BY stock").fetchall()
    return [dict(r) for r in rows]


def record_sales(args: dict[str, Any], source: str) -> tuple[Any, Block | None]:
    con = connect()
    day = _date(args.get("date"))
    sold, problems = [], []
    for it in args.get("items") or []:
        try:
            qty = int(it.get("qty") or 1)
        except (TypeError, ValueError):
            qty = 1
        if qty <= 0:
            continue
        p = _find(con, it.get("product"))
        if p is None:
            if it.get("price"):
                cur = con.execute(
                    "INSERT INTO products (name, price_cents, category) VALUES (?, ?, ?)",
                    (str(it["product"]).strip().title(), to_cents(it["price"]), _category(it.get("category"))),
                )
                p = con.execute("SELECT * FROM products WHERE id = ?", (cur.lastrowid,)).fetchone()
            else:
                problems.append(f"'{it.get('product')}' is not in the product list; ask the user for its price")
                continue
        price = to_cents(it["price"]) if it.get("price") else p["price_cents"]
        con.execute(
            "INSERT INTO sales (date, product_id, qty, price_cents, cost_cents, source) VALUES (?,?,?,?,?,?)",
            (day, p["id"], qty, price, p["cost_cents"], source),
        )
        # Made-fresh items (pandesal, yelo) have reorder_at 0 and no stock count.
        con.execute("UPDATE products SET stock = MAX(stock - ?, 0) WHERE id = ? AND reorder_at > 0", (qty, p["id"]))
        sold.append({"product": p["name"], "qty": qty, "price": to_pesos(price), "total": to_pesos(price * qty)})
    con.commit()
    if not sold:
        return {"error": "; ".join(problems) or "nothing recorded"}, None
    names = {s["product"] for s in sold}
    low = [x for x in _low(con) if x["name"] in names]
    total = round(sum(s["total"] for s in sold), 2)
    result = {"sold": sold, "total": total, "now_low_on_stock": low, "problems": problems}
    return result, {"type": "sale", "title": f"Sold · {day}", "rows": sold, "total": total, "low": low, "changed": True}


def restock(args: dict[str, Any], source: str) -> tuple[Any, Block | None]:
    con = connect()
    day = _date(args.get("date"))
    done = []
    for it in args.get("items") or []:
        try:
            qty = int(it.get("qty") or 0)
        except (TypeError, ValueError):
            continue
        if qty <= 0:
            continue
        p = _find(con, it.get("product"))
        cost = to_cents(it["cost"]) if it.get("cost") else None
        if p is None:
            price = to_cents(it["price"]) if it.get("price") else round((cost or 0) * 1.15)
            cur = con.execute(
                "INSERT INTO products (name, price_cents, cost_cents, category) VALUES (?, ?, ?, ?)",
                (str(it.get("product") or "Item").strip().title(), price, cost or 0, _category(it.get("category"))),
            )
            p = con.execute("SELECT * FROM products WHERE id = ?", (cur.lastrowid,)).fetchone()
        con.execute(
            "UPDATE products SET stock = stock + ?, cost_cents = COALESCE(?, cost_cents) WHERE id = ?",
            (qty, cost, p["id"]),
        )
        con.execute(
            "INSERT INTO restocks (date, product_id, qty, cost_cents, supplier) VALUES (?,?,?,?,?)",
            (day, p["id"], qty, cost if cost is not None else p["cost_cents"], it.get("supplier")),
        )
        stock = con.execute("SELECT stock FROM products WHERE id = ?", (p["id"],)).fetchone()[0]
        done.append({"product": p["name"], "qty": qty, "stock": stock})
    con.commit()
    if not done:
        return {"error": "nothing restocked: every item needs a product and a positive qty"}, None
    return {"restocked": done}, {"type": "stock", "title": "Restocked", "rows": done, "changed": True}


def update_product(args: dict[str, Any], source: str) -> tuple[Any, Block | None]:
    con = connect()
    p = _find(con, args.get("product"))
    if p is None:
        return {"error": f"no product named {args.get('product')!r}", "products": product_names()}, None
    fields, vals = [], []
    for key, col, conv in (("price", "price_cents", to_cents), ("cost", "cost_cents", to_cents), ("reorder_at", "reorder_at", int), ("stock", "stock", int)):
        if args.get(key) is not None:
            fields.append(f"{col} = ?")
            vals.append(conv(args[key]))
    if args.get("category"):
        fields.append("category = ?")
        vals.append(_category(args["category"]))
    if not fields:
        return {"error": "nothing to change"}, None
    con.execute(f"UPDATE products SET {', '.join(fields)} WHERE id = ?", [*vals, p["id"]])
    con.commit()
    r = con.execute("SELECT name, stock, reorder_at, unit, price_cents, cost_cents FROM products WHERE id = ?", (p["id"],)).fetchone()
    row = {"product": r["name"], "stock": r["stock"], "price": to_pesos(r["price_cents"]), "cost": to_pesos(r["cost_cents"])}
    return {"updated": row}, {"type": "stock", "title": "Updated", "rows": [row], "changed": True}


def stock_status(args: dict[str, Any], source: str) -> tuple[Any, Block | None]:
    con = connect()
    where = "WHERE reorder_at > 0 AND stock <= reorder_at" if args.get("only_low") else "WHERE reorder_at > 0"
    rows = [
        {"product": r["name"], "stock": r["stock"], "reorder_at": r["reorder_at"], "unit": r["unit"], "category": r["category"]}
        for r in con.execute(f"SELECT * FROM products {where} ORDER BY stock - reorder_at, name").fetchall()
    ]
    title = "Low on stock" if args.get("only_low") else "Stock on hand"
    return {"products": rows}, ({"type": "stock", "title": title, "rows": rows[:40]} if rows else None)


METRICS = {
    "revenue": ("SUM(s.qty * s.price_cents)", "peso"),
    "profit": ("SUM(s.qty * (s.price_cents - s.cost_cents))", "peso"),
    "qty": ("SUM(s.qty)", "qty"),
}
GROUPS = {
    "day": ("s.date", "line"),
    "week": ("strftime('%Y-W%W', s.date)", "bar"),
    "month": ("substr(s.date, 1, 7)", "bar"),
    "product": ("p.name", "hbar"),
    "category": ("p.category", "doughnut"),
}


def sales_report(args: dict[str, Any], source: str) -> tuple[Any, Block | None]:
    end = _date(args.get("end"))
    start = _date(args.get("start"), dt.date.fromisoformat(end) - dt.timedelta(days=6))
    if start > end:
        start, end = end, start
    metric = args.get("metric") if args.get("metric") in METRICS else "revenue"
    key = args.get("group_by") if args.get("group_by") in GROUPS else "day"
    agg, fmt = METRICS[metric]
    expr, kind = GROUPS[key]
    where, params = "s.date BETWEEN ? AND ?", [start, end]
    if args.get("product"):
        con = connect()
        p = _find(con, args["product"])
        if p:
            where += " AND s.product_id = ?"
            params.append(p["id"])
    if args.get("category"):
        where += " AND p.category = ?"
        params.append(_category(args["category"]))
    order = "1" if key in ("day", "week", "month") else "2 DESC"
    limit = int(args.get("limit") or (10 if key == "product" else 60))
    rows = connect().execute(
        f"SELECT {expr} AS label, {agg} AS v FROM sales s JOIN products p ON p.id = s.product_id WHERE {where} GROUP BY 1 ORDER BY {order} LIMIT ?",
        [*params, limit],
    ).fetchall()
    conv = to_pesos if fmt == "peso" else int
    data = [{"label": r["label"], "value": conv(r["v"])} for r in rows]
    if key == "day":  # give the model real weekday names so it never guesses them
        for x in data:
            x["weekday"] = dt.date.fromisoformat(x["label"]).strftime("%a")
    total = round(sum(d["value"] for d in data), 2)
    title = f"{metric.capitalize()} by {key} · {start} to {end}"
    result = {"start": start, "end": end, "metric": metric, "group_by": key, "rows": data, "total": total}
    if not data:
        return result, None
    return result, {"type": "chart", "kind": kind, "fmt": fmt, "title": title, "labels": [d["label"] for d in data], "values": [d["value"] for d in data], "total": total}


def _sum(con: Any, agg: str, start: str, end: str) -> int:
    return con.execute(f"SELECT COALESCE({agg}, 0) FROM sales s WHERE s.date BETWEEN ? AND ?", (start, end)).fetchone()[0]


def business_snapshot(args: dict[str, Any], source: str) -> tuple[Any, Block | None]:
    con = connect()
    t = today()
    iso = lambda d: d.isoformat()  # noqa: E731
    rev, prof = METRICS["revenue"][0], METRICS["profit"][0]
    today_rev = _sum(con, rev, iso(t), iso(t))
    yday_rev = _sum(con, rev, iso(t - dt.timedelta(1)), iso(t - dt.timedelta(1)))
    # Compare full days only: today is still in progress.
    wk_rev = _sum(con, rev, iso(t - dt.timedelta(7)), iso(t - dt.timedelta(1)))
    prev_rev = _sum(con, rev, iso(t - dt.timedelta(14)), iso(t - dt.timedelta(8)))
    wk_prof = _sum(con, prof, iso(t - dt.timedelta(7)), iso(t - dt.timedelta(1)))
    best = con.execute(
        "SELECT p.name, SUM(s.qty * s.price_cents) v FROM sales s JOIN products p ON p.id = s.product_id WHERE s.date >= ? GROUP BY 1 ORDER BY 2 DESC LIMIT 3",
        (iso(t - dt.timedelta(6)),),
    ).fetchall()
    slow = [
        r[0]
        for r in con.execute(
            "SELECT name FROM products p WHERE (stock > 0 OR reorder_at = 0) AND NOT EXISTS (SELECT 1 FROM sales s WHERE s.product_id = p.id AND s.date >= ?) ORDER BY name",
            (iso(t - dt.timedelta(13)),),
        )
    ]
    change = round((wk_rev - prev_rev) / prev_rev * 100) if prev_rev else None
    kpis = {
        "today_sales": to_pesos(today_rev),
        "yesterday_sales": to_pesos(yday_rev),
        "last_7_full_days_sales": to_pesos(wk_rev),
        "vs_previous_7_days_pct": change,
        "last_7_full_days_profit": to_pesos(wk_prof),
        "best_sellers_7d": [{"product": b[0], "sales": to_pesos(b[1])} for b in best],
        "low_stock": _low(con),
        "not_selling_14d": slow,
    }
    return kpis, {"type": "kpis", "title": "Your store at a glance", **kpis}


def list_sales(args: dict[str, Any], source: str) -> tuple[Any, Block | None]:
    day = _date(args.get("date"))
    where, params = "s.date = ?", [day]
    if args.get("product"):
        where += " AND p.name LIKE ?"
        params.append(f"%{args['product']}%")
    rows = [
        {"id": r["id"], "product": r["name"], "qty": r["qty"], "price": to_pesos(r["price_cents"]), "total": to_pesos(r["qty"] * r["price_cents"])}
        for r in connect().execute(
            f"SELECT s.id, p.name, s.qty, s.price_cents FROM sales s JOIN products p ON p.id = s.product_id WHERE {where} ORDER BY s.id DESC LIMIT 50",
            params,
        )
    ]
    return {"date": day, "sales": rows}, ({"type": "sale", "title": f"Sales · {day}", "rows": rows, "total": round(sum(r["total"] for r in rows), 2)} if rows else None)


def delete_sale(args: dict[str, Any], source: str) -> tuple[Any, Block | None]:
    con = connect()
    r = con.execute("SELECT s.*, p.name FROM sales s JOIN products p ON p.id = s.product_id WHERE s.id = ?", (args.get("id"),)).fetchone()
    if not r:
        return {"error": f"no sale with id {args.get('id')}"}, None
    con.execute("DELETE FROM sales WHERE id = ?", (r["id"],))
    con.execute("UPDATE products SET stock = stock + ? WHERE id = ?", (r["qty"], r["product_id"]))
    con.commit()
    row = {"product": r["name"], "qty": r["qty"], "price": to_pesos(r["price_cents"]), "total": to_pesos(r["qty"] * r["price_cents"])}
    return {"deleted": row}, {"type": "sale", "title": "Removed sale", "rows": [row], "total": row["total"], "changed": True}


def open_view(args: dict[str, Any], source: str) -> tuple[Any, Block | None]:
    panel = args.get("panel") if args.get("panel") in ("sales", "stock") else "sales"
    return {"opened": panel}, {"type": "view", "panel": panel}


RUN = {
    f.__name__: f
    for f in (record_sales, restock, update_product, stock_status, sales_report, business_snapshot, list_sales, delete_sale, open_view)
}
MUTATIONS = {"record_sales", "restock", "update_product", "delete_sale", "open_view"}

_date_prop = {"type": "string", "description": '"today", "yesterday", or YYYY-MM-DD'}
SCHEMAS = [
    _fn(
        "record_sales",
        "Record items the store SOLD to customers (e.g. '2 Coke Mismo, 1 Lucky Me', 'nakabenta ako ng 3 Kopiko').",
        {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "product": {"type": "string", "description": "Product name from the product list"},
                        "qty": {"type": "integer"},
                        "price": {"type": "number", "description": "Unit price in pesos; only if the user said a different price or it's a new product"},
                    },
                    "required": ["product", "qty"],
                },
            },
            "date": _date_prop,
        },
        ["items"],
    ),
    _fn(
        "restock",
        "Record stock the store RECEIVED or BOUGHT from a supplier/grocery (e.g. 'dumating 2 boxes ng Coke, 24 each', a supplier receipt photo).",
        {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "product": {"type": "string"},
                        "qty": {"type": "integer", "description": "Number of pieces (multiply boxes x pieces per box)"},
                        "cost": {"type": "number", "description": "Cost per piece in pesos, if known"},
                        "price": {"type": "number", "description": "Selling price per piece, only for a new product"},
                        "supplier": {"type": "string"},
                    },
                    "required": ["product", "qty"],
                },
            },
            "date": _date_prop,
        },
        ["items"],
    ),
    _fn(
        "update_product",
        "Change a product's selling price, cost, reorder level, category, or correct its stock count after a physical count.",
        {
            "product": {"type": "string"},
            "price": {"type": "number"},
            "cost": {"type": "number"},
            "reorder_at": {"type": "integer"},
            "stock": {"type": "integer", "description": "Actual counted stock"},
            "category": {"type": "string", "enum": CATEGORIES},
        },
        ["product"],
    ),
    _fn("stock_status", "Stock on hand for every product, or only those low on stock.", {"only_low": {"type": "boolean"}}),
    _fn(
        "sales_report",
        "Sales, profit or quantity sold over a date range, grouped by day/week/month/product/category. The app draws the chart. Use for any question about how much was sold, earned, best sellers, trends.",
        {
            "start": {"type": "string", "description": "YYYY-MM-DD"},
            "end": {"type": "string", "description": "YYYY-MM-DD"},
            "group_by": {"type": "string", "enum": list(GROUPS)},
            "metric": {"type": "string", "enum": list(METRICS)},
            "product": {"type": "string"},
            "category": {"type": "string", "enum": CATEGORIES},
            "limit": {"type": "integer"},
        },
        ["start", "end", "group_by", "metric"],
    ),
    _fn(
        "business_snapshot",
        "Today vs yesterday, last 7 days vs the 7 before, profit, best sellers, low stock and products not selling. Use for 'kumusta ang tindahan', advice, insights, what to restock.",
        {},
    ),
    _fn("list_sales", "List individual sales with ids for one day. Use before deleting a wrong entry.", {"date": _date_prop, "product": {"type": "string"}}),
    _fn("delete_sale", "Remove a wrongly recorded sale by id (stock is put back).", {"id": {"type": "integer"}}, ["id"]),
    _fn("open_view", "Open the Sales or Stock screen of the app.", {"panel": {"type": "string", "enum": ["sales", "stock"]}}, ["panel"]),
]
