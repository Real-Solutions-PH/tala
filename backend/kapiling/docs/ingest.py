"""Document ingestion: vision transcript or Docling parse -> HybridChunker -> batched embeddings -> index.

One background worker (`run_pending`) processes one document at a time, because the vision model is the bottleneck.
"""

import asyncio
import logging
import sqlite3
from functools import cache
from io import BytesIO
from pathlib import Path, PurePath

import httpx
from langchain_core.documents import Document

from kapiling import config, db
from kapiling.docs import index, store, vision
from kapiling.docs.index import TEMPLATE_VERSION, embed_text  # noqa: F401  (re-exported: part of this module's API)

log = logging.getLogger("kapiling.ingest")

KINDS = ("lab", "record", "prescription", "discharge", "imaging", "other")
PDF = "application/pdf"
EMBED_BATCH = 32
EMBED_TIMEOUT = 60.0
MAX_TOKENS = 512


class EmbedUnavailable(Exception):
    pass


class ParseFailed(Exception):
    pass


# --- embeddings ---------------------------------------------------------------

async def _embed_post(payload: dict) -> dict:
    """The one seam for embedding calls (tests substitute it)."""
    async with httpx.AsyncClient(timeout=EMBED_TIMEOUT) as client:
        r = await client.post(f"{config.settings.embed_url}/v1/embeddings", json=payload)
        r.raise_for_status()
        return r.json()


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed in batches of EMBED_BATCH (one POST for a typical document)."""
    out: list[list[float]] = []
    for i in range(0, len(texts), EMBED_BATCH):
        batch = texts[i:i + EMBED_BATCH]
        try:
            body = await _embed_post({"input": batch})
            data = sorted(body["data"], key=lambda d: d.get("index", 0))
            vectors = [d["embedding"] for d in data]
        except BaseException as e:
            if not isinstance(e, Exception):
                raise  # CancelledError must propagate
            raise EmbedUnavailable(type(e).__name__) from e
        if len(vectors) != len(batch):
            raise EmbedUnavailable(f"{len(vectors)} embeddings for {len(batch)} inputs")
        out.extend(vectors)
    return out


# --- Docling ------------------------------------------------------------------

@cache
def _md_converter():
    from docling.datamodel.base_models import InputFormat
    from docling.document_converter import DocumentConverter

    return DocumentConverter(allowed_formats=[InputFormat.MD])


@cache
def _pdf_converter():
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    # Docling's OCR is off: its auto engine (RapidOCR) downloads models from the network on first use, and a
    # PDF without a text layer is read page by page by the vision model instead (see _ingest).
    art = config.settings.docling_artifacts
    if not art.is_dir():
        log.warning("no Docling models at %s (run scripts/fetch_models.sh); falling back to the HF cache", art)
    opts = PdfPipelineOptions(do_ocr=False, artifacts_path=art if art.is_dir() else None)
    return DocumentConverter(allowed_formats=[InputFormat.PDF],
                             format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)})


@cache
def _chunker():
    from docling.chunking import HybridChunker
    from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer

    tok = HuggingFaceTokenizer.from_pretrained(config.settings.embed_tokenizer, max_tokens=MAX_TOKENS)
    return HybridChunker(tokenizer=tok, merge_peers=True)


def _from_markdown(md: str):
    from docling.datamodel.base_models import DocumentStream

    try:
        return _md_converter().convert(DocumentStream(name="t.md", stream=BytesIO(md.encode()))).document
    except Exception as e:
        raise ParseFailed(type(e).__name__) from e


def _from_pdf(path: Path):
    try:
        dl = _pdf_converter().convert(path).document
    except Exception as e:
        raise ParseFailed(type(e).__name__) from e
    return dl, dl.export_to_markdown()   # markdown kept for display and extraction only, never for chunking


def _first_prov(chunk):
    for item in chunk.meta.doc_items:
        if item.prov:
            return item.prov[0]
    return None


def first_page(chunk) -> int | None:
    p = _first_prov(chunk)
    return p.page_no if p else None


def first_bbox(chunk, dl) -> list[float] | None:
    """[left, top, right, bottom] in page points, top-left origin."""
    p = _first_prov(chunk)
    if p is None:
        return None
    page = dl.pages.get(p.page_no)
    bbox = p.bbox.to_top_left_origin(page_height=page.size.height) if page else p.bbox
    return [round(x, 1) for x in bbox.as_tuple()]


def _chunk(parts: list[tuple], title: str) -> list[Document]:
    """parts: (DoclingDocument, page to use when Docling has no provenance, i.e. a vision transcript)."""
    chunks = [(c, dl, page) for dl, page in parts for c in _chunker().chunk(dl)]
    return [Document(page_content=c.text, metadata={
                "title": title, "headings": c.meta.headings or [],
                "page": first_page(c) or page, "bbox": first_bbox(c, dl), "ord": i})
            for i, (c, dl, page) in enumerate(chunks)]


# --- queue --------------------------------------------------------------------

def enqueue(con: sqlite3.Connection, profile_id: int, data: bytes, filename: str, mime: str,
            title: str | None, kind: str | None) -> int:
    """Store the file and queue it. The same bytes for the same profile return the existing document id."""
    if kind is not None and kind not in KINDS:
        raise ValueError(f"kind must be one of {', '.join(KINDS)}")
    sha = store.sha256(data)
    existing = con.execute("select id from documents where profile_id=? and sha256=?", (profile_id, sha)).fetchone()
    if existing:
        return existing[0]
    pages = store.pdf_pages(data) if mime == PDF else 1
    rel = store.write(profile_id, data, filename, mime)
    # A title the user did not give is the file's stem; process_one replaces it with the extracted one.
    title = (title or "").strip() or PurePath(rel).stem
    try:
        cur = con.execute(
            "insert into documents (profile_id, title, kind, file_path, mime, pages, sha256) values (?,?,?,?,?,?,?)",
            (profile_id, title, kind or "other", rel, mime, pages, sha))
        con.commit()
    except sqlite3.IntegrityError:
        con.rollback()
        store.remove(rel)
        row = con.execute("select id from documents where profile_id=? and sha256=?", (profile_id, sha)).fetchone()
        if row is None:
            raise
        return row[0]
    except BaseException:
        con.rollback()
        store.remove(rel)
        raise
    return cur.lastrowid


def _error_code(e: Exception) -> str:
    if isinstance(e, vision.VisionUnavailable):
        return "vision_unavailable"
    if isinstance(e, EmbedUnavailable):
        return "embed_unavailable"
    if isinstance(e, ParseFailed):
        return "parse_failed"
    if isinstance(e, FileNotFoundError):
        return "file_missing"
    return "internal"


def _load(con: sqlite3.Connection, document_id: int) -> sqlite3.Row | None:
    doc = con.execute("select * from documents where id=?", (document_id,)).fetchone()
    if doc is not None:
        con.execute("update documents set status='reading', error=null where id=?", (document_id,))
        con.commit()
    return doc


def _write(con: sqlite3.Connection, doc: sqlite3.Row, docs: list[Document], vectors: list[list[float]], meta: dict,
           md: str, title: str, kind: str, date: str | None, facility: str | None) -> None:
    """One transaction: chunks + FTS + vectors, proposed observations and the document row."""
    con.execute("begin")
    try:
        index.write_chunks(con, doc["id"], doc["profile_id"], docs, vectors)
        con.execute("delete from observations where document_id=? and status='proposed'", (doc["id"],))
        for o in meta["observations"]:
            o_date = o["date"] or date
            if not o_date:
                continue  # observations.date is NOT NULL; an undated value cannot be charted
            con.execute(
                "insert into observations (profile_id, code, label, value, value_text, unit, ref_low, ref_high, date,"
                " facility, document_id, status) values (?,?,?,?,?,?,?,?,?,?,?, 'proposed')",
                (doc["profile_id"], o["code"], o["label"], o["value"], o["value_text"], o["unit"], o["ref_low"],
                 o["ref_high"], o_date, o["facility"] or facility, doc["id"]))
        con.execute("update documents set status='indexed', error=null, transcript_md=?, title=?, kind=?, date=?,"
                    " facility=? where id=?", (md, title, kind, date, facility, doc["id"]))
        con.commit()
    except BaseException:
        con.rollback()
        raise


def _fail(con: sqlite3.Connection, document_id: int, code: str) -> None:
    """Mark failed and unsearchable. If removing the index rows fails too, still mark the document failed."""
    if con.in_transaction:
        con.rollback()
    try:
        index.delete_document(con, document_id)
    except Exception:
        log.exception("document %s: could not clear its index rows", document_id)
        if con.in_transaction:
            con.rollback()
        code = "internal"
    con.execute("update documents set status='failed', error=? where id=?", (code, document_id))
    con.commit()


def _requeue(con: sqlite3.Connection, document_id: int) -> None:
    if con.in_transaction:
        con.rollback()
    con.execute("update documents set status='queued' where id=?", (document_id,))
    con.commit()


async def _ingest(con: sqlite3.Connection, doc: sqlite3.Row) -> None:
    path = store.path(doc["file_path"])
    is_image = doc["mime"].startswith("image/")
    if is_image:
        md = await vision.transcribe(await asyncio.to_thread(path.read_bytes), doc["mime"])
        parts = [(await asyncio.to_thread(_from_markdown, md), 1)]
    elif await asyncio.to_thread(store.pdf_has_text, path):
        dl, md = await asyncio.to_thread(_from_pdf, path)
        parts = [(dl, None)]
    else:  # a scanned PDF: the vision model reads each page, as it does photos
        pages_md, parts = [], []
        for n in range(1, min(doc["pages"], store.MAX_PDF_PAGES) + 1):
            page_md = await vision.transcribe(await asyncio.to_thread(store.render_pdf_page, path, n), "image/png")
            pages_md.append(page_md)
            parts.append((await asyncio.to_thread(_from_markdown, page_md), n))
        md = "\n\n".join(pages_md)
    meta = await vision.extract(md)

    # Fill what the user did not give: a stem title, kind 'other', no date, no facility.
    title = meta["title"] if meta["title"] and doc["title"] == PurePath(doc["file_path"]).stem else doc["title"]
    kind = meta["kind"] if meta["kind"] and doc["kind"] == "other" else doc["kind"]
    date = doc["date"] or meta["date"]
    facility = doc["facility"] or meta["facility"]

    docs = await asyncio.to_thread(_chunk, parts, title)
    vectors = await embed_texts([embed_text(title, d.metadata["headings"], d.page_content) for d in docs])
    await asyncio.to_thread(_write, con, doc, docs, vectors, meta, md, title, kind, date, facility)


async def process_one(con: sqlite3.Connection, document_id: int) -> None:
    """Read, chunk, embed and index one document; ends 'indexed' or 'failed' with an error code.
    Every database call runs in a worker thread, so a busy database never stalls the event loop (chat streams)."""
    doc = await asyncio.to_thread(_load, con, document_id)
    if doc is None:
        return
    try:
        await _ingest(con, doc)
    except BaseException as e:
        if not isinstance(e, Exception):
            # CancelledError (shutdown): requeue so the next start picks it up, then propagate. Done inline: a
            # cancelled task must not await again. One quick UPDATE.
            _requeue(con, document_id)
            raise
        code = _error_code(e)
        log.warning("document %s failed: %s (%s)", document_id, code, type(e).__name__)
        await asyncio.to_thread(_fail, con, document_id, code)


def _connect() -> sqlite3.Connection:
    return db.connect()


def _reset(con: sqlite3.Connection) -> None:
    con.execute("update documents set status='queued' where status='reading'")  # interrupted mid-way
    con.commit()


def _next(con: sqlite3.Connection) -> int | None:
    row = con.execute("select id from documents where status='queued' order by created, id limit 1").fetchone()
    return row[0] if row else None


async def run_pending(con: sqlite3.Connection | None = None, poll: float = 2.0, backoff: float = 2.0,
                      max_backoff: float = 60.0) -> None:
    """Detached worker loop with its own connection (G-C-015): oldest queued document first, one at a time.

    Any error outside a document's own failure handling (connecting, the startup reset, a failure while marking a
    document failed) is logged; the loop backs off, reconnects and resets 'reading' documents to 'queued', so
    nothing is left stuck in 'reading' and the worker never dies silently."""
    delay = backoff
    while True:
        own = con is None
        c = None
        try:
            c = await asyncio.to_thread(_connect) if own else con
            await asyncio.to_thread(_reset, c)
            delay = backoff
            while True:
                did = await asyncio.to_thread(_next, c)
                if did is None:
                    await asyncio.sleep(poll)
                    continue
                await process_one(c, did)
        except Exception:
            log.exception("ingest worker error; retrying in %.0f s", delay)
            if own and c is not None:
                await asyncio.to_thread(c.close)
            await asyncio.sleep(delay)
            delay = min(delay * 2, max_backoff)
        except BaseException:
            if own and c is not None:
                c.close()
            raise
