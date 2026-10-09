"""Local speech: Meta MMS-TTS (VITS) on CPU, one lazily loaded model per language."""

import io
import os
import re
import threading
from functools import lru_cache
from pathlib import Path

from num2words import num2words

# torch/transformers/scipy are imported lazily so importing this module (health check) stays cheap.

MODELS = {"tl": "facebook/mms-tts-tgl", "en": "facebook/mms-tts-eng"}
_locks = {lang: threading.Lock() for lang in MODELS}  # one synthesis at a time per model
_loaded: dict[str, tuple] = {}

# Numbers are spelled with num2words(lang="en") for both languages: MMS-tgl reads English
# numerals better than anything num2words would produce for Tagalog.
_UNITS = [
    (r"mg\s*/\s*dL", " milligrams per deciliter "),
    (r"mmol\s*/\s*L", " millimoles per liter "),
    (r"mmHg", " millimeters of mercury "),
    (r"mg", " milligrams "),
]
_MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august",
           "september", "october", "november", "december"]


def _iso_date(m: re.Match[str]) -> str:
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not (1 <= mo <= 12 and 1 <= d <= 31):
        return m.group()
    return f"{_MONTHS[mo - 1]} {num2words(d)}, {num2words(y, to='year')}"


def _fraction(m: re.Match[str]) -> str:
    # 1/2 -> "one half"; anything else is read plainly as "a slash b" (a date like 3/4 is ambiguous).
    if m.group(1) == "1" and m.group(2) == "2":
        return "1 half"
    return f"{m.group(1)} slash {m.group(2)}"


def _norm_lang(lang: str) -> str:
    return "en" if lang == "en" else "tl"


def is_loaded() -> bool:
    return bool(_loaded)


def models_cached() -> bool:
    """True when both MMS models are in the HF cache. Directory check only; never loads anything."""
    hub = os.getenv("HF_HUB_CACHE") or str(Path(os.getenv("HF_HOME", Path.home() / ".cache" / "huggingface")) / "hub")
    return all((Path(hub) / f"models--{name.replace('/', '--')}").is_dir() for name in MODELS.values())


def load(lang: str = "tl") -> None:
    from transformers import AutoTokenizer, VitsModel

    lang = _norm_lang(lang)
    with _locks[lang]:
        if lang not in _loaded:
            name = MODELS[lang]
            # local_files_only: a missing cache fails fast instead of stalling on the network.
            tok = AutoTokenizer.from_pretrained(name, local_files_only=True)
            model = VitsModel.from_pretrained(name, local_files_only=True).eval()
            _synth((model, tok), "handa na po" if lang == "tl" else "ready")  # warm-up: first call is slow
            _loaded[lang] = (model, tok)  # registered only once warm-up succeeded


def _say_numbers(text: str) -> str:
    """MMS reads letters, not digits: '5.6' -> 'five point six', '3' -> 'three'."""

    def money(m: re.Match[str]) -> str:
        whole, _, cents = m.group(1).replace(",", "").partition(".")
        out = f"{num2words(int(whole))} pesos"
        if cents and int(cents):
            out += f" {num2words(int(cents))}"
        return out

    text = re.sub(r"₱\s?([\d,]+(?:\.\d+)?)", money, text)
    text = re.sub(r"(\d+(?:\.\d+)?)\s?%", lambda m: f"{num2words(float(m.group(1)) if '.' in m.group(1) else int(m.group(1)))} percent", text)
    text = re.sub(r"(?<=\d),(?=\d{3}\b)", "", text)  # 1,250 -> 1250
    text = re.sub(r"\d+(?:\.\d+)?", lambda m: num2words(float(m.group()) if "." in m.group() else int(m.group())), text)
    return text


def clean(text: str, lang: str = "tl") -> str:
    # lang is accepted for symmetry; both models get the same English-spelled numbers and units.
    text = re.sub(r"\b(\d{4})-(\d{2})-(\d{2})\b", _iso_date, text)  # ISO date
    text = re.sub(r"\b(\d{2,3})/(\d{2,3})\b", r"\1 over \2", text)  # blood pressure 130/80
    text = re.sub(r"\b(\d+)/(\d+)\b", _fraction, text)
    for pat, spoken in _UNITS:  # lookarounds, not \b: units may be glued to the number (50mg)
        text = re.sub(rf"(?<![A-Za-z]){pat}(?![A-Za-z])", spoken, text, flags=re.IGNORECASE)
    text = re.sub(r"(?<!\w)-(?=\d)", "minus ", text)
    text = re.sub(r"(?<=\d)-(?=\d)", " to ", text)
    text = re.sub(r"\b[A-Z]{2,}\b", lambda m: " ".join(m.group().lower()), text)  # FBS -> f b s
    text = _say_numbers(text)
    text = re.sub(r"[☀-➿\U0001F300-\U0001FAFF]", "", text)  # emoji
    text = re.sub(r"\s+", " ", text.replace("-", " ")).strip().lower()
    return re.sub(r" ([,.;:!?])", r"\1", text)


def _synth(pair: tuple, text: str) -> bytes:
    import scipy.io.wavfile
    import torch

    model, tok = pair
    with torch.inference_mode():
        wave = model(**tok(text, return_tensors="pt")).waveform[0].clamp(-1, 1)
    pcm = (wave * 32767).short().numpy()  # 16-bit PCM: the WAV flavour every phone browser plays
    buf = io.BytesIO()
    scipy.io.wavfile.write(buf, model.config.sampling_rate, pcm)
    return buf.getvalue()


@lru_cache(maxsize=512)
def _speak(text: str, lang: str) -> bytes:
    load(lang)
    t = clean(text, lang) or ("pasensya po" if lang == "tl" else "sorry")
    with _locks[lang]:
        return _synth(_loaded[lang], t)


def speak(text: str, lang: str = "tl") -> bytes:
    """Synchronous; callers use run_in_threadpool."""
    return _speak(text, _norm_lang(lang))
