from __future__ import annotations

import ast
import tokenize
from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.embeddings.models import DEFAULT_NORMALIZATION
from app.backend.embeddings.pipeline import embed_chunks
from app.backend.embeddings.retrieval import search_similar
from app.backend.embeddings.vector_store import InMemoryVectorStore
from app.backend.persistence.database import make_engine
from app.backend.persistence.document_roles import (
    ARTICLE_AND_SUPPLEMENT_DOCUMENT_ROLES,
    ARTICLE_DOCUMENT_ROLES,
    PREREGISTRATION,
)
from app.backend.persistence.repository import (
    create_attachment,
    create_chunk,
    create_paper,
    get_all_chunks_for_paper,
    get_chunks_for_attachment,
    get_chunks_for_paper,
    refresh_processing_tier,
)
from app.backend.summarization.pipeline import SummaryScope, _source_chunks_for_scope


@dataclass(frozen=True)
class _ScopeEmbeddingModel:
    name: str = "document-scope-fixture"
    version: str = "1"
    dimension: int = 2
    normalization: str = DEFAULT_NORMALIZATION

    def encode_texts(self, texts: list[str]) -> list[list[float]]:
        return [[0.0, 1.0] if "registration-only" in text.casefold() else [1.0, 0.0] for text in texts]


def _paper_with_documents(conn) -> dict[str, int]:
    paper_id = create_paper(
        conn,
        title="Scoped paper",
        csl_json={"type": "article-journal", "title": "Scoped paper"},
    )
    ids: dict[str, int] = {"paper": paper_id}
    for key, role, text in (
        ("article", "primary", "Article-only account of the published study."),
        ("supplement", "supplementary-text", "Supplement-only robustness result."),
        ("registration", "preregistration", "Registration-only planned outcome and preregistration statement."),
        ("protocol", "protocol", "Protocol-only intervention schedule."),
    ):
        attachment_id = create_attachment(
            conn,
            paper_id=paper_id,
            storage_mode="managed",
            availability="available",
            content_type="application/pdf",
            checksum=f"scope-{key}",
            attachment_type="pdf",
            role=role,
        )
        chunk_id = create_chunk(
            conn,
            paper_id=paper_id,
            attachment_id=attachment_id,
            text=text,
            page_start=1,
            page_end=1,
            bbox_coordinate_system="pdf-points-top-left",
            extraction_tool="fixture",
            extraction_version="1",
            chunking_strategy="paragraph",
            chunk_version=f"scope-{key}-v1",
            source_attachment_checksum=f"scope-{key}",
        )
        ids[key] = attachment_id
        ids[f"{key}_chunk"] = chunk_id
    return ids


