import io
import json
import mimetypes
import sqlite3
import uuid
from datetime import date as _date
from typing import Annotated

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from PIL import Image
from pydantic import BaseModel, Field

from kapiling import config
from kapiling.auth.deps import Actor, require_owner_of, require_unlocked
from kapiling.auth.lock import log_access
from kapiling.db import get_con
from kapiling.records import repo
from kapiling.records.summary import emergency_card

router = APIRouter(prefix="/api")
Con = Annotated[sqlite3.Connection, Depends(get_con)]
Unlocked = Annotated[Actor, Depends(require_unlocked)]

CARD_KINDS = ("philhealth", "senior", "hmo", "pwd", "vaccination", "national_id", "other")
PROFILE_FIELDS = {"full_name", "nickname", "birth_date", "sex", "blood_type", "address", "phone",
                  "philhealth_no", "senior_id_no", "language"}


def _profile_or_404(con, pid: int):
    p = repo.get_profile(con, pid)
    if p is None:
        raise HTTPException(404, "Profile not found")
    return p


def _mask(number: str | None) -> str | None:
    if not number:
        return None
    digits = "".join(ch for ch in number if ch.isdigit())
    return "••••" + digits[-4:] if len(number) > 4 and digits else "••••"


def _card_json(c) -> dict:
    return {"id": c["id"], "kind": c["kind"], "label": c["label"], "number_masked": _mask(c["number"]),
            "front_url": f"/api/files/{c['id']}/front",
            "back_url": f"/api/files/{c['id']}/back" if c["back_path"] else None, "expires": c["expires"]}


def _row(r) -> dict:
    return dict(r)


def _safe_path(rel: str):
    base = config.settings.data_dir.resolve()
    p = (base / rel).resolve()
    if not p.is_relative_to(base) or not p.is_file():
        raise HTTPException(404, "File not found")
    return p


def _image(rel: str) -> FileResponse:
    p = _safe_path(rel)
    return FileResponse(p, media_type=mimetypes.guess_type(p.name)[0] or "application/octet-stream")


NO_STORE = {"Cache-Control": "no-store"}


@router.get("/profiles")
def profiles(con: Con):
    """Public: the lock screen's profile picker. has_biometric shows the biometric button (Task 15)."""
    from kapiling.auth.webauthn import has_biometric

    return [{"id": r["id"], "nickname": r["nickname"], "full_name": r["full_name"],
             "photo_url": f"/api/profiles/{r['id']}/photo" if r["photo_path"] else None,
             "has_biometric": has_biometric(con, r["id"])}
            for r in con.execute("select id, nickname, full_name, photo_path from profiles order by id")]


def _emergency_or_404(con, pid: int) -> dict:
    try:
        return emergency_card(con, pid)
    except KeyError:
        raise HTTPException(404, "Profile not found") from None


@router.get("/emergency/{pid}")
def emergency(pid: int, con: Con, response: Response):
    """Public by design (spec section 3): a responder must never meet a lock."""
    response.headers.update(NO_STORE)
    return _emergency_or_404(con, pid)


@router.get("/emergency/{pid}/qr.svg")
def emergency_qr(pid: int, con: Con):
    import qrcode
    import qrcode.image.svg

    text = _emergency_or_404(con, pid)["qr_text"]
    svg = qrcode.make(text, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=2).to_string()
    return Response(svg, media_type="image/svg+xml", headers=NO_STORE)


@router.get("/profiles/{pid}/photo")
def photo(pid: int, con: Con):
    p = repo.get_profile(con, pid)
    if p is None or not p["photo_path"]:
        raise HTTPException(404, "No photo")
    return _image(p["photo_path"])


@router.get("/profiles/{pid}/summary")
def summary(pid: int, con: Con, actor: Unlocked):
    p = _profile_or_404(con, pid)
    log_access(con, pid, actor, "view_summary", "summary")
    return {"profile": _row(p), "conditions": [_row(r) for r in repo.list_conditions(con, pid)],
            "allergies": [_row(r) for r in repo.list_allergies(con, pid)],
            "meds": [_row(r) for r in repo.list_meds(con, pid)],
            "latest": {k: _row(v) for k, v in repo.latest_observations(con, pid).items()},
            "contacts": [_row(r) for r in repo.list_contacts(con, pid)]}


@router.get("/profiles/{pid}")
def get_profile(pid: int, con: Con, _a: Unlocked):
    return _row(_profile_or_404(con, pid))


