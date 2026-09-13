"""#79 epistemic boundary: the reader "find referenced paper → Critique" flow gates Critique on USABLE FULL
TEXT.

The signal the reader gate uses is ``GET /papers/{id}.chunk_count > 0``: a metadata-only paper (no chunks) is
never offered Critique, and the honest "Critique needs the full paper" state is shown instead.

This gate is **load-bearing, not defense-in-depth**: the canonical Critical Read's claim extraction
(``methods.critical_review.extract_claim_sentences``) falls back to a paper's ABSTRACT when it has no chunks, so
metadata/abstract alone could otherwise be critiqued — precisely the boundary #79 forbids ("metadata / title /
abstract / snippets are never sufficient for Critique"). The reader flow never invokes ``critical-read`` on a
chunkless paper; this test pins the ``chunk_count`` signal that decision relies on, and documents (below) that a
chunkless-but-abstracted paper does yield abstract sentences — which is exactly why the frontend gate exists.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from alembic import command
from alembic.config import Config
from app.backend.api import create_app
from app.backend.methods.critical_review import extract_claim_sentences
from app.backend.pdf_processing.extraction import COORDINATE_SYSTEM, DEFAULT_CHUNKING_STRATEGY
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_attachment, create_chunk, create_paper


def _migrated(tmp_path: Path) -> str:
    url = f"sqlite:///{(tmp_path / 'reader-critique.sqlite').as_posix()}"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    return url


def _seed(engine):
    with engine.begin() as conn:
        meta_only = create_paper(
            conn,
            title="Meta only",
            csl_json={"title": "Meta only"},
            abstract="An abstract sentence that must NOT be treated as enough to critique the paper.",
        )
        full = create_paper(conn, title="Full text", csl_json={"title": "Full text"})
        att = create_attachment(
            conn,
            paper_id=full,
            storage_mode="linked",
            availability="available",
            original_path="/fake/f.pdf",
            resolved_path="/fake/f.pdf",
            checksum="ck1",
            file_size=1024,
            content_type="application/pdf",
            import_source="test",
            attachment_type="pdf",
            role="primary",
        )
        create_chunk(
            conn,
            paper_id=full,
            attachment_id=att,
            text="A real full-text sentence carrying actual content from the article body.",
            page_start=1,
            page_end=1,
            bbox_coordinate_system=COORDINATE_SYSTEM,
            extraction_tool="pymupdf",
            extraction_version="test",
            chunking_strategy=DEFAULT_CHUNKING_STRATEGY,
            chunk_version="ck1-v1",
            source_attachment_checksum="ck1",
            char_start=0,
            char_end=70,
            bbox_json=[{"page": 1, "x0": 50, "y0": 50, "x1": 300, "y1": 80}],
        )
    return meta_only, full


def test_chunk_count_signal_gates_the_reader_critique(tmp_path: Path):
    url = _migrated(tmp_path)
    engine = make_engine(url)
    meta_only, full = _seed(engine)
    engine.dispose()
    client = TestClient(create_app(db_url=url))
    meta = client.get(f"/papers/{meta_only}").json()
    full_detail = client.get(f"/papers/{full}").json()
    # The signal the reader gate reads: metadata-only (even WITH an abstract) has no usable full text.
    assert meta["chunk_count"] == 0
    assert full_detail["chunk_count"] > 0


def test_extract_claim_sentences_would_use_the_abstract_so_the_gate_is_load_bearing(tmp_path: Path):
    url = _migrated(tmp_path)
    engine = make_engine(url)
    meta_only, _ = _seed(engine)
    with engine.connect() as conn:
        claims = extract_claim_sentences(conn, meta_only)
    engine.dispose()
    # A chunkless-but-abstracted paper DOES yield abstract-derived claim sentences — so the canonical Critical
    # Read would critique from the abstract if invoked. The reader flow must therefore refuse to invoke it here
    # (it gates on chunk_count > 0, asserted above), never relying on the backend to withhold. This test locks
    # in *why* the frontend gate is required.
    assert claims  # non-empty: proof the boundary cannot be left to the backend extractor
