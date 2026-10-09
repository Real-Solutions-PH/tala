"""Tala API: a local agent loop over llama-server, plus whisper-server for voice."""

import base64
import io
import json
import os
from pathlib import Path
from typing import Any

import httpx
import qrcode
import qrcode.image.svg
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pypdf import PdfReader

import store
import tools
import tts

LLM_URL = os.getenv("LLM_URL", "http://127.0.0.1:8080/v1/chat/completions")
WHISPER_URL = os.getenv("WHISPER_URL", "http://127.0.0.1:8081/inference")
MAX_STEPS = 6
RUN = store.RUN
SCHEMAS = store.SCHEMAS

# Phones reach the laptop over LAN; only devices that scanned the pairing QR (which carries this key) get in.
PAIR_KEY = os.getenv("TALA_KEY", "")
PHONE_URL = os.getenv("TALA_PHONE_URL", "")

app = FastAPI(title="Tala")


@app.on_event("startup")
def warm_voice() -> None:
    import threading

    threading.Thread(target=tts.load, daemon=True).start()


@app.middleware("http")
async def paired_only(request: Request, call_next: Any) -> Any:
    host = request.client.host if request.client else ""
    if host in ("127.0.0.1", "::1"):
        return await call_next(request)
    if PAIR_KEY and request.query_params.get("k") == PAIR_KEY:
        response = await call_next(request)
        response.set_cookie("tala_k", PAIR_KEY, httponly=True, secure=True, samesite="strict", max_age=86400 * 30)
        return response
    if not PAIR_KEY or request.cookies.get("tala_k") != PAIR_KEY:
        return JSONResponse({"detail": "Scan the pairing QR code on the laptop to open Tala."}, status_code=403)
    return await call_next(request)


def system_prompt() -> str:
    d = tools.today()
    week = ", ".join(f"{(d - tools.dt.timedelta(days=i)).strftime('%A')} {(d - tools.dt.timedelta(days=i)).isoformat()}" for i in range(1, 7))
    return f"""You are Tala, a friendly store assistant for a small Filipino store (sari-sari store, carinderia, market stall). You run fully offline on the owner's own laptop.
Today is {d.isoformat()} ({d.strftime('%A')}). Past days: {week}. Currency is Philippine pesos (₱).
The owner speaks English, Tagalog or Taglish. Reply in simple, everyday Taglish: mostly plain English sentences with common store words in Tagalog.
Good words: benta (sales), kita (profit), paubos na (running low), ubos na (sold out), i-restock, presyo (price), mabenta (selling well), hindi gumagalaw (not selling), po, salamat.
Do NOT use deep or formal Tagalog, do not translate word by word, and never use words you are unsure of. Never call the owner by a name.

Products in the store: {store.product_names()}
Match what the owner says to these names ("canton" = Lucky Me Pancit Canton, "coke" = Coke Mismo, "kopiko" = Kopiko 3-in-1, "itlog" = Egg). Product categories: {store.CATEGORIES}.

Rules:
- Something was SOLD to a customer ("nakabenta", "bumili si...", "2 coke, 1 canton", "benta") -> record_sales. One item per product with its qty.
- Stock ARRIVED or was BOUGHT from a supplier/grocery ("dumating", "nag-restock", "bumili ako sa Puregold ng 2 box"), or a supplier receipt/delivery photo -> restock. Convert boxes/packs to pieces when the owner says how many per box.
- A photo of a handwritten sales list (listahan) -> record_sales for every line.
- Price changes ("taasan ang Coke to 22"), counted stock corrections, reorder levels -> update_product.
- Questions about sales, kita (profit), best sellers, trends, comparisons -> sales_report (the app draws the chart). Pick group_by and metric to fit the question. Ranges: "this week"/"last 7 days" = {(d - tools.dt.timedelta(days=6)).isoformat()} to today; "this month" = {d.replace(day=1).isoformat()} to today; "today" = today. Best seller means revenue unless the owner asks about pieces.
- "Kumusta ang tindahan?", advice, what to restock, what is not selling -> business_snapshot, then give ONE practical tip from its numbers.
  Tips must make business sense: restock only items that are low AND selling; for items not selling, suggest a promo, a bundle with a best seller, a lower price, or stop reordering them, never restock them.
- Stock questions ("ilan pa ang...", "ano ang paubos na?") -> stock_status.
- Wrong entry -> list_sales then delete_sale.
- If the message is unclear, just noise, or not about the store (e.g. "okay", "sari-sari", a random phrase), do NOT call any tool and do NOT repeat earlier advice; reply only: "Pasensya po, hindi ko narinig nang malinaw. Ano po ulit?"
- Never compute or guess numbers yourself; quote only numbers returned by tools.
- After tools run, answer in ONE or TWO short sentences (max 35 words). The app already shows the chart or table, so do not list every number."""


