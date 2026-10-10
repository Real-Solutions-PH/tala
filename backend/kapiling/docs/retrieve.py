"""Hybrid retrieval: FTS5 keywords + sqlite-vec vectors, both filtered by profile inside the query, fused with
reciprocal rank fusion, reranked by the local cross-encoder, cut at a score floor, and turned into citations.

Everything here is sync: callers run it in a threadpool.
"""

import asyncio
import json
import re
import sqlite3
from dataclasses import dataclass

import httpx
from sqlite_vec import serialize_float32

from kapiling import config
from kapiling.docs import index, ingest

CANDIDATES = 24
RERANK_FLOOR = 0.0   # placeholder: set from eval/run_eval.py output in Task 19; record the measured run next to it
RRF_K = 60
RERANK_TIMEOUT = 30.0
QUERY_INSTRUCT = "Instruct: Given a question about a person's health records, retrieve the passages that answer it\nQuery: "
CONTEXT = 80        # characters of before/after around a citation match
FALLBACK_MATCH = 160

_TOKEN = re.compile(r"[^\W_]+")   # unicode letters and digits
# A sentence ends at . ! or ? followed by whitespace (so "7.2" stays whole), at a line break, or at the end.
_SENTENCE = re.compile(r"\S[^\n]*?(?:[.!?]+(?=\s|$)|(?=\n)|$)")


class RerankUnavailable(Exception):
    pass


@dataclass(frozen=True)
class Hit:
    chunk_id: int
    document_id: int
    title: str
    headings: list[str]
    page: int | None
    bbox: list[float] | None
    text: str
    score: float


@dataclass(frozen=True)
class Source:
    n: int
    chunk_id: int
    document_id: int
    title: str
    page: int | None
    bbox: list[float] | None
    before: str
    match: str
    after: str


def _tokens(s: str) -> list[str]:
    return _TOKEN.findall(s)


def fts_query(q: str) -> str:
    """Alphanumeric tokens, each quoted, joined with OR: user punctuation can never become FTS5 syntax."""
    return " OR ".join(f'"{t}"' for t in _tokens(q))


def rrf(*rankings: list[int], k: int = RRF_K) -> list[int]:
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, cid in enumerate(ranking, start=1):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
    return sorted(scores, key=lambda c: -scores[c])


def embed_query(q: str) -> list[float]:
    """The query side gets the instruction prefix and no title (G-C-077). Reuses the ingest embedding client."""
    return asyncio.run(ingest.embed_texts([QUERY_INSTRUCT + q]))[0]


def _rerank_post(payload: dict) -> dict:
    """The one seam for rerank calls (tests substitute it)."""
    r = httpx.post(f"{config.settings.rerank_url}/v1/rerank", json=payload, timeout=RERANK_TIMEOUT)
    r.raise_for_status()
    return r.json()


def rerank(query: str, texts: list[str]) -> list[tuple[int, float]]:
    """(position in texts, relevance score), best first."""
    if not texts:
        return []
    try:
        body = _rerank_post({"query": query, "documents": texts})
        scored = [(int(r["index"]), float(r["relevance_score"])) for r in body["results"]]
    except Exception as e:
        raise RerankUnavailable(type(e).__name__) from e
    return sorted(scored, key=lambda p: -p[1])


def _row(con: sqlite3.Connection, cid: int) -> sqlite3.Row:
    return con.execute("select id, document_id, text, meta from chunks where id=?", (cid,)).fetchone()


def _hit(row: sqlite3.Row, score: float) -> Hit:
    m = json.loads(row["meta"])
    return Hit(chunk_id=row["id"], document_id=row["document_id"], title=m["title"], headings=m.get("headings") or [],
               page=m.get("page"), bbox=m.get("bbox"), text=row["text"], score=score)


def search(con: sqlite3.Connection, pid: int, query: str, k: int = 6) -> list[Hit]:
    """Top-k chunks of this profile for the query, reranked, with scores below RERANK_FLOOR dropped."""
    match = fts_query(query)
    if not match:
        return []
    if con.execute("select 1 from chunks where profile_id=? limit 1", (pid,)).fetchone() is None:
        return []   # nothing indexed: no model calls
    index.ensure(con)
    fts = con.execute("select chunks_fts.rowid, bm25(chunks_fts) s from chunks_fts join chunks on chunks.id=chunks_fts.rowid "
                      "where chunks_fts match ? and chunks.profile_id=? order by s limit ?",
                      (match, pid, CANDIDATES)).fetchall()
    qv = embed_query(query)
    vec = con.execute("select chunk_id, distance from chunks_vec where embedding match ? and k=? and profile_id=?",
                      (serialize_float32(qv), CANDIDATES, pid)).fetchall()
    fused = rrf([r[0] for r in fts], [r[0] for r in vec])[:CANDIDATES]
    rows = [_row(con, cid) for cid in fused]
    rows = [r for r in rows if r is not None]
    scored = rerank(query, [r["text"] for r in rows])
    return [_hit(rows[i], s) for i, s in scored if s >= RERANK_FLOOR][:k]


def _span(text: str, query: str) -> tuple[int, int]:
    """Start and end of the sentence sharing the most distinct word tokens with the query, else the first 160 chars."""
    q = {t.lower() for t in _tokens(query)}
    best, best_n = None, 0
    for m in _SENTENCE.finditer(text):
        n = len(q & {t.lower() for t in _tokens(m.group())})
        if n > best_n:
            best, best_n = m, n
    if best is None:
        return 0, min(len(text), FALLBACK_MATCH)
    return best.start(), best.end()


def to_sources(hits: list[Hit], query: str) -> list[Source]:
    """Citations numbered from 1; before/match/after are contiguous slices of the stored bare chunk text."""
    out = []
    for n, h in enumerate(hits, start=1):
        s, e = _span(h.text, query)
        out.append(Source(n=n, chunk_id=h.chunk_id, document_id=h.document_id, title=h.title, page=h.page,
                          bbox=h.bbox, before=h.text[max(0, s - CONTEXT):s], match=h.text[s:e],
                          after=h.text[e:e + CONTEXT]))
    return out
