"""Real-data validation harness for Callosum.

This script orchestrates existing import, PDF extraction, embedding, and
retrieval components. It should write only to a scratch output directory.
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any

import fitz
from sqlalchemy import Connection, Engine, func, select

from alembic import command
from alembic.config import Config
from app.backend.clustering.axis_scoring import AxisScoringConfig, create_axis, score_axis
from app.backend.embeddings import (
    DEFAULT_EMBEDDING_MODEL,
    SentenceTransformerEmbeddingModel,
    SQLiteVecVectorStore,
    VectorStore,
    embed_chunks,
    embed_papers,
    search_similar,
)
from app.backend.embeddings.models import EmbeddingModel
from app.backend.importers.zotero import import_zotero_library
from app.backend.pdf_processing.extraction import (
    extract_pdf,
    file_sha256,
    make_chunk_drafts,
)
from app.backend.pdf_processing.ingest import ingest_pdf_scaffold
from app.backend.pdf_processing.quote_matching import locate_quote
from app.backend.persistence.database import make_engine
from app.backend.persistence.schema import (
    attachments,
    chunks,
    citation_mappings,
    cluster_node_papers,
    evidence_quotes,
    papers,
)
from app.backend.summarization.generators import SummaryGenerator
from app.backend.summarization.pipeline import SummaryScope, _source_chunks_for_scope, summarize_scope
from app.backend.summarization.verification import (
    DEFAULT_SUPPORT_THRESHOLD,
    EmbeddingSupportScorer,
    NLISupportScorer,
    SupportScorer,
    VerificationConfig,
)
from integrations.gemini.generator import GeminiConfig, GeminiSummaryGenerator
from tools.validation.report_renderer import render_markdown_report
from tools.validation.reports import (
    AxisCalibrationReport,
    AxisCalibrationScore,
    AxisCalibrationSpec,
    PageDetail,
    PdfReport,
    ProgressReporter,
    QuoteCheck,
    RetrievalReport,
    SummarizationCitationReport,
    SummarizationReport,
    SummarizationSentenceReport,
    SummarizationSpec,
    SupportScoreDistributionItem,
    ValidationReport,
    ZoteroImportReport,
    ZoteroSchemaReport,
)

DEFAULT_OUTPUT_DIR = Path(".local") / "validation"


def run_validation(
    *,
    pdf_dir: Path | None = None,
    zotero_dir: Path | None = None,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    quote_checks: list[QuoteCheck] | None = None,
    queries: list[str] | None = None,
    axes: list[AxisCalibrationSpec] | None = None,
    summarization: SummarizationSpec | None = None,
    top_k: int = 5,
    embedding_model: EmbeddingModel | None = None,
    vector_store: VectorStore | None = None,
    summary_generator: SummaryGenerator | None = None,
    support_scorer_name: str = "nli",
    support_threshold: float = DEFAULT_SUPPORT_THRESHOLD,
    support_scorer: SupportScorer | None = None,
    gemini_config: GeminiConfig | None = None,
    progress: ProgressReporter | None = None,
    reuse_db: bool = False,
) -> ValidationReport:
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    db_path = output_dir / "validation.sqlite"
    if db_path.exists() and not reuse_db:
        db_path.unlink()

    if progress:
        progress.start("Preparing scratch database")
    engine, database_reused, database_created, database_migrated = _open_scratch_database(
        db_path,
        reuse_db=reuse_db,
    )
    if progress:
        progress.finish("Preparing scratch database")
    report = ValidationReport(
        output_dir=str(output_dir),
        database_path=str(db_path),
        database_reused=database_reused,
        database_created=database_created,
        database_migrated=database_migrated,
    )
    quote_checks = quote_checks or []
    queries = queries or []
    axes = axes or []

    with engine.begin() as conn:
        if pdf_dir is not None:
            pdf_paths = sorted(pdf_dir.glob("*.pdf"))
            if progress:
                progress.start("Validating PDFs", total=len(pdf_paths))
            for index, pdf_path in enumerate(pdf_paths, start=1):
                report.pdf_reports.append(
                    _validate_pdf(
                        conn,
                        pdf_path,
                        quote_checks,
                        output_dir,
                        reuse_existing=reuse_db,
                    )
                )
                if progress:
                    progress.update(f"Validating PDFs: {pdf_path.name}", current=index, total=len(pdf_paths))
            if progress:
                progress.finish("Validating PDFs", total=len(pdf_paths))

        if zotero_dir is not None:
            if progress:
                progress.start("Inspecting Zotero schema")
            report.zotero_schema = inspect_zotero_schema(zotero_dir)
            if progress:
                progress.finish("Inspecting Zotero schema")
                progress.start("Importing Zotero library")
            report.zotero_import = _validate_zotero_import(conn, zotero_dir)
            if progress:
                progress.finish("Importing Zotero library")
            if report.zotero_schema.source_db_checksum_after is None:
                source_db = zotero_dir / "zotero.sqlite"
                if source_db.exists():
                    report.zotero_schema.source_db_checksum_after = file_sha256(source_db)
                    report.zotero_schema.read_only_unchanged = (
                        report.zotero_schema.source_db_checksum_before == report.zotero_schema.source_db_checksum_after
                    )

        if queries:
            if progress:
                progress.start("Running retrieval spot checks", total=len(queries))
            report.retrieval = _run_retrieval_spot_check(
                conn,
                embedding_model=embedding_model,
                vector_store=vector_store,
                queries=queries,
                top_k=top_k,
                progress=progress,
            )
            if progress:
                progress.finish("Running retrieval spot checks", total=len(queries))
        if axes:
            if progress:
                progress.start("Running axis calibration", total=len(axes))
            report.axis_calibration = run_axis_calibration_probe(
                conn,
                axes=axes,
                embedding_model=embedding_model,
                vector_store=vector_store,
                progress=progress,
            )
            if progress:
                progress.finish("Running axis calibration", total=len(axes))
        if summarization is not None:
            if progress:
                progress.start("Running summarization probe")
            report.summarization = run_summarization_probe(
                conn,
                spec=summarization,
                embedding_model=embedding_model,
                vector_store=vector_store,
                top_k=top_k,
                summary_generator=summary_generator,
                support_scorer_name=support_scorer_name,
                support_threshold=support_threshold,
                support_scorer=support_scorer,
                gemini_config=gemini_config,
            )
            if progress:
                progress.finish("Running summarization probe")

    engine.dispose()

    if progress:
        progress.start("Writing validation report")
    report_text = render_markdown_report(report)
    (output_dir / "validation-report.md").write_text(report_text, encoding="utf-8")
    if progress:
        progress.finish("Writing validation report")
    return report


def inspect_zotero_schema(zotero_dir: Path) -> ZoteroSchemaReport:
    source_db = zotero_dir / "zotero.sqlite"
    report = ZoteroSchemaReport()
    if not source_db.exists():
        report.warnings.append(f"zotero.sqlite not found at {source_db}")
        return report

    report.source_db_checksum_before = file_sha256(source_db)
    with tempfile.TemporaryDirectory(prefix="callosum-zotero-schema-") as temp_dir:
        copied_db = Path(temp_dir) / "zotero.sqlite"
        shutil.copy2(source_db, copied_db)
        conn = sqlite3.connect(f"file:{copied_db.as_posix()}?mode=ro", uri=True)
        try:
            table_names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            expected = {
                "items": {"itemID", "itemTypeID", "key", "libraryID"},
                "itemTypes": {"itemTypeID", "typeName"},
                "fields": {"fieldID", "fieldName"},
                "itemData": {"itemID", "fieldID", "valueID"},
                "itemDataValues": {"valueID", "value"},
                "creators": {"creatorID", "firstName", "lastName"},
                "itemCreators": {"itemID", "creatorID", "orderIndex"},
                "itemAttachments": {"itemID", "parentItemID", "linkMode", "contentType", "path"},
                "collections": {"collectionID", "key", "collectionName", "parentCollectionID"},
                "collectionItems": {"collectionID", "itemID"},
                "tags": {"tagID", "name"},
                "itemTags": {"itemID", "tagID"},
                "itemNotes": {"itemID", "parentItemID", "note"},
            }
            optional = {"creatorTypes", "deletedItems", "itemAnnotations"}
            report.present_tables = sorted(table_names & set(expected))
            report.missing_tables = sorted(set(expected) - table_names)
            report.optional_present = sorted(table_names & optional)
            report.optional_missing = sorted(optional - table_names)
            for table, columns in expected.items():
                if table not in table_names:
                    continue
                actual_columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
                missing = sorted(columns - actual_columns)
                if missing:
                    report.missing_columns[table] = missing
            report.warnings.extend(_zotero_schema_warnings(conn, table_names))
        finally:
            conn.close()

    report.source_db_checksum_after = file_sha256(source_db)
    report.read_only_unchanged = report.source_db_checksum_before == report.source_db_checksum_after
    return report


def parse_quote_specs(values: list[str]) -> list[QuoteCheck]:
    checks = []
    for value in values:
        if "::" not in value:
            raise ValueError("Quote specs must use '<pdf filename or *>::<quote>'")
        pdf_name, quote = value.split("::", 1)
        checks.append(QuoteCheck(pdf_name=pdf_name, quote=quote))
    return checks


def parse_axis_specs(values: list[str]) -> list[AxisCalibrationSpec]:
    specs = []
    for value in values:
        if "::" in value:
            label, description = value.split("::", 1)
            specs.append(AxisCalibrationSpec(label=label.strip(), description=description.strip() or None))
        else:
            specs.append(AxisCalibrationSpec(label=value.strip(), description=None))
    return specs


def parse_paper_ids(value: str | None) -> list[int] | None:
    if value is None:
        return None
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def run_axis_calibration_probe(
    conn: Connection,
    *,
    axes: list[AxisCalibrationSpec],
    embedding_model: EmbeddingModel | None,
    vector_store: VectorStore | None,
    progress: ProgressReporter | None = None,
) -> list[AxisCalibrationReport]:
    model = embedding_model or SentenceTransformerEmbeddingModel(
        name=DEFAULT_EMBEDDING_MODEL,
        version=DEFAULT_EMBEDDING_MODEL,
        local_files_only=True,
    )
    store = vector_store or SQLiteVecVectorStore()
    reports = []
    for index, spec in enumerate(axes, start=1):
        axis_report = AxisCalibrationReport(label=spec.label, description=spec.description)
        try:
            axis_id = create_axis(conn, label=spec.label, description=spec.description)
            result = score_axis(
                conn,
                axis_id=axis_id,
                model=model,
                vector_store=store,
                config=AxisScoringConfig(
                    assignment_mode="absolute",
                    assignment_threshold=1.0,
                    uncertainty_threshold=0.0,
                ),
            )
            axis_report.scores = _axis_calibration_scores(conn, result.scores)
            axis_report.largest_gap_rank, axis_report.largest_gap = _largest_score_gap(axis_report.scores)
        except Exception as exc:
            axis_report.error = f"{type(exc).__name__}: {exc}"
        reports.append(axis_report)
        if progress:
            progress.update(f"Running axis calibration: {spec.label}", current=index, total=len(axes))
    return reports


def run_summarization_probe(
    conn: Connection,
    *,
    spec: SummarizationSpec,
    embedding_model: EmbeddingModel | None,
    vector_store: VectorStore | None,
    top_k: int,
    summary_generator: SummaryGenerator | None = None,
    support_scorer_name: str = "nli",
    support_threshold: float = DEFAULT_SUPPORT_THRESHOLD,
    support_scorer: SupportScorer | None = None,
    gemini_config: GeminiConfig | None = None,
) -> SummarizationReport:
    scope = _summary_scope_from_spec(spec)
    report = SummarizationReport(
        scope={"scope_type": scope.scope_type, **scope.to_ref()},
        support_scorer=support_scorer_name,
        support_threshold=support_threshold,
        source_chunk_count=_summary_scope_chunk_count(conn, scope),
    )
    if report.source_chunk_count == 0:
        report.zero_chunk_message = _zero_chunk_message()
        report.skipped_reason = "no source chunks available"
        return report
    generator = summary_generator
    if generator is None:
        config = gemini_config or GeminiConfig.from_environment()
        if not config.data_egress_enabled:
            _populate_summarization_scope_preview(
                report,
                conn=conn,
                scope=scope,
                embedding_model=embedding_model,
                vector_store=vector_store,
                top_k=top_k,
            )
            if report.source_chunk_count == 0:
                report.zero_chunk_message = _zero_chunk_message()
            report.skipped_reason = "CALLOSUM_ALLOW_DATA_EGRESS is not enabled"
            return report
        if not config.resolved_api_key():
            _populate_summarization_scope_preview(
                report,
                conn=conn,
                scope=scope,
                embedding_model=embedding_model,
                vector_store=vector_store,
                top_k=top_k,
            )
            if report.source_chunk_count == 0:
                report.zero_chunk_message = _zero_chunk_message()
            report.skipped_reason = f"{config.api_key_env} is not set"
            return report
        generator = GeminiSummaryGenerator(config=config)

    model = embedding_model or SentenceTransformerEmbeddingModel(
        name=DEFAULT_EMBEDDING_MODEL,
        version=DEFAULT_EMBEDDING_MODEL,
        local_files_only=True,
    )
    store = vector_store or SQLiteVecVectorStore()

    scorer = support_scorer
    if scorer is None:
        if support_scorer_name == "embedding":
            scorer = EmbeddingSupportScorer(model)
        elif support_scorer_name == "nli":
            scorer = NLISupportScorer(fallback_scorer=EmbeddingSupportScorer(model))
        else:
            report.error = f"Unsupported support scorer: {support_scorer_name}"
            return report

    try:
        result = summarize_scope(
            conn,
            scope=scope,
            generator=generator,
            model=model,
            vector_store=store,
            top_k=top_k,
            verifier_config=VerificationConfig(support_threshold=support_threshold),
            support_scorer=scorer,
        )
        report.summary_id = result.summary_id
        report.status = result.status
        report.verified_sentences = len([sentence for sentence in result.sentences if not sentence.flagged])
        report.flagged_sentences = len(result.flagged_sentences)
        report.sentences = [_sentence_report(conn, sentence) for sentence in result.sentences]
        report.support_scores = _support_score_distribution(report.sentences)
    except Exception as exc:
        report.error = f"{type(exc).__name__}: {exc}"
    return report


def _zero_chunk_message() -> str:
    return (
        "No source chunks were available for this summarization scope. "
        "Likely causes: no PDFs were ingested into this scratch DB, or the selected scope has no chunks. "
        "Run with --pdf-dir first, or pass --reuse-db with a populated --output-dir."
    )


def _open_scratch_database(db_path: Path, *, reuse_db: bool) -> tuple[Engine, bool, bool, bool]:
    existed = db_path.exists()
    if reuse_db and existed and _is_database_migrated(db_path):
        return make_engine(f"sqlite:///{db_path.as_posix()}"), True, False, False
    engine = _create_scratch_database(db_path)
    return engine, False, not existed, True


def _create_scratch_database(db_path: Path) -> Engine:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path.as_posix()}")
    command.upgrade(config, "head")
    return make_engine(f"sqlite:///{db_path.as_posix()}")


def _is_database_migrated(db_path: Path) -> bool:
    try:
        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'alembic_version'"
            ).fetchone()
            if row is None:
                return False
            version = conn.execute("SELECT version_num FROM alembic_version LIMIT 1").fetchone()
            return bool(version and version[0])
        finally:
            conn.close()
    except sqlite3.Error:
        return False


def _axis_calibration_scores(conn: Connection, scores) -> list[AxisCalibrationScore]:  # type: ignore[no-untyped-def]
    rows = []
    for index, score in enumerate(scores, start=1):
        title = conn.execute(select(papers.c.title).where(papers.c.id == score.paper_id)).scalar_one()
        next_score = scores[index].confidence if index < len(scores) else None
        rows.append(
            AxisCalibrationScore(
                rank=index,
                paper_id=score.paper_id,
                title=str(title),
                score=score.confidence,
                gap_to_next=None if next_score is None else score.confidence - next_score,
            )
        )
    return rows


def _largest_score_gap(scores: list[AxisCalibrationScore]) -> tuple[int | None, float | None]:
    gaps = [(score.rank, score.gap_to_next) for score in scores if score.gap_to_next is not None]
    if not gaps:
        return None, None
    rank, gap = max(gaps, key=lambda item: (item[1], -item[0]))
    return rank, gap


def _populate_summarization_scope_preview(
    report: SummarizationReport,
    *,
    conn: Connection,
    scope: SummaryScope,
    embedding_model: EmbeddingModel | None,
    vector_store: VectorStore | None,
    top_k: int,
) -> None:
    try:
        model = embedding_model or SentenceTransformerEmbeddingModel(
            name=DEFAULT_EMBEDDING_MODEL,
            version=DEFAULT_EMBEDDING_MODEL,
            local_files_only=True,
        )
        store = vector_store or SQLiteVecVectorStore()
        report.source_chunk_count = len(
            _source_chunks_for_scope(conn, scope=scope, model=model, vector_store=store, top_k=top_k)
        )
    except Exception as exc:
        report.error = f"Scope preview error: {type(exc).__name__}: {exc}"


def _summary_scope_from_spec(spec: SummarizationSpec) -> SummaryScope:
    selected = [
        spec.query is not None,
        spec.paper_ids is not None,
        spec.cluster_node_id is not None,
    ]
    if sum(selected) != 1:
        raise ValueError("Choose exactly one summarization scope: query, papers, or cluster node.")
    if spec.query is not None:
        return SummaryScope(scope_type="query", query=spec.query)
    if spec.paper_ids is not None:
        return SummaryScope(scope_type="papers", paper_ids=spec.paper_ids)
    return SummaryScope(scope_type="cluster_node", cluster_node_id=spec.cluster_node_id)


def _summary_scope_chunk_count(conn: Connection, scope: SummaryScope) -> int:
    stmt = select(func.count()).select_from(chunks)
    if scope.scope_type == "papers":
        paper_ids = scope.paper_ids or []
        stmt = stmt.where(chunks.c.paper_id.in_(paper_ids)) if paper_ids else stmt.where(False)
    elif scope.scope_type == "cluster_node":
        paper_ids = [
            int(row[0])
            for row in conn.execute(
                select(cluster_node_papers.c.paper_id).where(
                    cluster_node_papers.c.cluster_node_id == scope.cluster_node_id
                )
            )
        ]
        stmt = stmt.where(chunks.c.paper_id.in_(paper_ids)) if paper_ids else stmt.where(False)
    return int(conn.execute(stmt).scalar_one())


def _sentence_report(conn: Connection, sentence) -> SummarizationSentenceReport:  # type: ignore[no-untyped-def]
    return SummarizationSentenceReport(
        ordinal=sentence.ordinal,
        text=sentence.text,
        flagged=sentence.flagged,
        citations=[_citation_report(conn, citation) for citation in sentence.citations],
    )


def _citation_report(conn: Connection, citation) -> SummarizationCitationReport:  # type: ignore[no-untyped-def]
    quote_row = (
        conn.execute(select(evidence_quotes).where(evidence_quotes.c.id == citation.evidence_quote_id)).mappings().one()
    )
    mapping_row = (
        conn.execute(select(citation_mappings).where(citation_mappings.c.id == citation.mapping_id)).mappings().one()
    )
    chunk_row = conn.execute(select(chunks).where(chunks.c.id == citation.chunk_id)).mappings().one()
    paper_row = conn.execute(select(papers).where(papers.c.id == chunk_row["paper_id"])).mappings().one()
    return SummarizationCitationReport(
        chunk_id=int(citation.chunk_id),
        paper_id=int(chunk_row["paper_id"]) if chunk_row["paper_id"] is not None else None,
        paper_title=str(paper_row["title"]) if paper_row["title"] is not None else None,
        page_start=quote_row["page_start"],
        page_end=quote_row["page_end"],
        quote_text=str(quote_row["quote_text"]),
        quote_located=bool(
            quote_row["quote_confidence"] and quote_row["page_start"] is not None and quote_row["bbox_json"]
        ),
        status=str(mapping_row["status"]),
        retrieval_confidence=float(quote_row["retrieval_confidence"]),
        quote_confidence=float(quote_row["quote_confidence"]),
        support_confidence=float(quote_row["support_confidence"]),
    )


def _support_score_distribution(
    sentences: list[SummarizationSentenceReport],
) -> list[SupportScoreDistributionItem]:
    items = [
        SupportScoreDistributionItem(
            rank=0,
            sentence_ordinal=sentence.ordinal,
            chunk_id=citation.chunk_id,
            status=citation.status,
            score=citation.support_confidence,
        )
        for sentence in sentences
        for citation in sentence.citations
    ]
    ranked = sorted(items, key=lambda item: (-item.score, item.sentence_ordinal, item.chunk_id))
    return [
        SupportScoreDistributionItem(
            rank=index,
            sentence_ordinal=item.sentence_ordinal,
            chunk_id=item.chunk_id,
            status=item.status,
            score=item.score,
        )
        for index, item in enumerate(ranked, start=1)
    ]


def _validate_pdf(
    conn: Connection,
    pdf_path: Path,
    quote_checks: list[QuoteCheck],
    output_dir: Path | None = None,
    *,
    reuse_existing: bool = False,
) -> PdfReport:
    if reuse_existing:
        existing = _existing_pdf_report(conn, pdf_path, quote_checks)
        if existing is not None:
            return existing

    report = PdfReport(path=str(pdf_path))
    try:
        extraction = extract_pdf(pdf_path)
        pages_with_text_map = {page.page_number: len(page.blocks) > 0 for page in extraction.pages}

        with fitz.open(pdf_path) as document:
            report.page_count = document.page_count
            for page_index, page in enumerate(document):
                page_number = page_index + 1
                has_text = pages_with_text_map.get(page_number, False)

                hint = None
                if not has_text:
                    report.pages_without_text.append(page_number)
                    # Heuristic hint logic
                    has_images = len(page.get_images()) > 0
                    # Type 1 blocks are images in PyMuPDF
                    has_image_blocks = any(b["type"] == 1 for b in page.get_text("dict")["blocks"])
                    has_drawings = len(page.get_drawings()) > 0

                    if has_images or has_image_blocks:
                        hint = "likely image/figure page (image content present, no text)"
                    elif has_drawings:
                        hint = "likely graphic/drawing page (vector drawings present, no text)"
                    else:
                        hint = "empty page (no text, no image/drawing content)"

                    # Optional: Render text-free page
                    if output_dir:
                        debug_dir = output_dir / "debug-images" / pdf_path.name
                        debug_dir.mkdir(parents=True, exist_ok=True)
                        pix = page.get_pixmap(matrix=fitz.Matrix(0.5, 0.5))  # 50% scale
                        pix.save(debug_dir / f"page_{page_number}.png")

                report.page_details.append(PageDetail(page_number=page_number, has_text=has_text, hint=hint))

        drafts = make_chunk_drafts(extraction, source_attachment_checksum=file_sha256(pdf_path))
        report.chunk_count = len(drafts)
        report.pages_with_text = sum(1 for pd in report.page_details if pd.has_text)
        report.zero_text = report.chunk_count == 0
        ingest_pdf_scaffold(conn, pdf_path, title=pdf_path.stem)
    except Exception as exc:
        report.error = f"{type(exc).__name__}: {exc}"

    _append_quote_results(report, pdf_path, quote_checks)
    return report


def _existing_pdf_report(conn: Connection, pdf_path: Path, quote_checks: list[QuoteCheck]) -> PdfReport | None:
    checksum = file_sha256(pdf_path)
    existing_attachment_ids = [
        int(row[0])
        for row in conn.execute(
            select(attachments.c.id).where(
                attachments.c.checksum == checksum,
                attachments.c.content_type == "application/pdf",
            )
        )
    ]
    if not existing_attachment_ids:
        return None
    report = PdfReport(path=str(pdf_path), reused_existing=True)
    try:
        with fitz.open(pdf_path) as document:
            report.page_count = document.page_count
    except Exception as exc:
        report.error = f"{type(exc).__name__}: {exc}"
    report.chunk_count = int(
        conn.execute(
            select(func.count()).select_from(chunks).where(chunks.c.attachment_id.in_(existing_attachment_ids))
        ).scalar_one()
    )
    report.pages_with_text = int(
        conn.execute(
            select(func.count(func.distinct(chunks.c.page_start))).where(
                chunks.c.attachment_id.in_(existing_attachment_ids)
            )
        ).scalar_one()
    )
    report.zero_text = report.chunk_count == 0
    _append_quote_results(report, pdf_path, quote_checks)
    return report


def _append_quote_results(report: PdfReport, pdf_path: Path, quote_checks: list[QuoteCheck]) -> None:
    for check in quote_checks:
        if check.pdf_name not in {"*", pdf_path.name, str(pdf_path)}:
            continue
        try:
            match = locate_quote(pdf_path, check.quote)
            report.quote_results.append(
                {
                    "quote": check.quote,
                    "found": match.found,
                    "page_start": match.page_start,
                    "page_end": match.page_end,
                    "rectangle_count": len(match.rectangles),
                }
            )
        except Exception as exc:
            report.quote_results.append({"quote": check.quote, "found": False, "error": f"{type(exc).__name__}: {exc}"})


def _validate_zotero_import(conn: Connection, zotero_dir: Path) -> ZoteroImportReport:
    report = ZoteroImportReport()
    errors: list[str] = []

    def on_attachment_error(attachment, exc: Exception) -> None:  # type: ignore[no-untyped-def]
        errors.append(f"{attachment.key}: {type(exc).__name__}: {exc}")

    try:
        report.result = import_zotero_library(conn, zotero_dir, on_attachment_error=on_attachment_error)
        report.attachment_errors = errors
    except Exception as exc:
        report.error = f"{type(exc).__name__}: {exc}"
    report.imported_items = conn.execute(select(func.count()).select_from(papers)).scalar_one()
    report.imported_attachments = conn.execute(select(func.count()).select_from(attachments)).scalar_one()
    report.available_attachments = conn.execute(
        select(func.count()).select_from(attachments).where(attachments.c.availability == "available")
    ).scalar_one()
    report.missing_attachments = conn.execute(
        select(func.count()).select_from(attachments).where(attachments.c.availability == "missing")
    ).scalar_one()
    report.url_attachments = conn.execute(
        select(func.count()).select_from(attachments).where(attachments.c.storage_mode == "url")
    ).scalar_one()
    return report


def _run_retrieval_spot_check(
    conn: Connection,
    *,
    embedding_model: EmbeddingModel | None,
    vector_store: VectorStore | None,
    queries: list[str],
    top_k: int,
    progress: ProgressReporter | None = None,
) -> RetrievalReport:
    model = embedding_model or SentenceTransformerEmbeddingModel(
        name=DEFAULT_EMBEDDING_MODEL,
        version=DEFAULT_EMBEDDING_MODEL,
        local_files_only=True,
    )
    store = vector_store or SQLiteVecVectorStore()
    report = RetrievalReport()
    try:
        report.chunk_embeddings = len(embed_chunks(conn, model=model, vector_store=store))
        report.paper_embeddings = len(embed_papers(conn, model=model, vector_store=store))
        for index, query in enumerate(queries, start=1):
            hits = search_similar(conn, query=query, model=model, vector_store=store, top_k=top_k)
            report.query_results[query] = [_hit_to_dict(conn, hit) for hit in hits]
            if progress:
                progress.update(f"Running retrieval spot checks: {query}", current=index, total=len(queries))
    except Exception as exc:
        report.embedding_error = f"{type(exc).__name__}: {exc}"
    return report


def _hit_to_dict(conn: Connection, hit) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    snippet = None
    if hit.chunk_id is not None:
        text = conn.execute(select(chunks.c.text).where(chunks.c.id == hit.chunk_id)).scalar_one()
        snippet = " ".join(str(text).split())[:280]
    return {
        "embedding_id": hit.embedding_id,
        "target_type": hit.target_type,
        "target_id": hit.target_id,
        "score": hit.score,
        "distance": hit.distance,
        "paper_id": hit.paper_id,
        "chunk_id": hit.chunk_id,
        "page_start": hit.page_start,
        "page_end": hit.page_end,
        "title": hit.title,
        "snippet": snippet,
    }


def _zotero_schema_warnings(conn: sqlite3.Connection, table_names: set[str]) -> list[str]:
    warnings: list[str] = []
    if "creatorTypes" in table_names:
        warnings.append("creatorTypes present; importer currently preserves creator order but not creator roles.")
    if "itemTags" in table_names:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(itemTags)")}
        if "type" in columns:
            warnings.append("itemTags.type present; importer currently ignores automatic/manual tag type.")
    if "deletedItems" in table_names:
        warnings.append("deletedItems present; importer currently does not explicitly exclude deleted items.")
    if "itemAnnotations" in table_names:
        warnings.append("itemAnnotations present; importer preserves raw position but does not translate coordinates.")
    if "itemAttachments" in table_names:
        rows = conn.execute("SELECT path FROM itemAttachments WHERE path LIKE 'attachments:%' LIMIT 3").fetchall()
        if rows:
            warnings.append(
                "attachments: linked-path prefixes found; importer does not resolve Zotero base-directory aliases yet."
            )
    return warnings


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Run Callosum real-data validation.")
    parser.add_argument("--pdf-dir", type=Path, help="Folder of real PDFs to validate")
    parser.add_argument("--zotero-dir", type=Path, help="Zotero data directory containing zotero.sqlite")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--quote", action="append", default=[], help="Quote spec '<pdf filename or *>::<quote>'")
    parser.add_argument("--query", action="append", default=[], help="Retrieval query to spot-check")
    parser.add_argument("--axis", action="append", default=[], help="Axis calibration spec '<label>::<description>'")
    parser.add_argument("--summarize-query", help="Run a grounded summary for a retrieval query scope")
    parser.add_argument("--summarize-papers", help="Comma-separated paper IDs for a grounded summary scope")
    parser.add_argument("--summarize-cluster", type=int, help="Cluster node ID for a grounded summary scope")
    parser.add_argument("--support-scorer", choices=["embedding", "nli"], default="nli")
    parser.add_argument("--support-threshold", type=float, default=DEFAULT_SUPPORT_THRESHOLD)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--model", default=DEFAULT_EMBEDDING_MODEL)
    parser.add_argument("--reuse-db", action="store_true", help="Reuse an existing migrated scratch database")
    parser.add_argument("--no-progress", action="store_true", help="Disable stderr progress output")
    args = parser.parse_args()
    summarize_scopes = [
        args.summarize_query is not None,
        args.summarize_papers is not None,
        args.summarize_cluster is not None,
    ]
    if sum(summarize_scopes) > 1:
        parser.error("Choose at most one summarization scope flag.")
    summarization = None
    if args.summarize_query is not None:
        summarization = SummarizationSpec(query=args.summarize_query)
    elif args.summarize_papers is not None:
        summarization = SummarizationSpec(paper_ids=parse_paper_ids(args.summarize_papers))
    elif args.summarize_cluster is not None:
        summarization = SummarizationSpec(cluster_node_id=args.summarize_cluster)
    needs_embedding_model = bool(args.query or args.axis or summarization is not None)

    report = run_validation(
        pdf_dir=args.pdf_dir,
        zotero_dir=args.zotero_dir,
        output_dir=args.output_dir,
        quote_checks=parse_quote_specs(args.quote),
        queries=args.query,
        axes=parse_axis_specs(args.axis),
        summarization=summarization,
        top_k=args.top_k,
        embedding_model=SentenceTransformerEmbeddingModel(
            name=args.model,
            version=args.model,
            local_files_only=True,
        )
        if needs_embedding_model
        else None,
        support_scorer_name=args.support_scorer,
        support_threshold=args.support_threshold,
        progress=ProgressReporter(enabled=not args.no_progress),
        reuse_db=args.reuse_db,
    )
    print(render_markdown_report(report))
    print(f"\nReport written to: {Path(report.output_dir) / 'validation-report.md'}")


if __name__ == "__main__":
    main()
