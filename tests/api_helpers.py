from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import insert

from app.backend.api import create_app
from app.backend.embeddings.models import DEFAULT_NORMALIZATION, normalize_text
from app.backend.embeddings.vector_store import InMemoryVectorStore
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_attachment, create_chunk, create_paper
from app.backend.persistence.schema import (
    axes,
    cluster_node_papers,
    cluster_nodes,
)
from app.backend.persistence.tags_repo import add_tag_to_paper
from app.backend.summarization.generators import FakeSummaryGenerator

# A tiny real 2-page PDF committed at tests/fixtures/seed.pdf, whose text sits at the bboxes below (generated with
# PyMuPDF, top-left points). The seed's "renderable" paper links to it so QA can actually exercise the PDF viewer +
# the coordinate-honesty invariant (a real page renders; a chunk's bbox truthfully locates its quote).
SEED_PDF_PATH = str(Path(__file__).resolve().parent / "fixtures" / "seed.pdf")
SEED_PDF_BBOX_P1 = {"page": 1, "x0": 72.0, "y0": 187.1, "x1": 378.1, "y1": 203.6}
SEED_PDF_BBOX_P2 = {"page": 2, "x0": 72.0, "y0": 147.1, "x1": 409.5, "y1": 163.6}
SEED_PDF_TEXT_P1 = "Facial anomalies influence social judgments in observers."
SEED_PDF_TEXT_P2 = "A second passage about signal detection appears on page two."


