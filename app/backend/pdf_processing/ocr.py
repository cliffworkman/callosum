"""Local OCR for scanned / image-only PDFs (inc 231, backlog B3).

A scanned PDF imports today with **zero chunks** (no text layer) → it's invisible to search, embeddings, synthesis,
and citation. This renders each page to an image (PyMuPDF), runs the local **Tesseract** binary to produce a
*searchable PDF* (the page image with an invisible, correctly-positioned OCR text layer), and merges the pages into
one PDF. The caller then attaches that searchable copy and extracts it through the **normal** pipeline
(``attach_pdf_to_paper`` → ``extract_pdf``) — so the paper becomes fully first-class: searchable, embeddable, and
citable with **exact** highlight boxes + selectable text, with **no change to the coordinate-honesty / quote-location
code** (it reads the real text layer Tesseract embedded). Rebuilding the pages from upright rasters also means the
searchable copy has no page rotation, so the overlay never hits its rotated-page skip.

No new pip dependency: Tesseract is a *system binary* invoked via ``shutil.which`` + fail-closed ``subprocess.run``
(the Node/esbuild/citeproc pattern; the cloudflared precedent). PyMuPDF (already pinned) renders the page image and
merges the PDFs — no Pillow. Fully **local — no network egress** (like statcheck), NOT the Gemini gate.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import fitz

# Where to look for the tesseract binary when it isn't on PATH. The UB-Mannheim Windows installer (the one `winget
# install UB-Mannheim.TesseractOCR` uses) does NOT add itself to PATH by default, so `shutil.which` misses it even
# though it's installed; Homebrew/apt usually do add it. Override with the CALLOSUM_TESSERACT_PATH env var.
_COMMON_TESSERACT_PATHS = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    "/opt/homebrew/bin/tesseract",
    "/usr/local/bin/tesseract",
    "/usr/bin/tesseract",
)

OCR_DPI = 300  # standard OCR resolution
OCR_LANG = "eng"
MAX_OCR_PAGES = 200  # defensive cap on pages OCR'd in one run (rule #4)
TESSERACT_TIMEOUT_S = 180  # per-page subprocess timeout (rule #4)
OCR_IMPORT_SOURCE = "ocr"  # the attachment's import_source marks the searchable copy as OCR-produced (provenance)

# (page PNG bytes, language) -> a single-page searchable PDF's bytes. Injectable so tests never need the binary.
PdfPageRunner = Callable[[bytes, str], bytes]


class TesseractUnavailable(RuntimeError):
    """The ``tesseract`` binary isn't on PATH. Mirrors ``CitationEngineUnavailable`` — the feature degrades
    gracefully (the job fails with an install hint; the app never crashes)."""


def tesseract_exe() -> str | None:
    """Resolve the tesseract binary path: ``CALLOSUM_TESSERACT_PATH`` env override, then PATH (``shutil.which``),
    then the common install locations (so an installed-but-not-on-PATH Tesseract still works). None if not found."""
    override = os.environ.get("CALLOSUM_TESSERACT_PATH")
    if override and Path(override).is_file():
        return override
    found = shutil.which("tesseract")
    if found:
        return found
    for candidate in _COMMON_TESSERACT_PATHS:
        if Path(candidate).is_file():
            return candidate
    return None


def tesseract_available() -> bool:
    return tesseract_exe() is not None


def _default_page_runner(png: bytes, lang: str) -> bytes:
    """Run the local Tesseract binary over one page image → a single-page searchable PDF (image + text layer).

    Fixed argv; the image is piped via **stdin** and the PDF read from **stdout** — no client-supplied path ever
    reaches the command line. Fail-closed: a missing binary raises ``TesseractUnavailable``; a non-zero exit raises."""
    exe = tesseract_exe()
    if exe is None:
        raise TesseractUnavailable(
            "Tesseract OCR could not be found. Install it (e.g. `winget install UB-Mannheim.TesseractOCR` on Windows, "
            "`brew install tesseract` on macOS, `apt install tesseract-ocr` on Linux) and restart callosum. If it is "
            "installed in a non-standard location, set the CALLOSUM_TESSERACT_PATH environment variable to its path."
        )
    proc = subprocess.run(
        [exe, "stdin", "stdout", "-l", lang, "pdf"],
        input=png,
        capture_output=True,
        timeout=TESSERACT_TIMEOUT_S,
    )
    if proc.returncode != 0 or not proc.stdout:
        detail = proc.stderr.decode("utf-8", "replace").strip()[:200]
        raise RuntimeError(f"tesseract failed (rc={proc.returncode}): {detail}")
    return proc.stdout


def make_searchable_pdf(
    src_pdf_path: str | Path,
    out_pdf_path: str | Path,
    *,
    dpi: int = OCR_DPI,
    lang: str = OCR_LANG,
    runner: PdfPageRunner = _default_page_runner,
    on_progress: Callable[[int, int], None] | None = None,
) -> int:
    """Render each page of ``src_pdf_path`` to an image, OCR it into a single-page searchable PDF via ``runner``,
    merge the pages, and save to ``out_pdf_path``. Returns the page count.

    ``runner`` is injectable so tests never need the Tesseract binary. Bounded to ``MAX_OCR_PAGES`` (rule #4)."""
    out = fitz.open()
    pages = 0
    try:
        with fitz.open(src_pdf_path) as src:
            total = min(src.page_count, MAX_OCR_PAGES)
            for index in range(total):
                if on_progress:
                    on_progress(index + 1, total)
                png = src[index].get_pixmap(dpi=dpi).tobytes("png")
                page_pdf = runner(png, lang)
                with fitz.open(stream=page_pdf, filetype="pdf") as page_doc:
                    out.insert_pdf(page_doc)
                pages += 1
        if pages == 0:
            raise RuntimeError("OCR produced no pages (the source PDF has no pages).")
        out.save(str(out_pdf_path), garbage=3, deflate=True)
    finally:
        out.close()
    return pages
