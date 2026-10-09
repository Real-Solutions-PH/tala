"""Tala API: a local agent loop over llama-server, plus whisper-server for voice."""

import base64
import io
import json
import os
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from pypdf import PdfReader

import life
import tools
from db import CATEGORIES, connect, to_pesos

LLM_URL = os.getenv("LLM_URL", "http://127.0.0.1:8080/v1/chat/completions")
WHISPER_URL = os.getenv("WHISPER_URL", "http://127.0.0.1:8081/inference")
MAX_STEPS = 6
RUN = {**tools.RUN, **life.RUN}
SCHEMAS = tools.SCHEMAS + life.SCHEMAS

app = FastAPI(title="Tala")


def system_prompt() -> str:
    d = tools.today()
    habits = [r[0] for r in connect().execute("SELECT name FROM habits ORDER BY name")]
    return f"""You are Tala, a friendly personal assistant for money, tasks and habits that runs fully offline on the user's laptop.
Today is {d.isoformat()} ({d.strftime('%A')}). Next 7 days: {", ".join(f"{(d + tools.dt.timedelta(days=i)).strftime('%A')} {(d + tools.dt.timedelta(days=i)).isoformat()}" for i in range(1, 8))}. Currency is Philippine pesos (₱).
The user speaks English, Tagalog or Taglish. Reply in the same mix they use, short and warm.

Rules:
- When the user mentions anything they spent or paid (even casually, e.g. "nag-jeep ako 15, lunch 120"), call add_expenses. Split into one item per thing. Always set "merchant" to the place, app or ride (Jeep, Grab, Jollibee, Meralco). Infer the category from {CATEGORIES} (supermarkets like Puregold or SM Supermarket = Groceries; fuel, jeep, Grab = Transport; ATM withdrawals = Others).
- Dates: set "date" per item. Use "today" unless the user put a day word right before THAT item. A day word applies only to the items that come after it.
  Example: "jeep 15, lunch 165, kahapon grab 230" -> jeep date "today", lunch date "today", grab date "yesterday".
  "kahapon" = "yesterday", "kanina"/"ngayon" = "today"; any other day as YYYY-MM-DD.
- For a receipt photo: log ONE expense for the receipt's grand total, using the merchant name and the receipt date, unless the user asks for each item.
- For a bank or e-wallet statement: log each debit/payment line as its own expense; skip credits, transfers in and balances.
- For any question about amounts, totals, trends or "where did my money go", call query_spending (the app draws the chart). Never compute or guess totals yourself; quote only numbers returned by tools.
  If the user names a category (food, transport, bills...), ALWAYS pass it as "category".
  Default ranges: "this month" = {d.replace(day=1).isoformat()} to today; "per week"/weekly = last 8 weeks; "per day"/daily = last 30 days; "per month"/monthly = last 3 months.
- To edit or delete, call list_expenses first to find the id, then edit_expense / delete_expense.
- Things to do ("remind me to...", "kailangan ko...", "todo") -> add_tasks. "Done na yung..." / "tapos ko na" -> list_tasks then complete_tasks.
- Habits done ("nag-workout ako", "read 20 pages", "8 glasses of water") -> log_habits with a short habit name. Existing habits: {habits or "none yet"}. Reuse one when it means the same thing (gym/exercise/nag-gym = Workout, nagbasa = Read). Questions about streaks/consistency -> habit_summary.
- One message can mix all three (e.g. "lunch 150, nag-gym ako, remind me to pay Meralco") -> call every tool needed.
- After tools run, answer in ONE short sentence (max 30 words) with the single most useful insight. The app already shows the chart or table, so do not list every number."""


# Turns that only change data get a template reply instead of a second model call (saves ~5s).
MUTATIONS = {"add_expenses", "edit_expense", "delete_expense", "set_budget", "open_view", "add_tasks", "complete_tasks", "log_habits"}


