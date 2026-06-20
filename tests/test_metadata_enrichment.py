from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fitz
from sqlalchemy import select

from alembic import command
from alembic.config import Config
from app.backend.metadata import enrich_paper_metadata_from_crossref, enrich_pdf_scaffold_library
from app.backend.metadata.doi import find_doi_in_pdf, find_doi_in_text
from app.backend.pdf_processing.extraction import COORDINATE_SYSTEM
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import (
    compute_processing_tier,
    create_attachment,
    create_chunk,
    create_paper,
    get_paper,
)
from app.backend.persistence.schema import external_api_cache
from integrations.crossref import CrossrefClient


def test_doi_extraction_finds_pdf_metadata_text_and_avoids_false_matches(tmp_path: Path) -> None:
    metadata_pdf = _make_pdf(tmp_path / "metadata-doi.pdf", metadata_doi="10.5555/META.1")
    text_pdf = _make_pdf(
        tmp_path / "text-doi.pdf",
        lines=["This article has DOI: 10.7777/Text.DOI-2.", "Other text."],
    )
    absent_pdf = _make_pdf(tmp_path / "absent-doi.pdf", lines=["Version 10.123 is not a DOI."])

    metadata_candidate = find_doi_in_pdf(metadata_pdf)
    text_candidate = find_doi_in_pdf(text_pdf)

    assert metadata_candidate is not None
    assert metadata_candidate.doi == "10.5555/meta.1"
    assert metadata_candidate.source == "pdf-metadata"
    assert text_candidate is not None
    assert text_candidate.doi == "10.7777/text.doi-2"
    assert text_candidate.source == "pdf-text"
    assert find_doi_in_pdf(absent_pdf) is None
    assert find_doi_in_text("The value 10.123/abc is not a DOI under the conservative regex.") is None


def test_crossref_resolution_populates_metadata_and_records_provenance(tmp_path: Path) -> None:
    engine = _migrated_engine(tmp_path)
    pdf_path = _make_pdf(tmp_path / "filename-title.pdf", metadata_doi="10.1234/CROSSREF.1")
    client = CrossrefClient(fetcher=FakeCrossrefFetcher({200: _crossref_body("10.1234/crossref.1")}))

    with engine.begin() as conn:
        paper_id = _create_pdf_scaffold_paper(conn, pdf_path, with_chunk=True)
        result = enrich_paper_metadata_from_crossref(conn, paper_id, crossref_client=client)
        paper = get_paper(conn, paper_id)

    assert result.status == "resolved"
    assert result.doi == "10.1234/crossref.1"
    assert result.doi_source == "pdf-metadata"
    assert result.processing_tier == "fully-chunked"
    assert paper["title"] == "Canonical Crossref Title"
    assert paper["year"] == 2022
    assert paper["venue"] == "Journal of Replicable Metadata"
    assert paper["doi"] == "10.1234/crossref.1"
    assert paper["first_author_family_name"] == "Cassidy"
    assert paper["publication_date"] == "2022-5-1"
    assert paper["abstract"] == "A resolved abstract."
    assert paper["imported_source"] == "crossref"
    assert paper["processing_tier"] == "fully-chunked"
    assert paper["csl_json"]["title"] == "Canonical Crossref Title"


def test_crossref_adapter_caches_response_and_second_call_uses_cache(tmp_path: Path) -> None:
    engine = _migrated_engine(tmp_path)
    fetcher = CountingCrossrefFetcher(status_code=200, body=_crossref_body("10.2222/cache"))
    client = CrossrefClient(fetcher=fetcher)

    with engine.begin() as conn:
        first = client.resolve_doi(conn, "10.2222/CACHE")
        second = client.resolve_doi(conn, "10.2222/cache")
        cache_rows = list(conn.execute(select(external_api_cache)).mappings())

    assert first.resolved is True
    assert first.source == "network"
    assert second.resolved is True
    assert second.source == "cache"
    assert fetcher.calls == ["10.2222/cache"]
    assert len(cache_rows) == 1
    assert cache_rows[0]["provider"] == "crossref"
    assert cache_rows[0]["cache_key"] == "10.2222/cache"


def test_unresolvable_doi_leaves_explicit_unresolved_state_without_raising(tmp_path: Path) -> None:
    engine = _migrated_engine(tmp_path)
    pdf_path = _make_pdf(tmp_path / "unresolved.pdf", metadata_doi="10.4040/MISSING")
    client = CrossrefClient(fetcher=CountingCrossrefFetcher(status_code=404, body={"status": "error"}))

    with engine.begin() as conn:
        paper_id = _create_pdf_scaffold_paper(conn, pdf_path, with_chunk=False)
        result = enrich_paper_metadata_from_crossref(conn, paper_id, crossref_client=client)
        paper = get_paper(conn, paper_id)

    assert result.status == "unresolved"
    assert result.error == "Crossref returned HTTP 404"
    assert paper["title"] == "unresolved"
    assert paper["doi"] is None
    assert paper["year"] is None
    assert paper["venue"] is None
    assert paper["imported_source"] == "crossref-unresolved"
    assert paper["processing_tier"] == "metadata-only"


def test_missing_doi_leaves_explicit_unresolved_state_without_fetching(tmp_path: Path) -> None:
    engine = _migrated_engine(tmp_path)
    pdf_path = _make_pdf(tmp_path / "no-doi.pdf", lines=["No identifier appears here."])
    client = CrossrefClient(fetcher=CountingCrossrefFetcher(status_code=200, body=_crossref_body("10.9999/unused")))

    with engine.begin() as conn:
        paper_id = _create_pdf_scaffold_paper(conn, pdf_path, with_chunk=False)
        result = enrich_paper_metadata_from_crossref(conn, paper_id, crossref_client=client)
        paper = get_paper(conn, paper_id)

    assert result.status == "unresolved"
    assert result.doi is None
    assert client.fetcher.calls is None
    assert paper["title"] == "no-doi"
    assert paper["doi"] is None
    assert paper["imported_source"] == "crossref-unresolved"
    assert paper["processing_tier"] == "metadata-only"


