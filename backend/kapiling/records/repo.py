import json
import sqlite3
from datetime import datetime

Row = sqlite3.Row


def get_profile(con, pid: int) -> Row | None:
    return con.execute("select * from profiles where id=?", (pid,)).fetchone()


def list_meds(con, pid: int, active: bool = True) -> list[Row]:
    sql = "select * from medications where profile_id=?" + (" and active=1" if active else "") + " order by id"
    return con.execute(sql, (pid,)).fetchall()


def meds_today(con, pid: int, date: str) -> list[dict]:
    out = []
    for m in list_meds(con, pid):
        if (m["start_date"] and m["start_date"] > date) or (m["end_date"] and m["end_date"] < date):
            continue
        logs = {r["slot"]: r["taken_at"] for r in con.execute(
            "select slot, taken_at from med_logs where med_id=? and date=?", (m["id"], date))}
        for slot in sorted(json.loads(m["schedule"] or "[]")):
            out.append({"med_id": m["id"], "name": m["name"], "strength": m["strength"], "slot": slot,
                        "taken_at": logs.get(slot)})
    return sorted(out, key=lambda t: (t["slot"], t["name"]))


def mark_taken(con, mid: int, date: str, slot: str) -> None:
    con.execute("insert or ignore into med_logs (med_id, date, slot, taken_at) values (?,?,?,?)",
                (mid, date, slot, datetime.now().isoformat(timespec="seconds")))
    con.commit()


def unmark_taken(con, mid: int, date: str, slot: str) -> None:
    con.execute("delete from med_logs where med_id=? and date=? and slot=?", (mid, date, slot))
    con.commit()


def list_cards(con, pid: int) -> list[Row]:
    return con.execute("select * from cards where profile_id=? order by sort, id", (pid,)).fetchall()


def list_vaccines(con, pid: int) -> list[Row]:
    return con.execute("select * from vaccines where profile_id=? order by coalesce(date, next_due), id", (pid,)).fetchall()


def list_conditions(con, pid: int) -> list[Row]:
    return con.execute("select * from conditions where profile_id=? and status='active' order by id", (pid,)).fetchall()


def list_allergies(con, pid: int) -> list[Row]:
    return con.execute("select * from allergies where profile_id=? order by id", (pid,)).fetchall()


def list_contacts(con, pid: int) -> list[Row]:
    return con.execute("select * from contacts where profile_id=? order by id", (pid,)).fetchall()


def observations(con, pid: int, code: str | None = None, status: str = "confirmed") -> list[Row]:
    sql, args = "select * from observations where profile_id=? and status=?", [pid, status]
    if code:
        sql += " and code=?"
        args.append(code)
    return con.execute(sql + " order by date, id", args).fetchall()


def latest_observations(con, pid: int) -> dict[str, Row]:
    latest: dict[str, Row] = {}
    for o in observations(con, pid):  # ordered oldest first, so later rows win
        latest[o["code"]] = o
    return latest


def timeline(con, pid: int, kind: str | None = None) -> list[dict]:
    items = [{"kind": "visit", "date": r["date"], "title": r["reason"] or r["facility"] or "Visit", "ref_id": r["id"]}
             for r in con.execute("select * from visits where profile_id=?", (pid,))]
    items += [{"kind": "vaccine", "date": r["date"], "title": f"{r['name']} {r['dose'] or ''}".strip(), "ref_id": r["id"]}
              for r in con.execute("select * from vaccines where profile_id=? and date is not null", (pid,))]
    items += [{"kind": "lab" if r["kind"] == "lab" else "document", "date": r["date"] or r["created"][:10],
               "title": r["title"], "ref_id": r["id"]}
              for r in con.execute("select * from documents where profile_id=?", (pid,))]
    if kind:
        items = [i for i in items if i["kind"] == kind]
    return sorted(items, key=lambda i: (i["date"], i["ref_id"]), reverse=True)
