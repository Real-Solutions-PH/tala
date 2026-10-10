"""Kapiling API: local-first personal health record."""

import asyncio
import logging
import os
import re
import threading
from contextlib import asynccontextmanager, suppress
from typing import Any

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from kapiling import config
from kapiling.auth.routes import router as auth_router
from kapiling.docs.ingest import run_pending
from kapiling.docs.routes import router as docs_router
from kapiling.records.routes import router as records_router
from kapiling.voice import tts

STATIC_DIR = config.ROOT / "static"
log = logging.getLogger("kapiling")
COOKIE = "kapiling_k"
# The only API paths a non-paired LAN client may reach. Everything else needs the pairing cookie.
OPEN_PATHS = re.compile(
    r"/api/health|/api/profiles|/api/unlock"
    r"|/api/profiles/[0-9]+/photo"
    r"|/api/emergency/[0-9]+(?:/qr\.svg)?"
)

worker_task: asyncio.Task | None = None
# Load both MMS-TTS voices at startup so the first spoken reply is not slow. Tests set KAPILING_TTS_WARM=0,
# like KAPILING_WORKER for the ingestion worker.
TTS_WARM = os.getenv("KAPILING_TTS_WARM", "1") == "1"
# Prime llama-server's prompt cache with the real system prompt and tool schemas (one max_tokens=1 request), so the
# first question after startup is not slow. Tests set KAPILING_LLM_WARM=0.
LLM_WARM = os.getenv("KAPILING_LLM_WARM", "1") == "1"


def _warm_tts() -> None:
    for lang in ("tl", "en"):
        try:
            tts.load(lang)
        except Exception as e:  # noqa: BLE001 - a missing model only means a slower first reply
            log.warning("tts warm-up for %s failed: %s", lang, type(e).__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Start the ingestion worker as a detached task with its own connection (G-C-015), and warm up TTS."""
    global worker_task
    if TTS_WARM:
        threading.Thread(target=_warm_tts, name="tts-warmup", daemon=True).start()
    llm_warm = None
    if LLM_WARM:  # detached: never blocks startup, and warm_prompt_cache never raises
        from kapiling.chat import agent

        llm_warm = asyncio.create_task(agent.warm_prompt_cache())
    if config.settings.worker:
        worker_task = asyncio.create_task(run_pending())
    try:
        yield
    finally:
        if llm_warm is not None and not llm_warm.done():
            llm_warm.cancel()
        if worker_task is not None:
            worker_task.cancel()
            with suppress(asyncio.CancelledError):
                await worker_task
            worker_task = None


app = FastAPI(title="Kapiling", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(records_router)
app.include_router(docs_router)


def is_open(path: str) -> bool:
    return OPEN_PATHS.fullmatch(path) is not None


@app.middleware("http")
async def paired_only(request: Request, call_next: Any) -> Any:
    host = request.client.host if request.client else ""
    if host in ("127.0.0.1", "::1") or is_open(request.url.path):
        return await call_next(request)
    key = config.settings.pair_key
    if key and request.query_params.get("k") == key:
        response = await call_next(request)
        response.set_cookie(COOKIE, key, httponly=True, secure=True, samesite="strict", max_age=86400 * 30)
        return response
    if not key or request.cookies.get(COOKIE) != key:
        return JSONResponse({"detail": "Scan the pairing QR code on the laptop to open Kapiling."}, status_code=403)
    return await call_next(request)


async def probe(client: httpx.AsyncClient, url: str, any_response: bool = False) -> bool:
    try:
        r = await client.get(url)
    except Exception:
        return False
    return r.status_code < 500 if any_response else r.is_success


@app.get("/api/health")
async def health() -> dict[str, bool]:
    s = config.settings
    async with httpx.AsyncClient(timeout=1.0) as client:
        return {
            "llm": await probe(client, f"{s.llm_url}/health"),
            "embed": await probe(client, f"{s.embed_url}/health"),
            "rerank": await probe(client, f"{s.rerank_url}/health"),
            # whisper-server has no /health: any 2xx/4xx answer means it is up.
            "whisper": await probe(client, f"{s.whisper_url}/", any_response=True),
            "tts": tts.is_loaded() or tts.models_cached(),
        }


from kapiling.chat.routes import router as chat_router  # noqa: E402  (Task 8)

app.include_router(chat_router)

from kapiling.spa import spa  # noqa: E402  (Task 11: deep links and reloads serve index.html)

if STATIC_DIR.is_dir():
    app.mount("/", spa(STATIC_DIR), name="static")
