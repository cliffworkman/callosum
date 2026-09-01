"""Tests for the literature-acquisition clean lane (Increment A) — registry seam, fetch/validate/import,
and the managed-filename convention. Hermetic: injected fetchers, no real network.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import fitz
import httpx
import pytest
from sqlalchemy import select

import app.backend.acquisition.fetch as fetch_mod
from app.backend.acquisition.fetch import (
    OaFetchError,
    download_oa_pdf,
    import_oa_pdf,
    library_filename_for,
)
from app.backend.acquisition.registry import OaLocation, PaperRef, ResolverRegistry
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper
from app.backend.persistence.schema import attachments


def _minimal_pdf_bytes() -> bytes:
    doc = fitz.open()
    doc.new_page()
    data = doc.tobytes()
    doc.close()
    return data


def _paper(**kw):
    base = {"csl_json": {}, "year": None, "venue": None, "title": None, "first_author_family_name": None}
    base.update(kw)
    return base


# --- Structural OA-only guarantees (the bright lines, made impossible to cross) -----------------------------


def test_oalocation_rejects_non_oa_color():
    with pytest.raises(ValueError):
        OaLocation(pdf_url="https://e.org/x.pdf", oa_color="closed", version="vor", source="t")


def test_oalocation_rejects_non_https_url():
    with pytest.raises(ValueError):
        OaLocation(pdf_url="http://e.org/x.pdf", oa_color="gold", version="vor", source="t")


def test_oalocation_rejects_ip_literal_host():
    with pytest.raises(ValueError):
        OaLocation(pdf_url="https://127.0.0.1/x.pdf", oa_color="gold", version="vor", source="t")


def test_download_entrypoint_takes_oalocation_not_a_url():
    # The only public network entry takes an OaLocation, never a bare URL string — so an arbitrary/non-OA
    # fetch is not expressible. (Annotations are strings under `from __future__ import annotations`.)
    params = list(inspect.signature(download_oa_pdf).parameters.values())
    assert params[0].name == "location"
    assert params[0].annotation == "OaLocation"


# --- Registry cascade ---------------------------------------------------------------------------------------


class _StubResolver:
    def __init__(self, id_, location):
        self.id = id_
        self._location = location

    def resolve(self, conn, ref):
        return self._location


def test_new_resolver_registers_without_editing_the_cascade():
    loc = OaLocation(pdf_url="https://e.org/x.pdf", oa_color="green", version="am", source="fake")
    registry = ResolverRegistry()
    registry.register(_StubResolver("fake", loc))
    assert registry.resolve(None, PaperRef(doi="10.1/x")) is loc


def test_registry_returns_first_authorized_hit():
    gold = OaLocation(pdf_url="https://e.org/a.pdf", oa_color="gold", version="vor", source="a")
    green = OaLocation(pdf_url="https://e.org/b.pdf", oa_color="green", version="am", source="b")
    registry = ResolverRegistry()
    registry.register(_StubResolver("a", gold))
    registry.register(_StubResolver("b", green))
    assert registry.resolve(None, PaperRef(doi="10.1/x")) is gold
    miss_then_hit = ResolverRegistry()
    miss_then_hit.register(_StubResolver("none", None))
    miss_then_hit.register(_StubResolver("b", green))
    assert miss_then_hit.resolve(None, PaperRef(doi="10.1/x")) is green


# --- download_oa_pdf validation -----------------------------------------------------------------------------


def _gold_location():
    return OaLocation(pdf_url="https://e.org/x.pdf", oa_color="gold", version="vor", source="openalex")


def test_download_validates_and_writes_a_pdf():
    pdf = _minimal_pdf_bytes()
    path = download_oa_pdf(_gold_location(), fetcher=lambda url, *, timeout, max_bytes: pdf)
    try:
        assert path.exists() and path.read_bytes().startswith(b"%PDF-")
    finally:
        path.unlink(missing_ok=True)


def test_download_rejects_non_pdf():
    with pytest.raises(OaFetchError):
        download_oa_pdf(_gold_location(), fetcher=lambda url, *, timeout, max_bytes: b"<html>nope</html>")


def test_download_rejects_oversized(monkeypatch):
    monkeypatch.setattr(fetch_mod, "MAX_OA_PDF_BYTES", 4)
    with pytest.raises(OaFetchError):
        download_oa_pdf(_gold_location(), fetcher=lambda url, *, timeout, max_bytes: _minimal_pdf_bytes())


# --- temp-dir resolution (inc 414): never PROJECT_ROOT-relative — a packaged, code-signed app ships its
# source tree read-only, and a repo-relative scratch path crashed every acquire there with a bare OSError. ----


def test_download_uses_system_temp_dir_not_project_root(monkeypatch, tmp_path):
    """A hostile/unwritable PROJECT_ROOT (as it is inside a packaged macOS app bundle) must not break the
    download — the temp dir must never be derived from where the code lives."""
    fake_root = tmp_path / "readonly-bundle-resources"  # deliberately never created
    monkeypatch.setattr(fetch_mod, "PROJECT_ROOT", fake_root)
    pdf = _minimal_pdf_bytes()
    path = download_oa_pdf(_gold_location(), fetcher=lambda url, *, timeout, max_bytes: pdf)
    try:
        assert path.exists()
        assert fake_root not in path.parents
    finally:
        path.unlink(missing_ok=True)


def test_download_temp_dir_env_override(monkeypatch, tmp_path):
    custom = tmp_path / "custom-tmp"
    monkeypatch.setenv("CALLOSUM_OA_TEMP_DIR", str(custom))
    pdf = _minimal_pdf_bytes()
    path = download_oa_pdf(_gold_location(), fetcher=lambda url, *, timeout, max_bytes: pdf)
    try:
        assert path.parent == custom
    finally:
        path.unlink(missing_ok=True)


def test_download_wraps_temp_write_oserror(monkeypatch, tmp_path):
    """A real filesystem failure (disk full, permissions, the packaged-bundle case) must surface as
    OaFetchError — matching download_oa_pdf's own documented promise — never a bare, unclassified OSError."""
    monkeypatch.setenv("CALLOSUM_OA_TEMP_DIR", str(tmp_path / "custom-tmp"))
    monkeypatch.setattr(Path, "write_bytes", lambda self, data: (_ for _ in ()).throw(OSError("disk full")))
    pdf = _minimal_pdf_bytes()
    with pytest.raises(OaFetchError, match="could not save"):
        download_oa_pdf(_gold_location(), fetcher=lambda url, *, timeout, max_bytes: pdf)


