"""Cut a streaming LLM reply into speakable sentences, cleaning markdown per sentence."""

import re

# Always abbreviations: a following capital is a name, not a new sentence.
_TITLES = {"dr", "dra", "gng", "g"}
# Units/short words: an abbreviation only when the sentence visibly continues
# (lowercase letter or digit next). At the end of the buffer they count as a sentence end.
_SOFT = {"mg", "no"}
_FIRST_CHUNK_MIN = 40

_END = re.compile(r"[.!?]+(?=\s)")


def _clean(s: str) -> str:
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)  # links -> text
    s = re.sub(r"(?m)^\s*#+\s*", "", s)  # headings
    s = re.sub(r"(?m)^\s*(?:[-*+]|\d+[.)])\s+", "", s)  # list markers
    s = s.replace("**", "").replace("*", "").replace("`", "")
    s = re.sub(r"(?<![A-Za-z0-9])_|_(?![A-Za-z0-9])", "", s)  # emphasis underscores
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r" ?\n ?", "\n", s)
    return s.strip()


class SentenceAggregator:
    def __init__(self) -> None:
        self._buf = ""
        self._released = False  # has any chunk gone out yet?

    def _is_boundary(self, m: re.Match[str]) -> bool:
        text = self._buf
        word = re.search(r"([A-Za-z]+|\d+)$", text[: m.start()])
        if m.group().startswith("."):
            tok = word.group().lower() if word else ""
            if tok in _TITLES:
                return False
            line_start = text.rfind("\n", 0, m.start()) + 1
            if tok.isdigit() and text[line_start : m.start()].strip().isdigit():
                return False  # "1. " list marker
            if tok in _SOFT:
                rest = text[m.end() :].lstrip()
                if rest and (rest[0].islower() or rest[0].isdigit()):
                    return False
        return True

    def _take(self, end: int) -> str | None:
        chunk, self._buf = self._buf[:end], self._buf[end:].lstrip()
        self._released = True
        return _clean(chunk) or None

    def push(self, token: str) -> list[str]:
        self._buf += token
        out: list[str] = []
        while True:
            end = next((m.end() for m in _END.finditer(self._buf) if self._is_boundary(m)), None)
            if end is None and not self._released:
                # Low first-audio latency: release the first clause at a comma once it is long enough.
                end = next((m.end() for m in re.finditer(r",(?=\s)", self._buf) if m.end() >= _FIRST_CHUNK_MIN), None)
            if end is None:
                return out
            chunk = self._take(end)
            if chunk:
                out.append(chunk)

    def flush(self) -> list[str]:
        rest, self._buf = _clean(self._buf), ""
        self._released = True
        return [rest] if rest else []
