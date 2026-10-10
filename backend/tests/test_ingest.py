import asyncio
import json
from pathlib import Path

import httpx
import pytest

from kapiling.docs import index, ingest, vision
from kapiling.docs.ingest import embed_text, enqueue, process_one
from kapiling.records import repo

FIXTURES = Path(__file__).parent / "fixtures"
FIXTURE_MD = (FIXTURES / "lab_fbs.md").read_text()
FIXTURE_IMG = (Path(__file__).parent.parent / "seed" / "assets" / "lab_fbs_hba1c.jpg").read_bytes()
TITLE = "FBS and HbA1c — 2026-03-02"

EXTRACTION = {
    "title": "Clinical Chemistry", "kind": "lab", "date": "2026-03-02", "facility": "Marikina Valley Diagnostic Center",
    "observations": [
        {"code": "fbs", "label": "Fasting Blood Sugar", "value": "130", "value_text": None, "unit": "mg/dL",
         "ref_low": 70, "ref_high": 100, "date": "2026-03-02", "facility": "Marikina Valley Diagnostic Center"},
        {"code": "hba1c", "label": "Hemoglobin A1c (HbA1c)", "value": 7.2, "value_text": None, "unit": "%",
         "ref_low": 4.0, "ref_high": 5.6, "date": "2026-03-02", "facility": None},
        {"code": "glucose_random", "label": "Random Glucose", "value": "n/a", "value_text": "see note", "unit": "mg/dL",
         "ref_low": None, "ref_high": None, "date": "03/02/2026", "facility": None},
    ],
}


class FakeModels:
    def __init__(self):
        self.embed_calls = 0
        self.embed_inputs: list[list[str]] = []
        self.vision_payloads: list[dict] = []

    async def vision_post(self, url, payload, timeout):
        self.vision_payloads.append(payload)
        content = json.dumps(EXTRACTION) if "response_format" in payload else FIXTURE_MD
        return {"choices": [{"message": {"content": content}}]}

    async def embed_post(self, payload):
        self.embed_calls += 1
        self.embed_inputs.append(payload["input"])
        return {"data": [{"index": i, "embedding": [1.0 / (i + 1)] * 1024} for i in range(len(payload["input"]))]}


@pytest.fixture
def fake_models(monkeypatch):
    fm = FakeModels()
    monkeypatch.setattr(vision, "_post", fm.vision_post)
    monkeypatch.setattr(ingest, "_embed_post", fm.embed_post)
    return fm


@pytest.fixture
def failing_vision(monkeypatch, fake_models):
    async def boom(url, payload, timeout):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(vision, "_post", boom)
    return fake_models


def _ingest(con, lola, data=FIXTURE_IMG, title=TITLE, kind="lab"):
    did = enqueue(con, lola, data, "fbs.jpg", "image/jpeg", title, kind)
    asyncio.run(process_one(con, did))
    return did


def test_embed_text_drops_repeated_title_and_uses_no_labels():
    s = embed_text("FBS 2026-03-02", ["Results"], "FBS 2026-03-02\nGlucose 132 mg/dL")
    assert s == "FBS 2026-03-02\nResults\nGlucose 132 mg/dL" and "title:" not in s


def test_markdown_lab_is_chunked_with_heading_path(con, lola, fake_models):
    did = enqueue(con, lola, FIXTURE_IMG, "fbs.jpg", "image/jpeg", "FBS and HbA1c — 2026-03-02", "lab")
    asyncio.run(process_one(con, did))
    rows = con.execute("select text, meta from chunks where document_id=?", (did,)).fetchall()
    assert rows and all(json.loads(r["meta"])["title"].startswith("FBS") for r in rows)
    assert con.execute("select count(*) from chunks_vec where document_id=?", (did,)).fetchone()[0] == len(rows)
    assert con.execute("select status from documents where id=?", (did,)).fetchone()[0] == "indexed"
    metas = [json.loads(r["meta"]) for r in rows]
    assert ["Marikina Valley Diagnostic Center", "Results"] in [m["headings"] for m in metas]
    assert all(m["page"] == 1 for m in metas)
    results = next(r["text"] for r, m in zip(rows, metas) if m["headings"][-1] == "Results")
    assert "130" in results and "7.2" in results
    # FTS is populated from the same rows, and vectors carry the profile partition
    assert con.execute("select count(*) from chunks_fts where chunks_fts match 'hemoglobin'").fetchone()[0] == 1
    assert {r[0] for r in con.execute("select profile_id from chunks_vec where document_id=?", (did,))} == {lola}
    assert con.execute("select transcript_md from documents where id=?", (did,)).fetchone()[0] == FIXTURE_MD