@router.put("/profiles/{pid}")
def put_profile(pid: int, con: Con, _a: Unlocked, body: dict = Body(...)):
    _profile_or_404(con, pid)
    changes = {k: v for k, v in body.items() if k in PROFILE_FIELDS}
    if "language" in changes and changes["language"] not in ("tl", "en"):
        raise HTTPException(422, "settings.invalidLanguage")
    if changes:
        con.execute(f"update profiles set {', '.join(f'{k}=?' for k in changes)} where id=?", (*changes.values(), pid))
        con.commit()
    return _row(repo.get_profile(con, pid))


@router.get("/profiles/{pid}/cards")
def cards(pid: int, con: Con, actor: Unlocked):
    _profile_or_404(con, pid)
    log_access(con, pid, actor, "view_cards", "cards")
    return [_card_json(c) for c in repo.list_cards(con, pid)]


MAX_UPLOAD = 10 * 1024 * 1024
_FORMATS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}
try:  # HEIC only when pillow-heif happens to be installed
    import pillow_heif

    pillow_heif.register_heif_opener()
    _FORMATS["HEIF"] = ".heic"
except ImportError:
    pass


def _read_image(up: UploadFile) -> tuple[bytes, str]:
    """Read and validate one upload; returns (bytes, extension). Nothing is written."""
    data = up.file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "errors.fileTooLarge")
    try:
        with Image.open(io.BytesIO(data)) as img:
            fmt = img.format
            img.verify()
    except Exception:
        raise HTTPException(415, "errors.unsupportedImage") from None
    if fmt not in _FORMATS:
        raise HTTPException(415, "errors.unsupportedImage")
    return data, _FORMATS[fmt]


def _write(data: bytes, ext: str, pid: int, stem: str) -> str:
    rel = f"files/cards/{pid}-{stem}-{uuid.uuid4().hex[:8]}{ext}"
    dest = config.settings.data_dir / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return rel


@router.post("/profiles/{pid}/cards")
def add_card(pid: int, con: Con, _a: Unlocked, kind: Annotated[str, Form()], label: Annotated[str, Form()],
                   front: Annotated[UploadFile, File()], number: Annotated[str | None, Form()] = None,
                   back: Annotated[UploadFile | None, File()] = None):
    _profile_or_404(con, pid)
    if kind not in CARD_KINDS:
        raise HTTPException(422, f"kind must be one of {', '.join(CARD_KINDS)}")
    front_img = _read_image(front)
    back_img = _read_image(back) if back is not None and back.filename else None
    written: list[str] = []
    try:
        front_path = _write(*front_img, pid, "front")
        written.append(front_path)
        back_path = None
        if back_img:
            back_path = _write(*back_img, pid, "back")
            written.append(back_path)
        sort = con.execute("select coalesce(max(sort), -1) + 1 from cards where profile_id=?", (pid,)).fetchone()[0]
        cur = con.execute("insert into cards (profile_id, kind, label, number, front_path, back_path, sort) values (?,?,?,?,?,?,?)",
                          (pid, kind, label, number or None, front_path, back_path, sort))
        con.commit()
    except Exception:
        con.rollback()
        for rel in written:
            (config.settings.data_dir / rel).unlink(missing_ok=True)
        raise
    return _card_json(con.execute("select * from cards where id=?", (cur.lastrowid,)).fetchone())


@router.get("/files/{card_id}/{side}")
def card_file(card_id: int, side: str, con: Con, actor: Unlocked):
    c = con.execute("select * from cards where id=?", (card_id,)).fetchone()
    if c is None:
        raise HTTPException(404, "Card image not found")
    require_owner_of(actor, c["profile_id"])  # no {pid} in this path, so the dependency cannot check it
    path = c[f"{side}_path"] if side in ("front", "back") else None
    if not path:
        raise HTTPException(404, "Card image not found")
    resp = _image(path)
    log_access(con, c["profile_id"], actor, "view_cards", f"card:{card_id}:{side}")
    return resp


class Dose(BaseModel):
    date: str
    slot: str


@router.get("/profiles/{pid}/meds")
def meds(pid: int, con: Con, _a: Unlocked, date: str | None = None):
    _profile_or_404(con, pid)
    return {"meds": [_row(m) for m in repo.list_meds(con, pid)],
            "today": repo.meds_today(con, pid, date or _date.today().isoformat())}