def test_repository_retrieval_is_attachment_and_role_scoped(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        ids = _paper_with_documents(conn)
        article = get_chunks_for_paper(conn, ids["paper"], document_roles=ARTICLE_DOCUMENT_ROLES)
        published = get_chunks_for_paper(conn, ids["paper"], document_roles=ARTICLE_AND_SUPPLEMENT_DOCUMENT_ROLES)
        registration = get_chunks_for_paper(conn, ids["paper"], document_roles=(PREREGISTRATION,))
        exact = get_chunks_for_attachment(conn, ids["registration"])
        all_documents = get_all_chunks_for_paper(conn, ids["paper"])

    assert [row["id"] for row in article] == [ids["article_chunk"]]
    assert [row["id"] for row in published] == [ids["article_chunk"], ids["supplement_chunk"]]
    assert [row["id"] for row in registration] == [ids["registration_chunk"]]
    assert [row["id"] for row in exact] == [ids["registration_chunk"]]
    assert {row["id"] for row in all_documents} == {
        ids["article_chunk"],
        ids["supplement_chunk"],
        ids["registration_chunk"],
        ids["protocol_chunk"],
    }


def test_unrestricted_chunk_embedding_and_retrieval_require_explicit_scope(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    model = _ScopeEmbeddingModel()
    store = InMemoryVectorStore()
    with engine.begin() as conn:
        ids = _paper_with_documents(conn)
        with pytest.raises(TypeError, match="document_roles"):
            get_chunks_for_paper(conn, ids["paper"])  # type: ignore[call-arg]
        with pytest.raises(ValueError, match="explicit document_roles"):
            embed_chunks(conn, model=model, vector_store=store)
        embed_chunks(conn, model=model, vector_store=store, chunk_ids=[ids["article_chunk"]])
        with pytest.raises(ValueError, match="document_roles"):
            search_similar(
                conn,
                query="article",
                model=model,
                vector_store=store,
                target_types=("chunk",),
            )


def test_legacy_null_primary_and_secondary_roles_remain_safe(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id = create_paper(conn, title="Legacy", csl_json={"title": "Legacy"})
        chunk_ids: dict[str, int] = {}
        for key, role in (("null", None), ("primary", "primary"), ("secondary", "secondary")):
            attachment_id = create_attachment(
                conn,
                paper_id=paper_id,
                storage_mode="managed",
                availability="available",
                content_type="application/pdf",
                checksum=key,
                attachment_type="pdf",
                role=role,
            )
            chunk_ids[key] = create_chunk(
                conn,
                paper_id=paper_id,
                attachment_id=attachment_id,
                text=f"{key} role text",
                page_start=1,
                page_end=1,
                bbox_coordinate_system="pdf-points-top-left",
                extraction_tool="fixture",
                extraction_version="1",
                chunking_strategy="paragraph",
                chunk_version=f"{key}-v1",
                source_attachment_checksum=key,
            )
        rows = get_chunks_for_paper(conn, paper_id, document_roles=ARTICLE_DOCUMENT_ROLES)

    assert [row["id"] for row in rows] == [chunk_ids["null"], chunk_ids["primary"]]


def test_ordinary_reads_exclude_registration_while_transparency_can_read_supplements(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    model = _ScopeEmbeddingModel()
    store = InMemoryVectorStore()
    with engine.begin() as conn:
        ids = _paper_with_documents(conn)
        source_chunks = _source_chunks_for_scope(
            conn,
            scope=SummaryScope(scope_type="papers", paper_ids=[ids["paper"]]),
            model=model,
            vector_store=store,
            top_k=20,
        )
    client = TestClient(create_app(db_url=temp_db_url))
    chunk_rows = client.get(f"/papers/{ids['paper']}/chunks").json()
    transparency = client.get(f"/papers/{ids['paper']}/transparency").json()
    preregistration = next(item for item in transparency["checks"] if item["key"] == "preregistration")

    assert [row.chunk_id for row in source_chunks] == [ids["article_chunk"]]
    assert [row["id"] for row in chunk_rows] == [ids["article_chunk"]]
    assert preregistration["status"] == "not-found"
    assert preregistration["evidence"] is None


def test_ordinary_lexical_and_semantic_search_exclude_registration_chunks(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    model = _ScopeEmbeddingModel()
    store = InMemoryVectorStore()
    with engine.begin() as conn:
        ids = _paper_with_documents(conn)
        embed_chunks(
            conn,
            model=model,
            vector_store=store,
            chunk_ids=[ids["article_chunk"], ids["registration_chunk"]],
        )
        hits = search_similar(
            conn,
            query="registration-only",
            model=model,
            vector_store=store,
            top_k=10,
            target_types=("chunk",),
            document_roles=ARTICLE_DOCUMENT_ROLES,
        )
    client = TestClient(create_app(db_url=temp_db_url))

    assert [hit.chunk_id for hit in hits] == [ids["article_chunk"]]
    assert client.get("/papers/fulltext", params={"q": "registration-only"}).json() == []


def test_registration_chunks_do_not_promote_article_processing_tier(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id = create_paper(conn, title="Registration only", csl_json={"title": "Registration only"})
        attachment_id = create_attachment(
            conn,
            paper_id=paper_id,
            storage_mode="managed",
            availability="available",
            content_type="application/pdf",
            checksum="registration-only",
            attachment_type="pdf",
            role="preregistration",
        )
        create_chunk(
            conn,
            paper_id=paper_id,
            attachment_id=attachment_id,
            text="Registration-only content.",
            page_start=1,
            page_end=1,
            bbox_coordinate_system="pdf-points-top-left",
            extraction_tool="fixture",
            extraction_version="1",
            chunking_strategy="paragraph",
            chunk_version="registration-only-v1",
            source_attachment_checksum="registration-only",
        )
        tier = refresh_processing_tier(conn, paper_id)

    assert tier == "metadata-only"


def test_app_chunk_consumers_declare_scope_or_exact_ids() -> None:
    repo_root = Path(__file__).parents[1]
    code_roots = (repo_root / "app" / "backend", repo_root / "integrations")
    violations: list[str] = []
    for code_root in code_roots:
        for path in code_root.rglob("*.py"):
            with tokenize.open(path) as source:
                tree = ast.parse(source.read(), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                name = node.func.id if isinstance(node.func, ast.Name) else None
                keywords = {kw.arg for kw in node.keywords if kw.arg is not None}
                label = f"{path.relative_to(repo_root)}:{node.lineno}"
                if name == "get_chunks_for_paper" and "document_roles" not in keywords:
                    violations.append(f"{label}: get_chunks_for_paper")
                if name == "embed_chunks" and not ({"chunk_ids", "document_roles"} & keywords):
                    violations.append(f"{label}: embed_chunks")
                if name == "search_similar" and not ({"candidate_target_ids", "document_roles"} & keywords):
                    target_types = next((kw.value for kw in node.keywords if kw.arg == "target_types"), None)
                    if target_types is None or "chunk" in ast.unparse(target_types):
                        violations.append(f"{label}: search_similar")

    assert violations == []
