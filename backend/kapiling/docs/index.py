"""The chunk index: `chunks` rows, the FTS5 keyword index over them, and the sqlite-vec vectors."""

import hashlib
import json
import sqlite3

from langchain_core.documents import Document
from sqlite_vec import serialize_float32

DIM = 1024
TEMPLATE_VERSION = "v1"   # part of content_hash: changing embed_text() wording must bump this

VEC_DDL = ("CREATE VIRTUAL TABLE IF NOT EXISTS chunks_vec USING vec0(chunk_id INTEGER PRIMARY KEY, "
           "profile_id INTEGER PARTITION KEY, document_id INTEGER, embedding FLOAT[1024] distance_metric=cosine)")


def ensure(con: sqlite3.Connection) -> None:
    """Create chunks_vec (needs sqlite-vec >= 0.1.6 for the partition key and metadata column)."""
    con.execute(VEC_DDL)


def embed_text(title: str, headings: list[str], text: str) -> str:
    lines = text.splitlines()
    if lines and lines[0].strip().lower() == title.strip().lower():
        lines = lines[1:]                     # drop a first line that repeats the title
    return "\n".join([title, *headings, "\n".join(lines)])    # plain newline join, no labels (G-C-077 measurement)


def content_hash(doc: Document) -> str:
    s = TEMPLATE_VERSION + embed_text(doc.metadata["title"], doc.metadata.get("headings") or [], doc.page_content)
    return hashlib.sha256(s.encode()).hexdigest()


def _delete(con: sqlite3.Connection, document_id: int) -> None:
    rows = con.execute("select id, text from chunks where document_id=?", (document_id,)).fetchall()
    for r in rows:
        con.execute("insert into chunks_fts (chunks_fts, rowid, text) values ('delete', ?, ?)", (r["id"], r["text"]))
        con.execute("delete from chunks_vec where chunk_id=?", (r["id"],))
    con.execute("delete from chunks where document_id=?", (document_id,))


def _atomic(con: sqlite3.Connection, fn) -> None:
    """Run fn inside a savepoint: nested in the caller's transaction if one is open, committed otherwise."""
    outer = con.in_transaction
    con.execute("savepoint idx")
    try:
        fn()
    except BaseException:
        con.execute("rollback to idx")
        con.execute("release idx")
        raise
    con.execute("release idx")
    if not outer:
        con.commit()


def write_chunks(con: sqlite3.Connection, document_id: int, profile_id: int, docs: list[Document],
                 vectors: list[list[float]]) -> None:
    """Replace the document's chunks, FTS rows and vectors in one transaction."""
    if len(docs) != len(vectors):
        raise ValueError(f"{len(docs)} chunks but {len(vectors)} vectors")
    if any(len(v) != DIM for v in vectors):
        raise ValueError(f"embeddings must have {DIM} dimensions")
    ensure(con)

    def run():
        _delete(con, document_id)
        for i, (d, v) in enumerate(zip(docs, vectors)):
            m = d.metadata
            meta = {"title": m["title"], "headings": m.get("headings") or [], "page": m.get("page"), "bbox": m.get("bbox")}
            cur = con.execute(
                "insert into chunks (document_id, profile_id, ord, text, meta, content_hash) values (?,?,?,?,?,?)",
                (document_id, profile_id, m.get("ord", i), d.page_content, json.dumps(meta), content_hash(d)))
            cid = cur.lastrowid
            con.execute("insert into chunks_fts (rowid, text) values (?, ?)", (cid, d.page_content))
            con.execute("insert into chunks_vec (chunk_id, profile_id, document_id, embedding) values (?,?,?,?)",
                        (cid, profile_id, document_id, serialize_float32(v)))

    _atomic(con, run)


def delete_document(con: sqlite3.Connection, document_id: int) -> None:
    """Remove the document's chunks, FTS rows and vectors (the document row itself stays)."""
    ensure(con)
    _atomic(con, lambda: _delete(con, document_id))