def _owned_med(con, pid: int, mid: int) -> None:
    if con.execute("select 1 from medications where id=? and profile_id=?", (mid, pid)).fetchone() is None:
        raise HTTPException(404, "Medicine not found")


@router.post("/profiles/{pid}/meds/{mid}/taken", status_code=204)
def taken(pid: int, mid: int, body: Dose, con: Con, _a: Unlocked):
    _owned_med(con, pid, mid)
    repo.mark_taken(con, mid, body.date, body.slot)


@router.delete("/profiles/{pid}/meds/{mid}/taken", status_code=204)
def untaken(pid: int, mid: int, body: Dose, con: Con, _a: Unlocked):
    _owned_med(con, pid, mid)
    repo.unmark_taken(con, mid, body.date, body.slot)


@router.get("/profiles/{pid}/timeline")
def timeline(pid: int, con: Con, _a: Unlocked, kind: str | None = None):
    _profile_or_404(con, pid)
    return repo.timeline(con, pid, kind)


@router.get("/profiles/{pid}/observations")
def observations(pid: int, con: Con, _a: Unlocked, code: str | None = None):
    _profile_or_404(con, pid)
    return [_row(o) for o in repo.observations(con, pid, code)]


# --- Task 15: emergency card fields, family history and contacts -----------------------------------

class EmergencyFieldsBody(BaseModel):
    fields: list[str]


@router.put("/profiles/{pid}/emergency-fields")
def put_emergency_fields(pid: int, body: EmergencyFieldsBody, con: Con, actor: Unlocked):
    from kapiling.records.summary import _DEFAULT_FIELDS

    if not set(body.fields) <= set(_DEFAULT_FIELDS):
        raise HTTPException(422, "Unknown emergency card field")
    fields = [f for f in _DEFAULT_FIELDS if f in body.fields]
    con.execute("insert into emergency_fields (profile_id, fields) values (?, ?) "
                "on conflict(profile_id) do update set fields=excluded.fields", (pid, json.dumps(fields)))
    con.commit()
    log_access(con, pid, actor, "change_emergency_fields", ",".join(fields))
    return {"fields": fields}


class FamilyBody(BaseModel):
    relation: str = Field(min_length=1, max_length=40)
    condition: str = Field(min_length=1, max_length=120)


@router.get("/profiles/{pid}/family-history")
def family_history(pid: int, con: Con, _a: Unlocked):
    return [_row(r) for r in con.execute(
        "select id, relation, condition from family_history where profile_id=? order by id", (pid,))]


@router.post("/profiles/{pid}/family-history", status_code=201)
def add_family_history(pid: int, body: FamilyBody, con: Con, _a: Unlocked):
    _profile_or_404(con, pid)
    cur = con.execute("insert into family_history (profile_id, relation, condition) values (?,?,?)",
                      (pid, body.relation.strip(), body.condition.strip()))
    con.commit()
    return _row(con.execute("select id, relation, condition from family_history where id=?", (cur.lastrowid,)).fetchone())


@router.delete("/profiles/{pid}/family-history/{fid}", status_code=204)
def delete_family_history(pid: int, fid: int, con: Con, _a: Unlocked):
    if con.execute("delete from family_history where id=? and profile_id=?", (fid, pid)).rowcount == 0:
        raise HTTPException(404, "errors.notFound")
    con.commit()


class ContactBody(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    relation: str | None = Field(default=None, max_length=40)
    phone: str = Field(min_length=3, max_length=30)
    is_emergency: bool = True


@router.post("/profiles/{pid}/contacts", status_code=201)
def add_contact(pid: int, body: ContactBody, con: Con, _a: Unlocked):
    _profile_or_404(con, pid)
    cur = con.execute("insert into contacts (profile_id, name, relation, phone, is_emergency) values (?,?,?,?,?)",
                      (pid, body.name.strip(), (body.relation or "").strip() or None, body.phone.strip(),
                       int(body.is_emergency)))
    con.commit()
    return _row(con.execute("select * from contacts where id=?", (cur.lastrowid,)).fetchone())


@router.delete("/profiles/{pid}/contacts/{cid}", status_code=204)
def delete_contact(pid: int, cid: int, con: Con, _a: Unlocked):
    if con.execute("delete from contacts where id=? and profile_id=?", (cid, pid)).rowcount == 0:
        raise HTTPException(404, "errors.notFound")
    con.commit()