def test_stored_text_is_bare_not_templated(con, lola, fake_models):
    did = _ingest(con, lola)
    rows = con.execute("select text, content_hash from chunks where document_id=? order by ord", (did,)).fetchall()
    assert rows
    for r in rows:
        assert not r["text"].startswith(TITLE)
        assert "Marikina Valley Diagnostic Center\n" not in r["text"]  # heading path is not in the stored text
    embedded = fake_models.embed_inputs[0]
    assert all(e.startswith(TITLE + "\n") for e in embedded)
    assert [r["text"] for r in rows] != embedded
    assert len({r["content_hash"] for r in rows}) == len(rows)


def test_embeddings_are_one_batched_call(con, lola, fake_models):
    did = _ingest(con, lola)
    n = con.execute("select count(*) from chunks where document_id=?", (did,)).fetchone()[0]
    assert n >= 3
    assert fake_models.embed_calls == 1 and len(fake_models.embed_inputs[0]) == n


def test_duplicate_upload_returns_existing_id(con, lola):
    a = enqueue(con, lola, b"x", "a.jpg", "image/jpeg", None, None); b = enqueue(con, lola, b"x", "b.jpg", "image/jpeg", None, None)
    assert a == b


def test_duplicate_upload_is_per_profile(con, lola, mika):
    assert enqueue(con, lola, b"x", "a.jpg", "image/jpeg", None, None) != enqueue(con, mika, b"x", "a.jpg", "image/jpeg", None, None)


def test_extracted_values_are_proposed_until_confirmed(con, lola, fake_models, client, lola_unlocked):
    did = _ingest(con, lola)
    obs = con.execute("select * from observations where document_id=? order by id", (did,)).fetchall()
    assert [o["status"] for o in obs] == ["proposed"] * 3
    by_code = {o["code"]: o for o in obs}
    assert by_code["fbs"]["value"] == 130.0 and by_code["fbs"]["ref_high"] == 100.0
    assert by_code["hba1c"]["facility"] == "Marikina Valley Diagnostic Center"  # falls back to the document's facility
    other = by_code["other:Random Glucose"]  # unknown code
    assert other["value"] is None and other["value_text"] == "see note"
    assert other["date"] == "2026-03-02"  # an unparseable date falls back to the document date
    # the summary's "latest" ignores proposed values: seeded latest FBS is 132 (2026-07-07)
    assert repo.latest_observations(con, lola)["fbs"]["value"] == 132
    fbs_id, hba_id = by_code["fbs"]["id"], by_code["hba1c"]["id"]
    r = client.post(f"/api/documents/{did}/observations/confirm",
                    json={"ids": [fbs_id, hba_id], "edits": {str(hba_id): {"value": 7.3, "unit": "%", "date": "2026-03-03"}}})
    assert r.status_code == 204, r.text
    st = {o["id"]: o for o in con.execute("select * from observations where document_id=?", (did,))}
    assert st[fbs_id]["status"] == "confirmed" and st[hba_id]["status"] == "confirmed"
    assert st[hba_id]["value"] == 7.3 and st[hba_id]["date"] == "2026-03-03"
    assert st[other["id"]]["status"] == "proposed"
    assert [o["value"] for o in repo.observations(con, lola, "hba1c")][-1] == 7.3


