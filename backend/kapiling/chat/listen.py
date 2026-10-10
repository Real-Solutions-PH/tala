"""Usap and listen-in helpers (Task 18).

`about_record` is the listen-in gate: one fast LLM call that decides whether an overheard utterance is
about the patient's own record. `prelude` is the voice front of a run: it transcribes the uploaded audio
(then forgets it), emits the transcript, and in listen mode applies the gate. The agent calls it before
its main loop.
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

from kapiling import config
from kapiling.chat import agui
from kapiling.voice import stt

log = logging.getLogger(__name__)

TIMEOUT = 4.0
SCHEMA = {
    "type": "object",
    "properties": {"about_record": {"type": "boolean"}},
    "required": ["about_record"],
    "additionalProperties": False,
}
PROMPT = {
    "en": ("You overhear part of a doctor's consultation. Answer about_record=true only if this is a question "
           "or remark that the patient's own health record (medicines, lab results, history, allergies, "
           "visits) could help answer. Otherwise false."),
    "tl": ("Naririnig mo ang bahagi ng konsulta sa doktor. Sagutin ng about_record=true kung ang sinabi ay "
           "tanong o pahayag na masasagot ng sariling health record ng pasyente (gamot, lab, kasaysayan, "
           "allergy, pagbisita). Kung hindi, false."),
}


async def _post(url: str, payload: dict, timeout: float) -> dict:
    """The one seam for the model call (tests substitute it)."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, json=payload)
        r.raise_for_status()
        return r.json()


async def about_record(text: str, lang: str) -> bool:
    """True when the overheard text concerns the record. Any error, timeout or odd answer gives False:
    in listen mode, staying quiet is the safe failure."""
    if not text.strip():
        return False
    payload = {
        "temperature": 0,
        "max_tokens": 8,
        "messages": [
            {"role": "system", "content": PROMPT.get(lang, PROMPT["tl"])},
            {"role": "user", "content": text},
        ],
        "response_format": {"type": "json_schema", "json_schema": {"name": "listen_gate", "schema": SCHEMA}},
    }
    try:
        body = await _post(f"{config.settings.llm_url}/v1/chat/completions", payload, TIMEOUT)
        raw = json.loads(body["choices"][0]["message"]["content"] or "")
        return isinstance(raw, dict) and raw.get("about_record") is True
    except asyncio.CancelledError:
        raise
    except Exception as e:  # noqa: BLE001 - the gate never breaks a run
        log.warning("listen gate failed: %s", type(e).__name__)
        return False


async def prelude(ctx: Any) -> AsyncIterator[dict]:
    """Voice front of a run. Mutates ctx: sets `user_text` from the transcript, drops `audio`, and sets
    `gated_out=True` when a listen-mode utterance is not about the record (the agent must then stop
    with no text and no audio). Stamps `speech_end` (if the route did not), `stt_done`, `gate_done`."""
    timer = getattr(ctx, "timer", None)
    stamp = timer.stamp if timer is not None else (lambda _n: None)
    ctx.gated_out = False
    voiced = bool(ctx.audio) or ctx.mode == "listen"  # a plain text run gets no prelude events at all
    if ctx.audio:
        if timer is not None and "speech_end" not in timer.as_dict():
            stamp("speech_end")
        audio, ctx.audio = ctx.audio, None  # never stored: the only reference is dropped here
        yield agui.step_started("transcribing")
        try:
            text = await stt.transcribe(audio, "audio/wav", ctx.lang)
        finally:
            del audio
        yield agui.step_finished("transcribing")
        stamp("stt_done")
        ctx.user_text = (ctx.user_text + " " + text).strip() if ctx.user_text else text
        yield agui.custom("transcript", {"text": ctx.user_text})
    if ctx.mode == "listen":
        ok = await about_record(ctx.user_text, ctx.lang)
        stamp("gate_done")
        if not ok:
            ctx.gated_out = True
    if timer is not None and voiced:
        yield agui.custom("timing", timer.as_dict())