# --- PDF-download headers (inc 414): an identifying User-Agent — never a browser spoof — on the one fetch
# step that previously sent none, unlike every other external fetcher in this app. ----------------------------


def _mock_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)


def test_pdf_fetcher_sends_identifying_user_agent():
    captured = {}

    def handler(request):
        captured["headers"] = request.headers
        return httpx.Response(200, content=_minimal_pdf_bytes())

    with _mock_client(handler) as client:
        fetch_mod._httpx_pdf_fetcher(
            "https://example.test/paper.pdf", timeout=5, max_bytes=fetch_mod.MAX_OA_PDF_BYTES, client=client
        )
    ua = captured["headers"].get("user-agent", "")
    assert ua.startswith("Callosum/") and "Mozilla" not in ua  # honest identity, never a browser spoof


def test_pdf_fetcher_appends_mailto_when_configured(monkeypatch):
    monkeypatch.setenv("CALLOSUM_OA_MAILTO", "you@example.org")
    captured = {}

    def handler(request):
        captured["headers"] = request.headers
        return httpx.Response(200, content=_minimal_pdf_bytes())

    with _mock_client(handler) as client:
        fetch_mod._httpx_pdf_fetcher(
            "https://example.test/paper.pdf", timeout=5, max_bytes=fetch_mod.MAX_OA_PDF_BYTES, client=client
        )
    assert captured["headers"]["user-agent"].endswith("; mailto:you@example.org")


def test_pdf_fetcher_still_raises_on_403_with_header_present():
    captured = {}

    def handler(request):
        captured["headers"] = request.headers
        return httpx.Response(403)

    with _mock_client(handler) as client:
        with pytest.raises(OaFetchError, match="HTTP 403"):
            fetch_mod._httpx_pdf_fetcher(
                "https://example.test/paper.pdf", timeout=5, max_bytes=fetch_mod.MAX_OA_PDF_BYTES, client=client
            )
    assert captured["headers"]["user-agent"].startswith("Callosum/")  # the header addition changes no error path


