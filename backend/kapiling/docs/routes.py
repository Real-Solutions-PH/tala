import io
import sqlite3
from datetime import date as _date
from pathlib import Path
from typing import Annotated

import pillow_heif
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from PIL import Image
from pydantic import BaseModel

from kapiling.auth.deps import Actor, require_owner_of, require_unlocked
from kapiling.auth.lock import log_access
from kapiling.db import get_con
from kapiling.docs import store
from kapiling.docs.ingest import KINDS, PDF, enqueue

router = APIRouter(prefix="/api")
Con = Annotated[sqlite3.Connection, Depends(get_con)]
Unlocked = Annotated[Actor, Depends(require_unlocked)]

MAX_UPLOAD = 20 * 1024 * 1024
KEPT = {"JPEG": "image/jpeg", "PNG": "image/png"}   # other Pillow formats (WEBP, HEIF if pillow-heif) become JPEG
pillow_heif.register_heif_opener()  # once, at import: HEIC photos from phones open in Pillow

LIST_COLS = "id, title, kind, date, facility, mime, pages, status, error, created"


def _read_upload(up: UploadFile) -> tuple[bytes, str]:
    """Validate an upload by its bytes (never the client's content type); returns (bytes to store, mime)."""
    data = up.file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "errors.fileTooBig")
    if data.startswith(b"%PDF-"):
        try:
            pages = store.pdf_pages(data)
        except ValueError:
            raise HTTPException(415, "errors.fileType") from None
        if pages > store.MAX_PDF_PAGES:
            raise HTTPException(413, "errors.tooManyPages")
        return data, PDF
    try:
        with Image.open(io.BytesIO(data)) as img:
            fmt = img.format
            img.verify()
        if fmt in KEPT:
            return data, KEPT[fmt]
        with Image.open(io.BytesIO(data)) as img:  # verify() leaves the image unusable; reopen to convert
            buf = io.BytesIO()
            img.convert("RGB").save(buf, "JPEG", quality=92)
        return buf.getvalue(), "image/jpeg"
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(415, "errors.fileType") from None


def _doc_or_404(con, doc_id: int, actor: Actor):
    d = con.execute("select * from documents where id=?", (doc_id,)).fetchone()
    if d is None:
        raise HTTPException(404, "errors.notFound")
    require_owner_of(actor, d["profile_id"])  # no {pid} in these paths, so the dependency cannot check it
    return d


@router.get("/profiles/{pid}/documents")
def list_documents(pid: int, con: Con, _a: Unlocked):
    return [dict(r) for r in con.execute(
        f"select {LIST_COLS} from documents where profile_id=? order by coalesce(date, created) desc, id desc", (pid,))]


@router.post("/profiles/{pid}/documents")
def upload_document(pid: int, con: Con, _a: Unlocked, file: Annotated[UploadFile, File()],
                    title: Annotated[str | None, Form()] = None, kind: Annotated[str | None, Form()] = None):
    if con.execute("select 1 from profiles where id=?", (pid,)).fetchone() is None:
        raise HTTPException(404, "errors.notFound")
    if kind is not None and kind not in KINDS:
        raise HTTPException(422, f"kind must be one of {', '.join(KINDS)}")
    data, mime = _read_upload(file)
    did = enqueue(con, pid, data, file.filename or "document", mime, title, kind)
    return {"id": did, "status": con.execute("select status from documents where id=?", (did,)).fetchone()[0]}


@router.get("/documents/{doc_id}")
def get_document(doc_id: int, con: Con, actor: Unlocked):
    d = _doc_or_404(con, doc_id, actor)
    body = {k: d[k] for k in LIST_COLS.split(", ")} | {"transcript_md": d["transcript_md"]}
    body["file_url"] = f"/api/documents/{doc_id}/file"
    pages = min(d["pages"], store.MAX_PDF_PAGES)  # bounded even for a row written before the upload cap
    body["page_urls"] = [f"/api/documents/{doc_id}/page/{n}.png" for n in range(1, pages + 1)]
    body["observations"] = [dict(o) for o in con.execute(
        "select * from observations where document_id=? order by id", (doc_id,))]
    log_access(con, d["profile_id"], actor, "view_document", f"document:{doc_id}")
    return body


