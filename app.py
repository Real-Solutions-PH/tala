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

import tools
from db import CATEGORIES, connect, to_pesos

LLM_URL = os.getenv("LLM_URL", "http://127.0.0.1:8080/v1/chat/completions")
WHISPER_URL = os.getenv("WHISPER_URL", "http://127.0.0.1:8081/inference")
MAX_STEPS = 6

app = FastAPI(title="Tala")


def system_prompt() -> str:
    d = tools.today()
    return f"""You are Tala, a friendly money companion that runs fully offline on the user's laptop.
Today is {d.isoformat()} ({d.strftime('%A')}). Currency is Philippine pesos (₱).
The user speaks English, Tagalog or Taglish. Reply in the same mix they use, short and warm.

Rules:
- When the user mentions anything they spent or paid (even casually, e.g. "nag-jeep ako 15, lunch 120"), call add_expenses. Split into one item per thing. Infer the category from {CATEGORIES}. Dates like "kahapon" = yesterday, "kanina" = today.
- For a receipt photo: log ONE expense for the receipt's grand total, using the merchant name and the receipt date, unless the user asks for each item.
- For a bank or e-wallet statement: log each debit/payment line as its own expense; skip credits, transfers in and balances.
- For any question about amounts, totals, trends or "where did my money go", call query_spending (the app draws the chart). Never compute or guess totals yourself; quote only numbers returned by tools.
- To edit or delete, call list_expenses first to find the id, then edit_expense / delete_expense.
- After tools run, answer in 1-3 sentences. Do not repeat tables the app already shows."""


async def llm(messages: list[dict[str, Any]]) -> dict[str, Any]:
    body = {"messages": messages, "tools": tools.SCHEMAS, "temperature": 0.2}
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
    for _ in range(MAX_STEPS):
        msg = await llm(messages)
        calls = msg.get("tool_calls") or []
        if not calls:
            return {"reply": (msg.get("content") or "").strip(), "blocks": blocks}
        messages.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls})
        for call in calls:
            name = call["function"]["name"]
            try:
                args = json.loads(call["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            fn = tools.RUN.get(name)
            if fn is None:
                result: Any = {"error": f"unknown tool {name}"}
            else:
                result, block = fn(args, source)
                if block:
                    blocks.append(block)
            messages.append(
                {"role": "tool", "tool_call_id": call.get("id", name), "content": json.dumps(result, default=str)}
            )
    return {"reply": "Done.", "blocks": blocks}


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
    return {"rows": rows, "month": month, "month_total": to_pesos(month_total), "budgets": budgets.get("budgets", [])}


app.mount("/", StaticFiles(directory=Path(__file__).with_name("static"), html=True), name="static")