def test_confirm_rejects_bad_date(con, lola, fake_models, client, lola_unlocked):
    did = _ingest(con, lola)
    oid = con.execute("select id from observations where document_id=?", (did,)).fetchone()[0]
    r = client.post(f"/api/documents/{did}/observations/confirm", json={"ids": [oid], "edits": {str(oid): {"date": "soon"}}})
    assert r.status_code == 422
    assert con.execute("select status from observations where id=?", (oid,)).fetchone()[0] == "proposed"


def test_failure_marks_document_failed_with_reason(con, lola, failing_vision):
    did = _ingest(con, lola)
    doc = con.execute("select status, error from documents where id=?", (did,)).fetchone()
    assert (doc["status"], doc["error"]) == ("failed", "vision_unavailable")
    assert con.execute("select count(*) from chunks where document_id=?", (did,)).fetchone()[0] == 0
    assert con.execute("select count(*) from chunks_vec where document_id=?", (did,)).fetchone()[0] == 0
    assert con.execute("select count(*) from observations where document_id=?", (did,)).fetchone()[0] == 0
    assert failing_vision.embed_calls == 0


def test_failed_embedding_leaves_no_partial_rows(con, lola, fake_models, monkeypatch):
    async def down(payload):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(ingest, "_embed_post", down)
    did = _ingest(con, lola)
    doc = con.execute("select status, error from documents where id=?", (did,)).fetchone()
    assert (doc["status"], doc["error"]) == ("failed", "embed_unavailable")
    assert con.execute("select count(*) from chunks where document_id=?", (did,)).fetchone()[0] == 0


def test_cancellation_is_reraised(con, lola, fake_models, monkeypatch):
    async def cancelled(url, payload, timeout):
        raise asyncio.CancelledError

    monkeypatch.setattr(vision, "_post", cancelled)
    did = enqueue(con, lola, FIXTURE_IMG, "fbs.jpg", "image/jpeg", TITLE, "lab")
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(process_one(con, did))


def test_reindex_replaces_chunks_atomically(con, lola, fake_models):
    did = _ingest(con, lola)
    first = con.execute("select count(*) from chunks where document_id=?", (did,)).fetchone()[0]
    asyncio.run(process_one(con, did))
    assert con.execute("select count(*) from chunks where document_id=?", (did,)).fetchone()[0] == first
    assert con.execute("select count(*) from chunks_vec where document_id=?", (did,)).fetchone()[0] == first
    assert con.execute("select count(*) from chunks_fts where chunks_fts match 'hemoglobin'").fetchone()[0] == 1
    assert con.execute("select count(*) from observations where document_id=?", (did,)).fetchone()[0] == 3
    # a failing write rolls back to the previous set of chunks
    rows = con.execute("select id from chunks where document_id=? order by id", (did,)).fetchall()
    with pytest.raises(ValueError):
        index.write_chunks(con, did, lola, [], [[0.0] * 1024])  # mismatched lengths
    assert con.execute("select id from chunks where document_id=? order by id", (did,)).fetchall() == rows


def test_delete_document_clears_index(con, lola, fake_models):
    did = _ingest(con, lola)
    index.delete_document(con, did)
    for t in ("chunks", "chunks_vec"):
        assert con.execute(f"select count(*) from {t} where document_id=?", (did,)).fetchone()[0] == 0
    assert con.execute("select count(*) from chunks_fts where chunks_fts match 'hemoglobin'").fetchone()[0] == 0


def test_metadata_is_filled_when_user_gave_none(con, lola, fake_models):
    did = _ingest(con, lola, title=None, kind=None)
    doc = con.execute("select * from documents where id=?", (did,)).fetchone()
    assert (doc["title"], doc["kind"], doc["date"], doc["facility"]) == (
        "Clinical Chemistry", "lab", "2026-03-02", "Marikina Valley Diagnostic Center")


def test_user_metadata_is_kept(con, lola, fake_models):
    did = _ingest(con, lola, title="My sugar test", kind="record")
    doc = con.execute("select title, kind from documents where id=?", (did,)).fetchone()
    assert (doc["title"], doc["kind"]) == ("My sugar test", "record")