def tidy(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # A lookup table shown before an edit/delete is noise once the change itself is shown.
    if any(b.get("changed") for b in blocks):
        return [b for b in blocks if b.get("changed") or b["type"] not in ("table", "tasks")]
    return blocks


def quick_reply(blocks: list[dict[str, Any]]) -> str:
    parts = []
    for b in blocks:
        if b["type"] == "table" and b["title"].startswith("Logged"):
            total = sum(r["amount"] for r in b["rows"])
            parts.append(f"logged {len(b['rows'])} expense{'s' * (len(b['rows']) != 1)} (₱{total:,.2f})")
        elif b["type"] == "view":
            parts.append(f"opened {b['panel']}")
        elif b["type"] == "budget":
            parts.append("budget saved")
        else:
            parts.append(b["title"][0].lower() + b["title"][1:])
    text = ", ".join(parts)
    return f"Got it: {text}." if text else "Done."


async def llm(messages: list[dict[str, Any]]) -> dict[str, Any]:
    body = {"messages": messages, "tools": SCHEMAS, "temperature": 0.2}
    try:
        async with httpx.AsyncClient(timeout=180) as c:
            r = await c.post(LLM_URL, json=body)
            r.raise_for_status()
    except httpx.HTTPError:
        raise HTTPException(503, "The local model is not running. Start it with ./run.sh.")
    msg: dict[str, Any] = r.json()["choices"][0]["message"]
    return msg


def pdf_text(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    # ponytail: first 8 pages only — a statement longer than that overflows a local context window
    return "\n".join((p.extract_text() or "") for p in reader.pages[:8])


@app.post("/api/chat")
async def chat(
    message: str = Form(""),
    history: str = Form("[]"),
    source: str = Form("chat"),
    files: list[UploadFile] = File(default=[]),
) -> dict[str, Any]:
    content: list[dict[str, Any]] = []
    text = message.strip()
    for f in files:
        data = await f.read()
        if (f.content_type or "").startswith("image/"):
            source = "photo"
            url = f"data:{f.content_type};base64,{base64.b64encode(data).decode()}"
            content.append({"type": "image_url", "image_url": {"url": url}})
        elif f.filename and f.filename.lower().endswith(".pdf") or f.content_type == "application/pdf":
            source = "pdf"
            text += f"\n\n[Attached document: {f.filename}]\n{pdf_text(data)[:12000]}"
        else:
            raise HTTPException(415, f"{f.filename}: only images and PDFs are supported")
    if not text and not content:
        raise HTTPException(400, "Say or attach something first.")
    if not text:
        text = "Log this receipt."
    content.insert(0, {"type": "text", "text": text})

    past = [m for m in json.loads(history) if m.get("role") in ("user", "assistant")][-12:]
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt()},
        *[{"role": m["role"], "content": str(m["content"])} for m in past],
        {"role": "user", "content": content},
    ]
    blocks: list[dict[str, Any]] = []
    called: set[str] = set()
    for _ in range(MAX_STEPS):
        msg = await llm(messages)
        calls = msg.get("tool_calls") or []
        if not calls:
            return {"reply": (msg.get("content") or "").strip(), "blocks": tidy(blocks)}
        messages.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls})
        for call in calls:
            name = call["function"]["name"]
            try:
                args = json.loads(call["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            called.add(name)
            fn = RUN.get(name)
            if fn is None:
                result: Any = {"error": f"unknown tool {name}"}
            else:
                result, block = fn(args, source)
                if block:
                    blocks.append(block)
            messages.append(
                {"role": "tool", "tool_call_id": call.get("id", name), "content": json.dumps(result, default=str)}
            )
        if called <= MUTATIONS and blocks:
            return {"reply": quick_reply(blocks), "blocks": tidy(blocks)}
    return {"reply": "Done.", "blocks": tidy(blocks)}


@app.post("/api/transcribe")
async def transcribe(audio: UploadFile = File(...)) -> dict[str, str]:
    data = await audio.read()
    try:
        async with httpx.AsyncClient(timeout=120) as c:
            r = await c.post(
                WHISPER_URL,
                files={"file": (audio.filename or "voice.webm", data, audio.content_type or "audio/webm")},
                data={"response_format": "json", "temperature": "0"},
            )
            r.raise_for_status()
    except httpx.HTTPError:
        raise HTTPException(503, "The local speech model is not running. Start it with ./run.sh.")
    return {"text": str(r.json().get("text", "")).strip()}


@app.get("/api/expenses")
def expenses(category: str = "", start: str = "", end: str = "", search: str = "") -> dict[str, Any]:
    result, _ = tools.list_expenses(
        {"category": category, "start": start or "2000-01-01", "end": end, "search": search, "limit": 100}, ""
    )
    rows = result["rows"]
    month = tools.today().isoformat()[:7]
    month_total = connect().execute(
        "SELECT COALESCE(SUM(cents), 0) FROM expenses WHERE substr(date, 1, 7) = ?", [month]
    ).fetchone()[0]
    budgets, _ = tools.budget_status({}, "")
    tasks, _ = life.list_tasks({"status": "all"}, "")
    habits, _ = life.habit_summary({"days": 30}, "")
    return {
        "rows": rows,
        "month": month,
        "month_total": to_pesos(month_total),
        "budgets": budgets.get("budgets", []),
        "tasks": tasks["tasks"],
        "habits": habits.get("habits", []),
    }


@app.post("/api/tasks/{task_id}/toggle")
def toggle_task(task_id: int) -> dict[str, Any]:
    con = connect()
    con.execute(
        "UPDATE tasks SET done_on = CASE WHEN done_on IS NULL THEN ? ELSE NULL END WHERE id = ?",
        (tools.today().isoformat(), task_id),
    )
    con.commit()
    return {"ok": True}


app.mount("/", StaticFiles(directory=Path(__file__).with_name("static"), html=True), name="static")