def test_processing_tier_ladder_uses_chunks_before_metadata(tmp_path: Path) -> None:
    engine = _migrated_engine(tmp_path)
    pdf_path = _make_pdf(tmp_path / "tier.pdf", metadata_doi="10.3333/TIER")

    with engine.begin() as conn:
        empty_id = create_paper(
            conn,
            title="Empty",
            csl_json={"id": "empty", "type": "document", "title": "Empty"},
            imported_source="pdf-scaffold",
        )
        abstract_id = create_paper(
            conn,
            title="Abstract",
            abstract="Metadata only abstract.",
            csl_json={"id": "abstract", "type": "document", "title": "Abstract"},
            imported_source="pdf-scaffold",
        )
        chunked_id = _create_pdf_scaffold_paper(conn, pdf_path, with_chunk=True)

        assert compute_processing_tier(conn, empty_id) == "metadata-only"
        assert compute_processing_tier(conn, abstract_id) == "abstract-embedded"
        assert compute_processing_tier(conn, chunked_id) == "fully-chunked"


def test_enrichment_is_idempotent_and_does_not_corrupt_records(tmp_path: Path) -> None:
    engine = _migrated_engine(tmp_path)
    pdf_path = _make_pdf(tmp_path / "idempotent.pdf", metadata_doi="10.8888/IDEMPOTENT")
    fetcher = CountingCrossrefFetcher(status_code=200, body=_crossref_body("10.8888/idempotent"))
    client = CrossrefClient(fetcher=fetcher)

    with engine.begin() as conn:
        paper_id = _create_pdf_scaffold_paper(conn, pdf_path, with_chunk=True)
        first = enrich_pdf_scaffold_library(conn, crossref_client=client)
        first_paper = dict(get_paper(conn, paper_id))
        second = enrich_pdf_scaffold_library(conn, crossref_client=client)
        second_paper = dict(get_paper(conn, paper_id))
        cache_count = len(list(conn.execute(select(external_api_cache)).mappings()))

    assert first.resolved == 1
    assert first.unresolved == 0
    assert first.skipped == 0
    assert second.resolved == 1
    assert fetcher.calls == ["10.8888/idempotent"]
    assert cache_count == 1
    assert second_paper == first_paper
    assert second_paper["processing_tier"] == "fully-chunked"


@dataclass
class CountingCrossrefFetcher:
    status_code: int
    body: dict
    calls: list[str] | None = None

    def __call__(self, doi: str, *, headers: dict[str, str], timeout: float):
        assert "User-Agent" in headers
        if self.calls is None:
            self.calls = []
        self.calls.append(doi)
        return self.status_code, self.body


class FakeCrossrefFetcher:
    def __init__(self, responses: dict[int, dict]) -> None:
        self.responses = responses

    def __call__(self, doi: str, *, headers: dict[str, str], timeout: float):
        status_code, body = next(iter(self.responses.items()))
        return status_code, body


def _migrated_engine(tmp_path: Path):
    db_path = tmp_path / "callosum-metadata.sqlite"
    url = f"sqlite:///{db_path.as_posix()}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    return make_engine(url)


def _create_pdf_scaffold_paper(conn, pdf_path: Path, *, with_chunk: bool) -> int:
    paper_id = create_paper(
        conn,
        title=pdf_path.stem,
        csl_json={"id": f"local-{pdf_path.stem}", "type": "document", "title": pdf_path.stem},
        imported_source="pdf-scaffold",
    )
    attachment_id = create_attachment(
        conn,
        paper_id=paper_id,
        storage_mode="linked",
        availability="available",
        original_path=str(pdf_path),
        resolved_path=str(pdf_path.resolve()),
        checksum=f"checksum-{pdf_path.stem}",
        file_size=pdf_path.stat().st_size,
        content_type="application/pdf",
        import_source="pdf-scaffold",
        attachment_type="pdf",
        role="primary",
    )
    if with_chunk:
        create_chunk(
            conn,
            paper_id=paper_id,
            attachment_id=attachment_id,
            text="Metadata fixture text.",
            page_start=1,
            page_end=1,
            bbox_coordinate_system=COORDINATE_SYSTEM,
            extraction_tool="fixture",
            extraction_version="1",
            chunking_strategy="fixture",
            chunk_version="fixture-v1",
            source_attachment_checksum=f"checksum-{pdf_path.stem}",
            bbox_json=[{"page": 1, "x0": 1, "y0": 2, "x1": 3, "y1": 4}],
        )
    return paper_id


def _make_pdf(path: Path, *, metadata_doi: str | None = None, lines: list[str] | None = None) -> Path:
    document = fitz.open()
    page = document.new_page(width=500, height=240)
    for index, line in enumerate(lines or ["Metadata fixture text."]):
        page.insert_text((50, 70 + index * 20), line, fontsize=12)
    if metadata_doi:
        document.set_metadata({"subject": f"doi:{metadata_doi}"})
    document.save(path)
    document.close()
    return path


def _crossref_body(doi: str) -> dict:
    return {
        "status": "ok",
        "message": {
            "DOI": doi,
            "type": "journal-article",
            "title": ["Canonical Crossref Title"],
            "container-title": ["Journal of Replicable Metadata"],
            "issued": {"date-parts": [[2022, 5, 1]]},
            "author": [{"given": "Cliff", "family": "Cassidy"}],
            "abstract": "A resolved abstract.",
        },
    }