def test_vision_payloads(con, lola, fake_models):
    _ingest(con, lola)
    transcribe, extract = fake_models.vision_payloads
    assert transcribe["temperature"] == 0 and extract["temperature"] == 0
    parts = transcribe["messages"][0]["content"]
    assert any(p.get("type") == "image_url" and p["image_url"]["url"].startswith("data:image/jpeg;base64,") for p in parts)
    schema = extract["response_format"]["json_schema"]["schema"]
    assert extract["response_format"]["type"] == "json_schema"
    assert "fbs" in schema["properties"]["observations"]["items"]["properties"]["code"]["enum"]


def test_run_pending_processes_oldest_queued(con, lola, fake_models, monkeypatch):
    a = enqueue(con, lola, FIXTURE_IMG, "a.jpg", "image/jpeg", TITLE, "lab")
    b = enqueue(con, lola, FIXTURE_IMG + b"\0", "b.jpg", "image/jpeg", TITLE, "lab")
    con.execute("update documents set status='reading' where id=?", (b,))  # left over from a crash
    con.commit()

    async def main():
        task = asyncio.create_task(ingest.run_pending(con, poll=0.01))
        for _ in range(500):
            await asyncio.sleep(0.02)
            if con.execute("select count(*) from documents where status='indexed'").fetchone()[0] == 2:
                break
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(main())
    assert [r[0] for r in con.execute("select status from documents where id in (?,?) order by id", (a, b))] == ["indexed"] * 2


# --- routes ------------------------------------------------------------------

def _pdf_bytes() -> bytes:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument.new()
    pdf.new_page(595, 842)
    pdf.new_page(595, 842)
    import io
    buf = io.BytesIO()
    pdf.save(buf)
    return buf.getvalue()