MUTATIONS = store.MUTATIONS


def tidy(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # A lookup list shown before a delete is noise once the change itself is shown.
    if any(b.get("changed") for b in blocks):
        return [b for b in blocks if b.get("changed") or not b["title"].startswith("Sales ·")]
    return blocks


def quick_reply(blocks: list[dict[str, Any]]) -> str:
    parts = []
    for b in blocks:
        if b["type"] == "sale" and b["title"].startswith("Sold"):
            items = sum(r["qty"] for r in b["rows"])
            parts.append(f"₱{b['total']:,.2f} na benta ({items} item{'s' * (items != 1)})")
            if b.get("low"):
                parts.append("paubos na ang " + ", ".join(f"{x['name']} ({x['stock']} left)" for x in b["low"]))
        elif b["type"] == "stock" and b["title"] == "Restocked":
            parts.append("restocked " + ", ".join(f"{r['product']} +{r['qty']} (now {r['stock']})" for r in b["rows"]))
        elif b["type"] == "stock" and b["title"] == "Updated":
            r = b["rows"][0]
            parts.append(f"{r['product']} is now ₱{r['price']:,.2f}, {r['stock']} in stock")
        elif b["type"] == "view":
            parts.append(f"opened {b['panel']}")
        else:
            parts.append(b["title"][0].lower() + b["title"][1:])
    text = "; ".join(parts)
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
        text = "Record what is in this photo for the store."
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


@app.post("/api/speak")
def speak(text: str = Form(...)) -> Response:
    # Spoken replies in Tagalog, synthesised on this laptop (Meta MMS-TTS).
    return Response(tts.speak(text[:400]), media_type="audio/wav")


@app.get("/api/store")
def store_overview() -> dict[str, Any]:
    kpis, _ = store.business_snapshot({}, "")
    week, _ = store.sales_report({"start": (tools.today() - tools.dt.timedelta(days=13)).isoformat(), "end": tools.today().isoformat(), "group_by": "day", "metric": "revenue"}, "")
    stock, _ = store.stock_status({}, "")
    today_rows, _ = store.list_sales({"date": "today"}, "")
    return {"kpis": kpis, "trend": week["rows"], "stock": stock["products"], "today": today_rows["sales"]}


@app.get("/manifest.webmanifest")
def manifest() -> JSONResponse:
    # Served dynamically: an iOS home-screen app has its own cookie jar, so its start URL carries the pairing key.
    start = f"/?k={PAIR_KEY}" if PAIR_KEY else "/"
    return JSONResponse(
        {
            "name": "Tala",
            "short_name": "Tala",
            "description": "Just say what happened. Tala logs it. Offline.",
            "start_url": start,
            "display": "standalone",
            "background_color": "#f3f5f2",
            "theme_color": "#0a6b3d",
            "icons": [
                {"src": "icon-180.png", "sizes": "180x180", "type": "image/png"},
                {"src": "icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
            ],
        },
        media_type="application/manifest+json",
    )


@app.get("/api/pair")
def pair(request: Request) -> Response:
    if not PHONE_URL or (request.client and request.client.host not in ("127.0.0.1", "::1")):
        raise HTTPException(404, "Phone pairing is off. Start Tala with ./run.sh.")
    svg = qrcode.make(PHONE_URL, image_factory=qrcode.image.svg.SvgPathImage, box_size=12, border=2).to_string().decode()
    return JSONResponse({"url": PHONE_URL.split("?")[0], "link": PHONE_URL, "svg": svg})


app.mount("/", StaticFiles(directory=Path(__file__).with_name("static"), html=True), name="static")
