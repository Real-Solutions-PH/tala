"""Server-owned conversations and messages. The client only ever sends the new message plus the id."""

import json
import re
import sqlite3
import uuid
from datetime import date

TITLE_MAX = 60
# Copies of i18n chat.usapTitle and chat.newChat (frontend/src/i18n/{en,tl}.ts); titles are stored text.
_USAP_TITLE = {"en": "Talk on {date}", "tl": "Usap noong {date}"}
_NEW_CHAT = {"en": "New chat", "tl": "Bagong usapan"}
_SENTENCE_END = re.compile(r"[.?!](?=\s|$)")
_JSON_FIELDS = ("blocks", "steps", "sources", "attachments")


def make_title(first_text: str, *, mode: str = "text", lang: str = "tl", today: str | None = None) -> str:
    """VCAC-C-10: the first user text cut at its first sentence end or 60 characters. Usap sessions are
    titled by date."""
    lang = lang if lang in _NEW_CHAT else "tl"
    if mode == "usap":
        return _USAP_TITLE[lang].format(date=today or date.today().isoformat())
    text = " ".join(first_text.split())
    if not text:
        return _NEW_CHAT[lang]
    m = _SENTENCE_END.search(text)
    if m:
        text = text[: m.end()]
    return text[:TITLE_MAX].rstrip()


def create(con: sqlite3.Connection, pid: int, first_text: str, *, mode: str = "text", lang: str = "tl",
           today: str | None = None) -> str:
    cid = uuid.uuid4().hex
    con.execute("insert into conversations (id, profile_id, title) values (?,?,?)",
                (cid, pid, make_title(first_text, mode=mode, lang=lang, today=today)))
    con.commit()
    return cid


def append(con: sqlite3.Connection, cid: str, role: str, content: str, *, id: str | None = None,
           mode: str = "text", status: str = "complete", blocks: list | None = None, steps: list | None = None,
           sources: list | None = None, attachments: list | None = None) -> str:
    mid = id or uuid.uuid4().hex
    con.execute(
        "insert into messages (id, conversation_id, role, content, mode, status, blocks, steps, sources, attachments)"
        " values (?,?,?,?,?,?,?,?,?,?)",
        (mid, cid, role, content, mode, status, json.dumps(blocks or []), json.dumps(steps or []),
         json.dumps(sources or []), json.dumps(attachments or [])))
    con.execute("update conversations set updated=datetime('now') where id=?", (cid,))
    con.commit()
    return mid


def owner(con: sqlite3.Connection, cid: str) -> int | None:
    row = con.execute("select profile_id from conversations where id=?", (cid,)).fetchone()
    return None if row is None else row[0]


def history(con: sqlite3.Connection, cid: str, limit: int = 12) -> list[dict]:
    """The last `limit` messages, oldest first, for the agent. Includes the user message of the current run,
    which is saved before the agent starts."""
    rows = con.execute("select role, content from messages where conversation_id=? order by rowid desc limit ?",
                       (cid, limit)).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def list_for(con: sqlite3.Connection, pid: int) -> list[dict]:
    rows = con.execute("select id, title, updated from conversations where profile_id=? order by updated desc, rowid desc",
                       (pid,))
    return [dict(r) for r in rows]


def get(con: sqlite3.Connection, cid: str) -> dict | None:
    conv = con.execute("select id, title, profile_id from conversations where id=?", (cid,)).fetchone()
    if conv is None:
        return None
    messages = []
    for r in con.execute("select id, role, content, mode, status, blocks, steps, sources, attachments, created"
                         " from messages where conversation_id=? order by rowid", (cid,)):
        m = dict(r)
        for f in _JSON_FIELDS:
            m[f] = json.loads(m[f])
        messages.append(m)
    return {"id": conv["id"], "title": conv["title"], "profile_id": conv["profile_id"], "messages": messages}


def rename(con: sqlite3.Connection, cid: str, title: str) -> None:
    con.execute("update conversations set title=? where id=?", (title, cid))
    con.commit()


def delete(con: sqlite3.Connection, cid: str) -> None:
    con.execute("delete from conversations where id=?", (cid,))  # messages cascade
    con.commit()