def _file(d) -> Path:
    try:
        return store.path(d["file_path"])
    except FileNotFoundError:
        raise HTTPException(404, "errors.notFound") from None


@router.get("/documents/{doc_id}/file")
def document_file(doc_id: int, con: Con, actor: Unlocked):
    d = _doc_or_404(con, doc_id, actor)
    p = _file(d)
    log_access(con, d["profile_id"], actor, "view_document", f"document:{doc_id}:file")
    return FileResponse(p, media_type=d["mime"], filename=p.name, headers={"Cache-Control": "no-store"})


@router.get("/documents/{doc_id}/page/{n}.png")
def document_page(doc_id: int, n: int, con: Con, actor: Unlocked):
    d = _doc_or_404(con, doc_id, actor)
    if not 1 <= n <= min(d["pages"], store.MAX_PDF_PAGES):
        raise HTTPException(404, "errors.notFound")
    p = _file(d)
    log_access(con, d["profile_id"], actor, "view_document", f"document:{doc_id}:page:{n}")
    if d["mime"] != PDF:  # a photo is its own single page
        return FileResponse(p, media_type=d["mime"], headers={"Cache-Control": "no-store"})
    try:
        png = store.render_pdf_page(p, n)
    except IndexError:
        raise HTTPException(404, "errors.notFound") from None
    return Response(png, media_type="image/png", headers={"Cache-Control": "no-store"})


class Edit(BaseModel):
    value: float | None = None
    unit: str | None = None
    date: str | None = None


class Confirm(BaseModel):
    ids: list[int] = []
    edits: dict[int, Edit] = {}


@router.post("/documents/{doc_id}/observations/confirm", status_code=204)
def confirm_observations(doc_id: int, body: Confirm, con: Con, actor: Unlocked):
    d = _doc_or_404(con, doc_id, actor)
    own = {r[0] for r in con.execute("select id from observations where document_id=? and profile_id=?",
                                     (doc_id, d["profile_id"]))}
    if not (set(body.ids) | set(body.edits)) <= own:
        raise HTTPException(404, "errors.notFound")
    for e in body.edits.values():
        if e.date is not None:
            try:
                _date.fromisoformat(e.date)
            except ValueError:
                raise HTTPException(422, "date must be YYYY-MM-DD") from None
    try:
        for oid, e in body.edits.items():
            changes = {k: v for k, v in e.model_dump(exclude_unset=True).items() if not (k == "date" and v is None)}
            if changes:
                con.execute(f"update observations set {', '.join(f'{k}=?' for k in changes)} where id=?",
                            (*changes.values(), oid))
        con.executemany("update observations set status='confirmed' where id=?", [(i,) for i in body.ids])
        con.commit()
        log_access(con, d["profile_id"], actor, "confirm_observations", f"document:{doc_id}")
    except BaseException:
        con.rollback()
        raise


@router.delete("/documents/{doc_id}/observations/{oid}", status_code=204)
def reject_observation(doc_id: int, oid: int, con: Con, actor: Unlocked):
    """Drop a value the reader proposed and the person rejected. A confirmed value is record data: 409."""
    d = _doc_or_404(con, doc_id, actor)  # owner check via require_owner_of
    o = con.execute("select status from observations where id=? and document_id=? and profile_id=?",
                    (oid, doc_id, d["profile_id"])).fetchone()
    if o is None:
        raise HTTPException(404, "errors.notFound")
    if o["status"] != "proposed":
        raise HTTPException(409, "errors.alreadyConfirmed")
    con.execute("delete from observations where id=? and status='proposed'", (oid,))
    con.commit()
    log_access(con, d["profile_id"], actor, "reject_observation", f"document:{doc_id}:observation:{oid}")
    return Response(status_code=204)
