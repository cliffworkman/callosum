"""Drift guard for reader "Ask this paper" (inc 596).

The reader Ask is a THIN client of canonical Ask: it sends `scope_type="papers", paper_ids=[one], query` to the
same production `/summarize` pipeline. This pins the invariant the reader depends on — that the canonical
pipeline honors that shape as a DETERMINISTIC single-paper question Ask: the candidate pool is restricted to
exactly that paper (no other paper's chunks leak in) AND the question reaches the generator (so it answers,
rather than merely summarizing). If papers+query scope ever stops restricting or stops passing the query,
reader Ask would silently drift from canonical Ask — and this fails first.

Self-contained (no cross-test imports): it builds two papers with chunks directly, runs `summarize_scope`
with a capturing generator, and asserts on the scope handed to that generator. Hermetic — no network, no real
embeddings needed for the scope invariant.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from alembic import command
from alembic.config import Config
from app.backend.embeddings.models import DEFAULT_NORMALIZATION
from app.backend.embeddings.vector_store import InMemoryVectorStore
from app.backend.pdf_processing.extraction import COORDINATE_SYSTEM, DEFAULT_CHUNKING_STRATEGY
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_attachment, create_chunk, create_paper
from app.backend.summarization.pipeline import SummaryScope, summarize_scope
from app.backend.summarization.verification import EmbeddingSupportScorer


def _migrated_engine(tmp_path: Path):
    url = f"sqlite:///{(tmp_path / 'reader-ask.sqlite').as_posix()}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    return make_engine(url)


@dataclass(frozen=True)
class _FakeModel:
    name: str = "reader-ask-fake"
    version: str = "v1"
    dimension: int = 3
    normalization: str = DEFAULT_NORMALIZATION

    def encode_texts(self, texts: list[str]) -> list[list[float]]:
        # Deterministic (no hash-seed dependence); the scope invariant does not depend on ranking quality.
        out = []
        for text in texts:
            h = (sum(ord(c) for c in text) % 1000) / 1000.0
            out.append([1.0, h, 1.0 - h])
        return out


class _CapturingGenerator:
    name = "reader-ask-capture"

    def __init__(self) -> None:
        self.source_chunks = None
        self.scope_ref = None

    def generate(self, *, source_chunks, scope_ref, engine=None):
        self.source_chunks = list(source_chunks)
        self.scope_ref = dict(scope_ref)
        return []  # no sentences -> no verification work; we only assert the scope handed to the generator


def _make_paper(conn, title: str, checksum: str, texts: list[str]) -> int:
    paper_id = create_paper(
        conn, title=title, csl_json={"id": title, "type": "document", "title": title}, processing_tier="fully-chunked"
    )
    attachment_id = create_attachment(
        conn,
        paper_id=paper_id,
        storage_mode="linked",
        availability="available",
        original_path=f"/fake/{checksum}.pdf",
        resolved_path=f"/fake/{checksum}.pdf",
        checksum=checksum,
        file_size=1024,
        content_type="application/pdf",
        import_source="test",
        attachment_type="pdf",
        role="primary",
    )
    for i, text in enumerate(texts):
        create_chunk(
            conn,
            paper_id=paper_id,
            attachment_id=attachment_id,
            text=text,
            page_start=1,
            page_end=1,
            bbox_coordinate_system=COORDINATE_SYSTEM,
            extraction_tool="pymupdf",
            extraction_version="test",
            chunking_strategy=DEFAULT_CHUNKING_STRATEGY,
            chunk_version=f"{checksum}-v1",
            source_attachment_checksum=checksum,
            char_start=0,
            char_end=len(text),
            bbox_json=[{"page": 1, "x0": 50, "y0": 50 + i * 40, "x1": 300, "y1": 80 + i * 40}],
        )
    return paper_id


def _run(tmp_path: Path, query: str):
    engine = _migrated_engine(tmp_path)
    with engine.begin() as conn:
        paper_a = _make_paper(conn, "Paper A", "aaaa1111", ["Alpha finding about neurons.", "Alpha methods used fMRI."])
        paper_b = _make_paper(conn, "Paper B", "bbbb2222", ["Beta unrelated result.", "Beta orchard material."])
    generator = _CapturingGenerator()
    summarize_scope(
        engine,
        scope=SummaryScope(scope_type="papers", paper_ids=[paper_a], query=query),
        generator=generator,
        model=_FakeModel(),
        vector_store=InMemoryVectorStore(),
        support_scorer=EmbeddingSupportScorer(_FakeModel()),
    )
    engine.dispose()
    return paper_a, paper_b, generator


def test_reader_ask_papers_query_restricts_to_the_one_paper(tmp_path: Path) -> None:
    paper_a, paper_b, gen = _run(tmp_path, "What did this paper find about neurons?")
    assert gen.source_chunks, "a single-paper Ask must hand the generator chunks from that paper"
    paper_ids = {chunk.paper_id for chunk in gen.source_chunks}
    assert paper_ids == {paper_a}  # ONLY paper A — paper B's chunks never leak into a single-paper Ask
    assert paper_b not in paper_ids


def test_reader_ask_passes_the_question_to_the_generator(tmp_path: Path) -> None:
    paper_a, _, gen = _run(tmp_path, "How was the sample recruited?")
    # to_ref carries the query -> the generator ANSWERS the question (Ask), not merely summarizes the paper.
    assert gen.scope_ref.get("query") == "How was the sample recruited?"
    # The paper relationship is recorded in the artifact's scope_ref (discoverable by paper later; no reader copy).
    assert gen.scope_ref.get("paper_ids") == [paper_a]
