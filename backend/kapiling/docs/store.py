"""Original document files on disk, under data_dir/files/docs/<profile>/<random>/<original name>."""

import hashlib
import re
import uuid
from pathlib import Path, PurePath

from kapiling import config

MAX_PDF_PAGES = 30             # uploads with more pages are refused (413)
MAX_RENDER_PIXELS = 4_000_000  # a rendered page never exceeds about 4 megapixels, whatever its MediaBox says

EXT = {"image/jpeg": ".jpg", "image/png": ".png", "application/pdf": ".pdf"}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_stem(filename: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", PurePath(filename or "").stem).strip("._-")
    return stem[:80] or "document"


def write(profile_id: int, data: bytes, filename: str, mime: str) -> str:
    """Write the bytes and return the path relative to data_dir. The stem keeps the original name."""
    rel = f"files/docs/{profile_id}/{uuid.uuid4().hex[:12]}/{safe_stem(filename)}{EXT.get(mime, '')}"
    dest = config.settings.data_dir / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return rel


def path(rel: str) -> Path:
    """Absolute path of a stored file; raises FileNotFoundError if it escapes data_dir or is missing."""
    base = config.settings.data_dir.resolve()
    p = (base / rel).resolve()
    if not p.is_relative_to(base) or not p.is_file():
        raise FileNotFoundError(rel)
    return p


def remove(rel: str) -> None:
    p = config.settings.data_dir / rel
    p.unlink(missing_ok=True)
    try:
        p.parent.rmdir()
    except OSError:
        pass


def pdf_pages(data: bytes) -> int:
    """Page count of a PDF; raises ValueError if pypdfium2 cannot open it."""
    import pypdfium2 as pdfium

    try:
        pdf = pdfium.PdfDocument(data)
    except pdfium.PdfiumError as e:
        raise ValueError("not a readable PDF") from e
    try:
        return len(pdf)
    finally:
        pdf.close()


def pdf_has_text(p: Path) -> bool:
    """True if any page has a text layer (a scan has none)."""
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(p)
    try:
        return any(page.get_textpage().get_text_range().strip() for page in pdf)
    finally:
        pdf.close()


def render_scale(width_pt: float, height_pt: float, scale: float = 2.0) -> float:
    """The requested scale (1.0 = 72 dpi), lowered so the page stays under MAX_RENDER_PIXELS."""
    area = max(width_pt, 1.0) * max(height_pt, 1.0)
    return min(scale, (MAX_RENDER_PIXELS / area) ** 0.5)


def render_pdf_page(p: Path, n: int, scale: float = 2.0) -> bytes:
    """PNG of 1-based page n; raises IndexError if out of range."""
    import io

    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(p)
    try:
        if not 1 <= n <= len(pdf):
            raise IndexError(n)
        page = pdf[n - 1]
        w, h = page.get_size()
        img = page.render(scale=render_scale(w, h, scale)).to_pil()
        buf = io.BytesIO()
        img.save(buf, "PNG")
        return buf.getvalue()
    finally:
        pdf.close()
