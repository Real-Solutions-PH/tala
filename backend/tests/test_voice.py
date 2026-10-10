import asyncio
import io
import json
import os
import wave
from pathlib import Path

import httpx
import pytest

from kapiling.voice import stt, tts
from kapiling.voice.sentences import SentenceAggregator
from kapiling.voice.timing import TurnTimer


def test_aggregator_emits_complete_sentences_only():
    a = SentenceAggregator()
    assert a.push("Losartan po ") == []
    assert a.push("ang gamot ninyo. Iniinom ") == ["Losartan po ang gamot ninyo."]
    assert a.flush() == ["Iniinom"]


def test_aggregator_ignores_decimal_points_and_abbreviations():
    a = SentenceAggregator()
    assert a.push("Ang FBS ay 5.6 mmol/L noong Dr. Reyes ") == []


def test_aggregator_strips_markdown_per_sentence():
    a = SentenceAggregator()
    assert a.push("**Losartan** 50 mg. ") == ["Losartan 50 mg."]


def test_aggregator_markdown_variants():
    a = SentenceAggregator()
    out = a.push("## Gamot\n- Tingnan ang [talaan](http://x/y) at `Losartan`! _Salamat_ po? ")
    assert out == ["Gamot\nTingnan ang talaan at Losartan!", "Salamat po?"]


def test_aggregator_first_sentence_can_be_short_clause():
    # first chunk is released at a comma after >= 40 chars so first audio is early
    a = SentenceAggregator(); out = a.push("Opo, ang huling blood sugar ninyo noong Hulyo, ")
    assert out == ["Opo, ang huling blood sugar ninyo noong Hulyo,"]
    # only the first chunk is released early
    assert a.push("ay normal, po ninyo at maganda, talaga ") == []


def test_clean_reads_units_and_numbers_by_language():
    assert tts.clean("FBS 132 mg/dL", "tl") == "f b s one hundred and thirty two milligrams per deciliter"   # MMS-tgl reads latin letters
    assert tts.clean("BP 130/80", "en") == "b p one hundred and thirty over eighty"


def test_clean_other_units():
    assert tts.clean("5.6 mmol/L", "en") == "five point six millimoles per liter"
    assert tts.clean("120 mmHg", "en") == "one hundred and twenty millimeters of mercury"
    assert tts.clean("Losartan 50 mg, 12%", "tl") == "losartan fifty milligrams, twelve percent"


def test_clean_glued_units():
    assert tts.clean("Losartan 50mg", "tl") == "losartan fifty milligrams"
    assert tts.clean("130mmHg", "en") == "one hundred and thirty millimeters of mercury"
    assert tts.clean("5.6mmol/L", "en") == "five point six millimoles per liter"


def test_clean_decimal_percent():
    assert tts.clean("6.5%", "en") == "six point five percent"


def test_clean_signs_ranges_and_dates():
    assert tts.clean("-5", "en") == "minus five"
    assert tts.clean("3-5 tablets", "tl") == "three to five tablets"
    assert tts.clean("2024-01-05", "en") == "january five, twenty twenty four"


def test_clean_bp_only_is_over():
    assert tts.clean("BP 130/80", "en") == "b p one hundred and thirty over eighty"
    half = tts.clean("1/2 tablet", "en")
    assert half == "one half tablet" and "over" not in half
    assert "over" not in tts.clean("3/4", "en")


def test_load_fails_fast_and_stays_unloaded_when_cache_missing(monkeypatch):
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setitem(tts.MODELS, "en", "facebook/does-not-exist-xyz")
    monkeypatch.setattr(tts, "_loaded", {})
    with pytest.raises(Exception):
        tts.load("en")
    assert not tts.is_loaded()


# --- STT ------------------------------------------------------------------

def test_stt_posts_language_and_returns_text(monkeypatch):
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["url"] = str(req.url)
        seen["body"] = req.read()
        return httpx.Response(200, json={"text": " Kumusta po \n"})

    monkeypatch.setattr(stt, "_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    out = asyncio.run(stt.transcribe(b"RIFFfake", "audio/wav", "tl"))
    assert out == "Kumusta po"
    assert seen["url"].endswith("/inference")
    body = seen["body"]
    assert b'name="language"' in body and b"\r\n\r\ntl\r\n" in body
    assert b'name="response_format"' in body and b"json" in body
    assert b'name="temperature"' in body and b"\r\n\r\n0\r\n" in body


def test_stt_error_raises(monkeypatch):
    monkeypatch.setattr(stt, "_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(500))))
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(stt.transcribe(b"x", "audio/webm", "en"))


# --- timing ---------------------------------------------------------------

def test_turn_timer_stamps_and_saves(con):
    t = TurnTimer()
    t.stamp("speech_end")
    t.stamp("first_token")
    d = t.as_dict()
    assert list(d) == ["speech_end", "first_token"]
    assert 0 <= d["speech_end"] <= d["first_token"]
    t.save(con, "m1")
    row = con.execute("select stamps from turn_timings where message_id='m1'").fetchone()
    assert json.loads(row[0]) == d


# --- real synthesis ---------------------------------------------------------

def _cached(name: str) -> bool:
    home = Path(os.getenv("HF_HOME", Path.home() / ".cache" / "huggingface"))
    return (home / "hub" / f"models--facebook--{name}").is_dir()


@pytest.mark.skipif(not _cached("mms-tts-tgl"), reason="mms-tts-tgl not in HF cache")
def test_real_tagalog_synthesis_is_valid_wav(monkeypatch):
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    wav = tts.speak("Magandang umaga po", "tl")
    assert wav[:4] == b"RIFF" and wav[8:12] == b"WAVE"
    with wave.open(io.BytesIO(wav)) as w:
        assert w.getsampwidth() == 2
        assert w.getnframes() > 0
        assert w.getnframes() / w.getframerate() > 0
    assert tts.is_loaded()
