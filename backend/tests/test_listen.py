import asyncio
import json
from dataclasses import dataclass, field

import httpx
import pytest

from kapiling.chat import listen
from kapiling.voice.timing import TurnTimer


def _answer(content: str) -> dict:
    return {"choices": [{"message": {"content": content}}]}


def _gate(monkeypatch, result=None, exc=None, seen=None):
    async def fake_post(url, payload, timeout):
        if seen is not None:
            seen.append((url, payload, timeout))
        if exc:
            raise exc
        return result

    monkeypatch.setattr(listen, "_post", fake_post)


def test_gate_true(monkeypatch):
    seen = []
    _gate(monkeypatch, _answer('{"about_record": true}'), seen=seen)
    assert asyncio.run(listen.about_record("Ano po ang gamot niya sa presyon?", "tl")) is True
    url, payload, _ = seen[0]
    assert url.endswith("/v1/chat/completions")
    assert payload["max_tokens"] == 8
    schema = payload["response_format"]["json_schema"]["schema"]
    assert schema["properties"] == {"about_record": {"type": "boolean"}}


def test_gate_false(monkeypatch):
    _gate(monkeypatch, _answer('{"about_record": false}'))
    assert asyncio.run(listen.about_record("Ang ganda ng panahon", "tl")) is False


@pytest.mark.parametrize("content", ["", "not json", '{"about_record": "yes"}', "[true]", '{"x": 1}'])
def test_gate_odd_answer_is_false(monkeypatch, content):
    _gate(monkeypatch, _answer(content))
    assert asyncio.run(listen.about_record("hello", "en")) is False


@pytest.mark.parametrize("exc", [httpx.ConnectError("down"), httpx.ReadTimeout("slow"), KeyError("choices")])
def test_gate_error_is_false(monkeypatch, exc):
    _gate(monkeypatch, exc=exc)
    assert asyncio.run(listen.about_record("What is her sugar level?", "en")) is False


def test_gate_empty_text_skips_call(monkeypatch):
    seen = []
    _gate(monkeypatch, _answer('{"about_record": true}'), seen=seen)
    assert asyncio.run(listen.about_record("  ", "en")) is False
    assert seen == []


def test_gate_cancellation_propagates(monkeypatch):
    _gate(monkeypatch, exc=asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(listen.about_record("x", "en"))


@dataclass
class Ctx:
    mode: str
    audio: bytes | None
    lang: str = "tl"
    user_text: str = ""
    timer: TurnTimer = field(default_factory=TurnTimer)


def _collect(ctx):
    async def go():
        return [ev async for ev in listen.prelude(ctx)]
    return asyncio.run(go())


def _stt(monkeypatch, text="Ano po ang gamot ko?"):
    async def fake(audio, mime, lang):
        assert audio == b"RIFFwav"
        return text
    monkeypatch.setattr(listen.stt, "transcribe", fake)


def test_listen_gate_false_ends_quietly_and_forgets_audio(monkeypatch):
    _stt(monkeypatch)
    _gate(monkeypatch, _answer('{"about_record": false}'))
    ctx = Ctx(mode="listen", audio=b"RIFFwav")
    evs = _collect(ctx)
    assert ctx.gated_out is True
    assert ctx.audio is None
    assert not any(e["type"].startswith("TEXT_MESSAGE") for e in evs)
    assert not any(e.get("name") == "audio" for e in evs)
    assert "RIFFwav" not in json.dumps(evs)
    assert ctx.user_text == "Ano po ang gamot ko?"


def test_listen_gate_true_continues(monkeypatch):
    _stt(monkeypatch)
    _gate(monkeypatch, _answer('{"about_record": true}'))
    ctx = Ctx(mode="listen", audio=b"RIFFwav")
    _collect(ctx)
    assert ctx.gated_out is False


def test_usap_emits_transcript_then_increasing_timing(monkeypatch):
    _stt(monkeypatch)
    ctx = Ctx(mode="usap", audio=b"RIFFwav")
    evs = _collect(ctx)
    names = [e.get("stepName") or e.get("name") for e in evs]
    assert names == ["transcribing", "transcribing", "transcript", "timing"]
    assert evs[2]["value"] == {"text": "Ano po ang gamot ko?"}
    stamps = evs[-1]["value"]
    assert list(stamps) == ["speech_end", "stt_done"]
    assert stamps["speech_end"] <= stamps["stt_done"]
    assert ctx.gated_out is False


def test_text_run_has_no_transcript(monkeypatch):
    ctx = Ctx(mode="text", audio=None, user_text="hi", timer=None)
    assert _collect(ctx) == []
    assert ctx.user_text == "hi"
