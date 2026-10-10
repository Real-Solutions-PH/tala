"""Speech-to-text client for the local whisper.cpp server."""

import httpx

from kapiling import config

_EXT = {"audio/wav": "wav", "audio/x-wav": "wav", "audio/webm": "webm", "audio/ogg": "ogg",
        "audio/mp4": "m4a", "audio/mpeg": "mp3"}


def _client() -> httpx.AsyncClient:
    # Seam for tests (httpx.MockTransport). Long timeout: a cold whisper can be slow.
    return httpx.AsyncClient(timeout=30.0)


async def transcribe(audio: bytes, mime: str, lang: str) -> str:
    # Language is always explicit (tl|en): "auto" mislabels Taglish.
    language = "en" if lang == "en" else "tl"
    ext = _EXT.get(mime.split(";")[0].strip().lower(), "wav")
    async with _client() as client:
        r = await client.post(
            f"{config.settings.whisper_url}/inference",
            files={"file": (f"audio.{ext}", audio, mime)},
            data={"language": language, "response_format": "json", "temperature": "0"},
        )
        r.raise_for_status()
        return str(r.json().get("text", "")).strip()