def alembic_head() -> str:
    """The current Alembic head revision, read from the migration scripts. Tests assert against THIS rather than
    a hardcoded revision string — which drifts every time a migration lands and only the full suite catches
    (the stale-constant failure that bit inc 91/98). Assumes the single linear head the project maintains."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    return ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()


@dataclass(frozen=True)
class ApiFakeEmbeddingModel:
    name: str = "fake-api-embedding"
    version: str = "v1"
    dimension: int = 3
    normalization: str = DEFAULT_NORMALIZATION

    def encode_texts(self, texts: list[str]) -> list[list[float]]:
        return [_api_vector(normalize_text(text, self.normalization)) for text in texts]


@dataclass(frozen=True)
class ConstantSupportScorer:
    value: float = 1.0

    def score(self, *, sentence: str, passage: str) -> float:
        return self.value


def _annotation_body(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "page": 2,
        "color": "#ffd54a",
        "bboxes": [
            {"page": 2, "x0": 100.0, "y0": 120.0, "x1": 240.0, "y1": 134.0},
            {"page": 2, "x0": 100.0, "y0": 136.0, "x1": 180.0, "y1": 150.0},
        ],
        "anchor_text": "Compared with typical faces",
        "prefix": "Results. ",
        "suffix": " were rated lower.",
    }
    body.update(overrides)
    return body


def _seed_library(db_url: str) -> dict[str, int]:
    engine = make_engine(db_url)
    with engine.begin() as conn:
        facial_paper_id = create_paper(
            conn,
            title="Facial Anomaly Perception",
            abstract="Faces and social perception.",
            year=2024,
            doi="10.123/facial",
            venue="Journal of Faces",
            first_author_family_name="Lovelace",
            citation_key="lovelace2024",
            processing_tier="fully-chunked",
            item_type="article-journal",  # so GET /papers/item-types is non-empty → the Library Type filter renders
            csl_json={
                "id": "lovelace2024",
                "type": "article-journal",
                "title": "Facial Anomaly Perception",
                "author": [{"given": "Ada", "family": "Lovelace"}],
            },
        )
        signal_paper_id = create_paper(
            conn,
            title="Signal Detection Theory",
            abstract="Criterion shifts in signal detection.",
            year=2023,
            venue="Cognition",
            first_author_family_name="Turing",
            processing_tier="metadata-only",
            item_type="article-journal",  # so GET /papers/item-types is non-empty → the Library Type filter renders
            csl_json={
                "id": "turing2023",
                "type": "article-journal",
                "title": "Signal Detection Theory",
                "author": [{"given": "Alan", "family": "Turing"}],
            },
        )
        attachment_id = create_attachment(
            conn,
            paper_id=facial_paper_id,
            storage_mode="linked",
            availability="available",
            original_path=r"C:\papers\facial.pdf",
            resolved_path=r"C:\papers\facial.pdf",
            checksum="checksum-facial",
            file_size=1000,
            content_type="application/pdf",
            import_source="test",
            attachment_type="pdf",
            role="primary",
        )
        create_attachment(
            conn,
            paper_id=facial_paper_id,
            storage_mode="linked",
            availability="available",
            original_path="/home/u/library/posix-facial.pdf",
            resolved_path="/home/u/library/posix-facial.pdf",
            checksum="checksum-posix",
            file_size=1001,
            content_type="application/pdf",
            import_source="test",
            attachment_type="pdf",
            role="supplement",
        )
        create_attachment(
            conn,
            paper_id=facial_paper_id,
            storage_mode="linked",
            availability="available",
            original_path="C:/papers/drive-slash-facial.pdf",
            resolved_path="C:/papers/drive-slash-facial.pdf",
            checksum="checksum-drive-slash",
            file_size=1002,
            content_type="application/pdf",
            import_source="test",
            attachment_type="pdf",
            role="supplement",
        )
        create_attachment(
            conn,
            paper_id=facial_paper_id,
            storage_mode="linked",
            availability="available",
            original_path="bare-facial.pdf",
            resolved_path="bare-facial.pdf",
            checksum="checksum-bare",
            file_size=1003,
            content_type="application/pdf",
            import_source="test",
            attachment_type="pdf",
            role="supplement",
        )
        create_chunk(
            conn,
            paper_id=facial_paper_id,
            attachment_id=attachment_id,
            text="Facial anomalies influence social judgments.",
            page_start=1,
            page_end=1,
            bbox_coordinate_system="pdf-points-top-left",
            extraction_tool="fixture",
            extraction_version="1",
            chunking_strategy="paragraph",
            chunk_version="chunk-v1",
            source_attachment_checksum="checksum-facial",
            bbox_json=[{"page": 1, "x0": 10, "y0": 20, "x1": 120, "y1": 40}],
        )
        create_chunk(
            conn,
            paper_id=facial_paper_id,
            attachment_id=attachment_id,
            text="A second passage appears on the next page.",
            page_start=2,
            page_end=2,
            bbox_coordinate_system="pdf-points-top-left",
            extraction_tool="fixture",
            extraction_version="1",
            chunking_strategy="paragraph",
            chunk_version="chunk-v2",
            source_attachment_checksum="checksum-facial",
            bbox_json=[{"page": 2, "x0": 12, "y0": 24, "x1": 130, "y1": 42}],
        )
        # inc 120 (QA seed enrichment): a paper backed by a REAL on-disk PDF + truthful chunk bboxes, so QA routes
        # can exercise the PDF viewer render path and the coordinate-honesty invariant (the facial paper above keeps
        # testing the path-edge-cases + the honest "PDF not available locally" 404, so it is left untouched).
        renderable_paper_id = create_paper(
            conn,
            title="Renderable Seed Paper",
            abstract="A real PDF for the viewer + coordinate-honesty QA path.",
            year=2025,
            doi="10.123/renderable",
            venue="Journal of Fixtures",
            first_author_family_name="Curie",
            citation_key="curie2025",
            processing_tier="fully-chunked",
            csl_json={
                "id": "curie2025",
                "type": "article-journal",
                "title": "Renderable Seed Paper",
                "author": [{"given": "Marie", "family": "Curie"}],
            },
        )
        renderable_attachment_id = create_attachment(
            conn,
            paper_id=renderable_paper_id,
            storage_mode="linked",
            availability="available",
            original_path=SEED_PDF_PATH,
            resolved_path=SEED_PDF_PATH,
            checksum="checksum-renderable",
            file_size=1475,
            content_type="application/pdf",
            import_source="test",
            attachment_type="pdf",
            role="primary",
        )
        create_chunk(
            conn,
            paper_id=renderable_paper_id,
            attachment_id=renderable_attachment_id,
            text=SEED_PDF_TEXT_P1,
            page_start=1,
            page_end=1,
            bbox_coordinate_system="pdf-points-top-left",
            extraction_tool="fixture",
            extraction_version="1",
            chunking_strategy="paragraph",
            chunk_version="chunk-v1",
            source_attachment_checksum="checksum-renderable",
            bbox_json=[SEED_PDF_BBOX_P1],
        )
        create_chunk(
            conn,
            paper_id=renderable_paper_id,
            attachment_id=renderable_attachment_id,
            text=SEED_PDF_TEXT_P2,
            page_start=2,
            page_end=2,
            bbox_coordinate_system="pdf-points-top-left",
            extraction_tool="fixture",
            extraction_version="1",
            chunking_strategy="paragraph",
            chunk_version="chunk-v2",
            source_attachment_checksum="checksum-renderable",
            bbox_json=[SEED_PDF_BBOX_P2],
        )
        # a tag, so the sidebar Tags panel + tag-filter surfaces are non-empty for QA
        tag_id = int(add_tag_to_paper(conn, renderable_paper_id, "social-perception")["id"])
        axis_id = int(
            conn.execute(
                insert(axes).values(label="Facial Anomalies", description="User-defined axis")
            ).inserted_primary_key[0]
        )
        cluster_node_id = int(
            conn.execute(
                insert(cluster_nodes).values(
                    axis_id=axis_id,
                    parent_id=None,
                    label="Facial cluster",
                    description="Assigned papers",
                    confidence=0.8,
                )
            ).inserted_primary_key[0]
        )
        conn.execute(
            insert(cluster_node_papers).values(
                cluster_node_id=cluster_node_id,
                paper_id=facial_paper_id,
                confidence=0.91,
            )
        )
    engine.dispose()
    return {
        "facial_paper_id": facial_paper_id,
        "signal_paper_id": signal_paper_id,
        "renderable_paper_id": renderable_paper_id,  # inc 120: backed by tests/fixtures/seed.pdf (real, 2 pages)
        "tag_id": tag_id,
        "axis_id": axis_id,
        "cluster_node_id": cluster_node_id,
    }


def _summarization_app(temp_db_url: str, *, generator: FakeSummaryGenerator | None = None, overview_generator=None):
    if generator is None:
        generator = FakeSummaryGenerator(sentences=[])
    return create_app(
        db_url=temp_db_url,
        summary_generator=generator,
        overview_generator=overview_generator,
        embedding_model=ApiFakeEmbeddingModel(),
        vector_store=InMemoryVectorStore(),
        support_scorer=ConstantSupportScorer(),
    )


def _seed_summarization_library(db_url: str) -> dict[str, int]:
    engine = make_engine(db_url)
    with engine.begin() as conn:
        facial_paper_id = create_paper(
            conn,
            title="API Summarization Facial Paper",
            csl_json={
                "type": "article-journal",
                "title": "API Summarization Facial Paper",
                "author": [{"given": "Ada", "family": "Lovelace"}],
            },
            first_author_family_name="Lovelace",
            processing_tier="fully-chunked",
        )
        unrelated_paper_id = create_paper(
            conn,
            title="API Summarization Banana Paper",
            csl_json={
                "type": "article-journal",
                "title": "API Summarization Banana Paper",
                "author": [{"given": "Alan", "family": "Turing"}],
            },
            first_author_family_name="Turing",
            processing_tier="fully-chunked",
        )
        facial_attachment_id = create_attachment(
            conn,
            paper_id=facial_paper_id,
            storage_mode="linked",
            availability="available",
            content_type="application/pdf",
            checksum="summary-facial-checksum",
            import_source="test",
            attachment_type="pdf",
            role="primary",
        )
        unrelated_attachment_id = create_attachment(
            conn,
            paper_id=unrelated_paper_id,
            storage_mode="linked",
            availability="available",
            content_type="application/pdf",
            checksum="summary-banana-checksum",
            import_source="test",
            attachment_type="pdf",
            role="primary",
        )
        facial_chunk_id = create_chunk(
            conn,
            paper_id=facial_paper_id,
            attachment_id=facial_attachment_id,
            text="Facial anomalies influence social judgments.",
            page_start=1,
            page_end=1,
            bbox_coordinate_system="pdf-points-top-left",
            extraction_tool="fixture",
            extraction_version="1",
            chunking_strategy="paragraph",
            chunk_version="summary-chunk-v1",
            source_attachment_checksum="summary-facial-checksum",
            bbox_json=[{"page": 1, "x0": 10, "y0": 20, "x1": 120, "y1": 40}],
        )
        create_chunk(
            conn,
            paper_id=unrelated_paper_id,
            attachment_id=unrelated_attachment_id,
            text="Banana orchard material is unrelated.",
            page_start=3,
            page_end=3,
            bbox_coordinate_system="pdf-points-top-left",
            extraction_tool="fixture",
            extraction_version="1",
            chunking_strategy="paragraph",
            chunk_version="summary-chunk-v2",
            source_attachment_checksum="summary-banana-checksum",
            bbox_json=[{"page": 3, "x0": 11, "y0": 22, "x1": 121, "y1": 42}],
        )
        axis_id = int(
            conn.execute(
                insert(axes).values(label="Summary Axis", description="API summary scope")
            ).inserted_primary_key[0]
        )
        cluster_node_id = int(
            conn.execute(
                insert(cluster_nodes).values(
                    axis_id=axis_id,
                    parent_id=None,
                    label="Summary cluster",
                    description="Assigned papers",
                    confidence=0.9,
                )
            ).inserted_primary_key[0]
        )
        conn.execute(
            insert(cluster_node_papers).values(
                cluster_node_id=cluster_node_id,
                paper_id=facial_paper_id,
                confidence=0.95,
            )
        )
    engine.dispose()
    return {
        "facial_paper_id": facial_paper_id,
        "unrelated_paper_id": unrelated_paper_id,
        "facial_chunk_id": facial_chunk_id,
        "facial_attachment_id": facial_attachment_id,
        "unrelated_attachment_id": unrelated_attachment_id,
        "cluster_node_id": cluster_node_id,
    }


def _api_vector(text: str) -> list[float]:
    if "facial" in text or "social judgment" in text or "social judgments" in text:
        return [1.0, 0.0, 0.0]
    if "banana" in text or "orchard" in text:
        return [0.0, 1.0, 0.0]
    return [0.0, 0.0, 1.0]
