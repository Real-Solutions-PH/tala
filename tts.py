"""Local Tagalog speech: Meta MMS-TTS (facebook/mms-tts-tgl, VITS), on CPU."""

import io
import re
import threading
from functools import lru_cache

import scipy.io.wavfile
import torch
from num2words import num2words
from transformers import AutoTokenizer, VitsModel

MODEL = "facebook/mms-tts-tgl"
_lock = threading.Lock()  # ponytail: one synthesis at a time; a queue per device if several phones talk at once
_model: VitsModel | None = None
_tok = None


def load() -> None:
    global _model, _tok
    with _lock:
        if _model is None:
            _tok = AutoTokenizer.from_pretrained(MODEL)
            _model = VitsModel.from_pretrained(MODEL).eval()
            _synth("handa na po")  # warm-up: the first call is several times slower


def _say_numbers(text: str) -> str:
    """MMS reads letters, not digits: '₱86.50' -> 'eighty-six pesos fifty', '3' -> 'three'."""

    def money(m: re.Match[str]) -> str:
        whole, _, cents = m.group(1).replace(",", "").partition(".")
        out = f"{num2words(int(whole))} pesos"
        if cents and int(cents):
            out += f" {num2words(int(cents))}"
        return out

    text = re.sub(r"₱\s?([\d,]+(?:\.\d+)?)", money, text)
    text = re.sub(r"(\d+)%", lambda m: f"{num2words(int(m.group(1)))} percent", text)
    text = re.sub(r"\d+(?:\.\d+)?", lambda m: num2words(float(m.group()) if "." in m.group() else int(m.group())), text)
    return text


def clean(text: str) -> str:
    text = _say_numbers(text)
    text = re.sub(r"[☀-➿\U0001F300-\U0001FAFF]", "", text)  # emoji
    return re.sub(r"\s+", " ", text.replace("-", " ")).strip().lower()


def _synth(text: str) -> bytes:
    assert _model is not None and _tok is not None
    with torch.inference_mode():
        wave = _model(**_tok(text, return_tensors="pt")).waveform[0].clamp(-1, 1)
    pcm = (wave * 32767).short().numpy()  # 16-bit PCM: the WAV flavour every phone browser plays
    buf = io.BytesIO()
    scipy.io.wavfile.write(buf, _model.config.sampling_rate, pcm)
    return buf.getvalue()


@lru_cache(maxsize=256)
def speak(text: str) -> bytes:
    load()
    t = clean(text)
    with _lock:
        return _synth(t or "pasensya po")


if __name__ == "__main__":
    assert clean("Benta: ₱86.00, 3 Kopiko, 12%") == "benta: eighty six pesos, three kopiko, twelve percent", clean("Benta: ₱86.00, 3 Kopiko, 12%")
    assert clean("₱1,250.50!") == "one thousand, two hundred and fifty pesos fifty!"
    print("ok")