# --- import_oa_pdf: managed storage, labeling, local-only ---------------------------------------------------


def test_import_oa_pdf_stores_managed_labeled_and_local(temp_db_url, monkeypatch, tmp_path):
    lib = tmp_path / "lib"
    monkeypatch.setenv("CALLOSUM_LIBRARY_DIR", str(lib))
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id = create_paper(
            conn,
            title="A Paper",
            year=2021,
            doi="10.1/x",
            first_author_family_name="Smith",
            csl_json={
                "type": "article-journal",
                "title": "A Paper",
                "container-title-short": "J. Test",
                "author": [{"family": "Smith"}, {"family": "Jones"}],
            },
        )
    location = OaLocation(pdf_url="https://e.org/x.pdf", oa_color="bronze", version="vor", source="openalex")
    temp_pdf = download_oa_pdf(location, fetcher=lambda url, *, timeout, max_bytes: _minimal_pdf_bytes())
    with engine.begin() as conn:
        result = import_oa_pdf(conn, location, temp_pdf, paper_id=paper_id)

    assert result["oa_color"] == "bronze" and result["bronze_unstable"] is True
    assert result["filename"] == "Smith & Jones - 2021 - J. Test.pdf"
    managed_file = lib / result["filename"]
    assert managed_file.exists()  # the copy lives in the local library dir (nothing server-side)
    with engine.begin() as conn:
        rows = list(conn.execute(select(attachments).where(attachments.c.paper_id == paper_id)).mappings())
    assert len(rows) == 1
    att = rows[0]
    assert att["storage_mode"] == "managed"
    assert att["oa_color"] == "bronze" and att["oa_version"] == "vor" and att["oa_source"] == "openalex"
    assert att["oa_bronze_unstable"] == 1
    assert att["import_source"] == "oa:openalex"


# --- managed-filename convention ----------------------------------------------------------------------------


def test_filename_single_author():
    paper = _paper(csl_json={"author": [{"family": "Smith"}], "container-title-short": "J. Test"}, year=2019)
    assert library_filename_for(paper) == "Smith - 2019 - J. Test.pdf"


def test_filename_two_authors():
    paper = _paper(
        csl_json={"author": [{"family": "Smith"}, {"family": "Jones"}], "container-title": "Cognition"}, year=2020
    )
    assert library_filename_for(paper) == "Smith & Jones - 2020 - Cognition.pdf"


def test_filename_three_plus_authors_et_al():
    paper = _paper(
        csl_json={"author": [{"family": "A"}, {"family": "B"}, {"family": "C"}], "container-title-short": "Jrnl"},
        year=2020,
    )
    assert library_filename_for(paper) == "A et al. - 2020 - Jrnl.pdf"


def test_filename_book_chapter():
    paper = _paper(
        csl_json={"type": "chapter", "author": [{"family": "Doe"}], "container-title": "Big Book", "chapter-number": 3},
        year=2017,
    )
    assert library_filename_for(paper) == "Doe - 2017 - Big Book (Ch. 3).pdf"


def test_filename_sanitizes_illegal_chars():
    paper = _paper(csl_json={"author": [{"family": "O/Brien"}], "container-title": 'A: B? "x"'}, year=2018)
    name = library_filename_for(paper)
    assert all(ch not in name for ch in '<>:"/\\|?*')
    assert name.endswith(".pdf")


def test_filename_falls_back_when_metadata_missing():
    paper = _paper(csl_json={}, first_author_family_name="Lovelace")
    assert library_filename_for(paper) == "Lovelace - n.d. - Unknown.pdf"


def test_filename_uses_known_title_instead_of_implying_an_unknown_paper():
    paper = _paper(
        csl_json={"type": "article-journal", "title": "Evidence Against the Stereotype"},
        title="Evidence Against the Stereotype",
        first_author_family_name="Workman",
        year=2022,
    )

    assert library_filename_for(paper) == "Workman - 2022 - Evidence Against the Stereotype.pdf"