def test_upload_image_and_list(client, con, lola_unlocked):
    r = client.post(f"/api/profiles/{lola_unlocked}/documents", files={"file": ("fbs.jpg", FIXTURE_IMG, "application/octet-stream")},
                    data={"title": TITLE, "kind": "lab"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "queued"
    doc = con.execute("select * from documents where id=?", (body["id"],)).fetchone()
    assert doc["mime"] == "image/jpeg" and doc["pages"] == 1 and doc["profile_id"] == lola_unlocked
    again = client.post(f"/api/profiles/{lola_unlocked}/documents", files={"file": ("other.jpg", FIXTURE_IMG, "image/jpeg")})
    assert again.json()["id"] == body["id"]
    listed = client.get(f"/api/profiles/{lola_unlocked}/documents").json()
    assert [d["id"] for d in listed] == [body["id"]] and listed[0]["title"] == TITLE


def test_upload_pdf_counts_pages(client, con, lola_unlocked):
    r = client.post(f"/api/profiles/{lola_unlocked}/documents", files={"file": ("x.pdf", _pdf_bytes(), "image/png")})
    assert r.status_code == 200, r.text
    doc = con.execute("select * from documents where id=?", (r.json()["id"],)).fetchone()
    assert doc["mime"] == "application/pdf" and doc["pages"] == 2
    png = client.get(f"/api/documents/{doc['id']}/page/2.png")
    assert png.status_code == 200 and png.content.startswith(b"\x89PNG")
    assert client.get(f"/api/documents/{doc['id']}/page/3.png").status_code == 404


def test_upload_rejects_unsupported_and_large(client, lola_unlocked, monkeypatch):
    from kapiling.docs import routes

    url = f"/api/profiles/{lola_unlocked}/documents"
    r = client.post(url, files={"file": ("x.pdf", b"hello, not a pdf", "application/pdf")})
    assert r.status_code == 415 and r.json()["detail"] == "errors.fileType"
    assert client.post(url, files={"file": ("x.pdf", b"%PDF-1.4 broken", "application/pdf")}).status_code == 415
    monkeypatch.setattr(routes, "MAX_UPLOAD", 1000)
    r = client.post(url, files={"file": ("big.jpg", FIXTURE_IMG, "image/jpeg")})
    assert r.status_code == 413 and r.json()["detail"] == "errors.fileTooBig"
    r = client.post(url, files={"file": ("a.jpg", FIXTURE_IMG[:500], "image/jpeg")})  # truncated image
    assert r.status_code == 415


def test_upload_rejects_bad_kind(client, lola_unlocked):
    r = client.post(f"/api/profiles/{lola_unlocked}/documents", files={"file": ("fbs.jpg", FIXTURE_IMG, "image/jpeg")},
                    data={"kind": "bogus"})
    assert r.status_code == 422


def test_png_upload_is_kept_and_webp_converted(client, con, lola_unlocked):
    import io

    from PIL import Image

    def enc(fmt):
        buf = io.BytesIO()
        Image.new("RGB", (40, 30), (200, 10, 10) if fmt == "PNG" else (10, 200, 10)).save(buf, fmt)
        return buf.getvalue()

    url = f"/api/profiles/{lola_unlocked}/documents"
    p = con.execute("select mime from documents where id=?", (client.post(url, files={"file": ("a.png", enc("PNG"))}).json()["id"],)).fetchone()
    w = con.execute("select mime from documents where id=?", (client.post(url, files={"file": ("a.webp", enc("WEBP"))}).json()["id"],)).fetchone()
    assert (p[0], w[0]) == ("image/png", "image/jpeg")


def test_document_routes_and_access_log(client, con, lola, fake_models, lola_unlocked):
    did = _ingest(con, lola)
    meta = client.get(f"/api/documents/{did}")
    assert meta.status_code == 200
    body = meta.json()
    assert body["status"] == "indexed" and body["transcript_md"] == FIXTURE_MD and len(body["observations"]) == 3
    assert body["page_urls"] == [f"/api/documents/{did}/page/1.png"]
    f = client.get(f"/api/documents/{did}/file")
    assert f.status_code == 200 and f.content == FIXTURE_IMG
    page = client.get(f"/api/documents/{did}/page/1.png")
    assert page.status_code == 200 and page.content == FIXTURE_IMG
    assert client.get(f"/api/documents/{did}/page/2.png").status_code == 404
    logged = [r[0] for r in con.execute("select target from access_log where action='view_document' order by id")]
    assert logged == [f"document:{did}", f"document:{did}:file", f"document:{did}:page:1"]
    assert client.get("/api/documents/99999").status_code == 404


def test_document_routes_are_locked_and_owner_checked(client, con, lola, fake_models, mika_unlocked):
    did = _ingest(con, lola)
    for path in (f"/api/documents/{did}", f"/api/documents/{did}/file", f"/api/documents/{did}/page/1.png"):
        assert client.get(path).status_code == 403, path
    assert client.post(f"/api/documents/{did}/observations/confirm", json={"ids": [], "edits": {}}).status_code == 403
    assert client.get(f"/api/profiles/{lola}/documents").status_code == 403
    client.post("/api/lock")
    assert client.get(f"/api/documents/{did}").status_code == 401


def test_confirm_ignores_other_documents_observations(con, lola, fake_models, client, lola_unlocked):
    did = _ingest(con, lola)
    seeded = con.execute("select id from observations where document_id is null limit 1").fetchone()[0]
    con.execute("update observations set status='proposed' where id=?", (seeded,))
    con.commit()
    r = client.post(f"/api/documents/{did}/observations/confirm", json={"ids": [seeded], "edits": {}})
    assert r.status_code == 404
    assert con.execute("select status from observations where id=?", (seeded,)).fetchone()[0] == "proposed"


def test_worker_does_not_start_under_tests(client):
    from kapiling import main

    assert main.worker_task is None


# --- PDFs ----------------------------------------------------------------------

def _text_pdf(lines: list[str]) -> bytes:
    """A one-page PDF with a real text layer (Helvetica), built by hand."""
    content = "BT /F1 14 Tf 72 760 Td " + " ".join(f"({ln}) Tj 0 -24 Td" for ln in lines) + " ET"
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            f"<< /Length {len(content)} >>\nstream\n{content}\nendstream", "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offs = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode() + b"".join(f"{o:010d} 00000 n \n".encode() for o in offs)
    return out + f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()


def test_text_pdf_goes_through_docling_with_page_and_bbox(con, lola, fake_models):
    data = _text_pdf(["Marikina Valley Diagnostic Center", "Creatinine 0.9 mg/dL 0.6 - 1.1"])
    did = enqueue(con, lola, data, "renal.pdf", "application/pdf", "Renal function", "lab")
    asyncio.run(process_one(con, did))
    doc = con.execute("select status, transcript_md from documents where id=?", (did,)).fetchone()
    assert doc["status"] == "indexed" and "Creatinine 0.9" in doc["transcript_md"]
    metas = [json.loads(r[0]) for r in con.execute("select meta from chunks where document_id=?", (did,))]
    assert metas and metas[0]["page"] == 1 and len(metas[0]["bbox"]) == 4
    # only the extraction call went to the vision server: the text layer needed no transcription
    assert [("response_format" in p) for p in fake_models.vision_payloads] == [True]


def test_scanned_pdf_is_transcribed_page_by_page(con, lola, fake_models):
    import io

    from PIL import Image

    img = Image.open(io.BytesIO(FIXTURE_IMG)).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, "PDF", save_all=True, append_images=[img.copy()])
    did = enqueue(con, lola, buf.getvalue(), "scan.pdf", "application/pdf", TITLE, "lab")
    asyncio.run(process_one(con, did))
    assert con.execute("select status from documents where id=?", (did,)).fetchone()[0] == "indexed"
    transcribes = [p for p in fake_models.vision_payloads if "response_format" not in p]
    assert len(transcribes) == 2
    assert transcribes[0]["messages"][0]["content"][0]["image_url"]["url"].startswith("data:image/png;base64,")
    pages = {json.loads(r[0])["page"] for r in con.execute("select meta from chunks where document_id=?", (did,))}
    assert pages == {1, 2}


def test_validate_drops_text_copy_of_a_number():
    # live check: the model echoed the unit into value_text next to a numeric value
    o = vision.validate({"code": "fbs", "label": "FBS", "value": 130, "value_text": "mg/dL", "unit": "mg/dL",
                         "ref_low": None, "ref_high": "100", "date": "2026-03-02", "facility": None})
    assert (o["value"], o["value_text"], o["ref_high"]) == (130.0, None, 100.0)
    assert vision.validate({"code": "x", "label": "", "value": 1}) is None


@pytest.mark.parametrize("code,label,expected", [
    ("hemoglobin", "Hematocrit", "other:Hematocrit"),        # live check: the model reused 'hemoglobin' for a CBC
    ("hemoglobin", "Platelet count", "other:Platelet count"),
    ("hemoglobin", "Hemoglobin A1c (HbA1c)", "other:Hemoglobin A1c (HbA1c)"),
    ("hemoglobin", "Hemoglobin", "hemoglobin"),
    ("fbs", "Fasting Blood Sugar", "fbs"),
    ("hba1c", "Hemoglobin A1c (HbA1c)", "hba1c"),
    ("total_chol", "Total Cholesterol", "total_chol"),
    ("ldl", "HDL Cholesterol", "other:HDL Cholesterol"),
    ("bp_systolic", "BP", "bp_systolic"),
    ("creatinine", "Blood Urea Nitrogen", "other:Blood Urea Nitrogen"),
])
def test_known_code_must_match_its_label(code, label, expected):
    o = vision.validate({"code": code, "label": label, "value": 1.0})
    assert o["code"] == expected


def test_known_code_needs_a_number():
    # live check: the discharge summary's "uncontrolled" came back as an HbA1c observation
    o = vision.validate({"code": "hba1c", "label": "HbA1c", "value": None, "value_text": "uncontrolled"})
    assert (o["code"], o["value_text"]) == ("other:HbA1c", "uncontrolled")
