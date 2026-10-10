"""AG-UI events (contract C3). Each event is one SSE frame: `data: <json>\\n\\n`."""

import json
from typing import Any


def encode(event: dict) -> bytes:
    # json.dumps escapes newlines inside strings, so a frame can never be split early.
    return b"data: " + json.dumps(event, ensure_ascii=False, separators=(",", ":")).encode() + b"\n\n"


def run_started(tid: str, rid: str) -> dict:
    return {"type": "RUN_STARTED", "threadId": tid, "runId": rid}


def step_started(name: str) -> dict:
    return {"type": "STEP_STARTED", "stepName": name}


def step_finished(name: str) -> dict:
    return {"type": "STEP_FINISHED", "stepName": name}


def tool_start(cid: str, name: str) -> dict:
    return {"type": "TOOL_CALL_START", "toolCallId": cid, "toolCallName": name}


def tool_end(cid: str) -> dict:
    return {"type": "TOOL_CALL_END", "toolCallId": cid}


def text_start(mid: str) -> dict:
    return {"type": "TEXT_MESSAGE_START", "messageId": mid, "role": "assistant"}


def text_delta(mid: str, s: str) -> dict:
    return {"type": "TEXT_MESSAGE_CONTENT", "messageId": mid, "delta": s}


def text_end(mid: str) -> dict:
    return {"type": "TEXT_MESSAGE_END", "messageId": mid}


def custom(name: str, value: Any) -> dict:
    return {"type": "CUSTOM", "name": name, "value": value}


def run_error(key: str, code: str) -> dict:
    """`key` is an i18n key (e.g. errors.timeout); `code` is llm_unavailable|timeout|cancelled|bad_input|internal."""
    return {"type": "RUN_ERROR", "message": key, "code": code}


def run_finished(tid: str, rid: str, mid: str | None, status: str) -> dict:
    """`mid` is the saved assistant message id, or None when saving it failed."""
    return {"type": "RUN_FINISHED", "threadId": tid, "runId": rid, "result": {"messageId": mid, "status": status}}
