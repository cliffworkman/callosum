"""Export the curated anomalous-is-bad public demo from a dedicated read-only database.

This exporter never accepts an ordinary Callosum database implicitly. The caller must name the deliberately
curated source and acknowledge that every selected byte is public. SQL selects are explicit whitelists, output
models reject unknown fields, licensed assets are checksum-verified, and the final JSON is scanned fail-closed.
"""

# ruff: noqa: E402 -- direct script execution needs the repository root on sys.path before app imports.

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sqlite3
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from app.backend.api.routers.health import HealthResponse
from app.backend.api.routers.help import help_corpus
from app.backend.api.routers.lmm import LmmLibrarySummary, build_lmm_response
from app.backend.api.routers.metaanalysis import MetaLibrarySummary, build_meta_analysis_response
from app.backend.api.routers.methods import (
    StatcheckCoverage,
    StatcheckLibrarySummary,
    StatcheckResult,
    _run_statcheck_for_paper,
    _statcheck_result_payload,
)
from app.backend.api.routers.methods_bayes import BayesLibrarySummary, build_bayes_response
from app.backend.api.routers.methods_statcheck_cache import StatcheckCacheResponse
from app.backend.api.routers.paper_models import AttachmentResponse, PaperDetailResponse, PaperListItem
from app.backend.api.routers.settings import AccountStatus, SettingsStatus
from app.backend.api.routers.status import JOB_COMPUTE_KINDS, JOB_LABELS, StatusJob, StatusResponse
from app.backend.api.routers.summaries import (
    SummarizeJobResponse,
    SummaryCitationResponse,
    SummaryListItem,
    SummarySentenceResponse,
)
from app.backend.api.routers.transparency import TransparencyLibrarySummary, build_transparency_response
from app.backend.api.startup import PROJECT_ROOT  # noqa: E402
from app.backend.citations.render import render_papers
from app.backend.demo_ask_overview import DemoAskOverviewState, verified_claims_sha256
from app.backend.demo_capabilities import WORKSPACE_CAPABILITIES
from app.backend.demo_extended_state import DemoExtendedState
from app.backend.demo_library_state import DemoLibraryState
from app.backend.demo_snapshot import (
    SNAPSHOT_SCHEMA_VERSION,
    DemoApi,
    DemoCapabilities,
    DemoDocument,
    DemoLicense,
    DemoManifest,
    DemoMethodSnapshots,
    DemoMethodSummaries,
    DemoPaper,
    DemoSnapshot,
    assert_public_snapshot_bytes,
)
from app.backend.demo_synthesis_state import DemoSynthesisState
from app.backend.demo_wip_state import DemoWipState
from app.backend.metadata.citation_export import render_citations
from app.backend.methods.evidence_anchors import pdf_attachment_ids
from app.backend.persistence import workbench_export
from tools.demo.curated_library import CORPUS, CURATED_ON, curated_abstract

SUMMARY_ID = 1


def _citation_row(paper_id: int) -> dict[str, Any]:
    """Explicit public metadata whitelist for the production citation renderers."""

    item = CORPUS[paper_id]
    return {
        "id": paper_id,
        "title": item["title"],
        "year": item["year"],
        "doi": item["doi"],
        "venue": item["venue"],
        "item_type": "article-journal",
        "first_author_family_name": item["csl_authors"][0]["family"],
        "citation_key": None,
        "csl_json": {
            "id": f"demo-{paper_id}",
            "type": "article-journal",
            "title": item["title"],
            "author": item["csl_authors"],
            "issued": {"date-parts": [[item["year"]]]},
            "DOI": item["doi"],
            "URL": item["canonical_url"],
            "container-title": item["venue"],
        },
    }


def _json(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    parsed = json.loads(value) if isinstance(value, str) else value
    return parsed


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _authors(csl: dict[str, Any], fallback: list[str]) -> list[str]:
    values = []
    for author in csl.get("author") or []:
        if not isinstance(author, dict):
            continue
        literal = str(author.get("literal") or "").strip()
        name = literal or " ".join(str(author.get(k) or "").strip() for k in ("given", "family")).strip()
        if name:
            values.append(name)
    return values or fallback


def _paper(
    con: sqlite3.Connection,
    paper_id: int,
    asset_dir: Path,
    methods: DemoMethodSnapshots,
    library_state: DemoLibraryState,
) -> DemoPaper:
    curated = CORPUS[paper_id]
    has_pdf = curated.get("bundled_material", "complete-pdf") == "complete-pdf"
    row = con.execute(
        """SELECT id, abstract, item_type, language, publication_date, first_author_family_name,
                  citation_key, csl_json, processing_tier
           FROM papers WHERE id = ?""",
        (paper_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"curated paper {paper_id} is missing")
    attachment = None
    actual_hash = None
    if has_pdf:
        attachment = con.execute(
            """SELECT id, resolved_path, checksum, file_size, content_type, attachment_type, role
               FROM attachments WHERE paper_id = ? AND availability = 'available'
               ORDER BY CASE WHEN role = 'primary' THEN 0 ELSE 1 END, id LIMIT 1""",
            (paper_id,),
        ).fetchone()
        if attachment is None:
            raise ValueError(f"curated paper {paper_id} has no available document")
        source = Path(str(attachment["resolved_path"] or ""))
        if not source.is_file():
            raise ValueError(f"curated paper {paper_id} document is unavailable")
        actual_hash = _sha256(source)
        if actual_hash != str(attachment["checksum"]):
            raise ValueError(f"curated paper {paper_id} checksum does not match its source record")
        if str(attachment["content_type"]) != "application/pdf":
            raise ValueError(f"curated paper {paper_id} asset is not a PDF")
        if source.read_bytes()[:5] != b"%PDF-":
            raise ValueError(f"curated paper {paper_id} asset does not have a PDF signature")
        asset_dir.mkdir(parents=True, exist_ok=True)
        destination = asset_dir / curated["filename"]
        if source.resolve() != destination.resolve():
            shutil.copyfile(source, destination)
        if _sha256(destination) != actual_hash:
            raise ValueError(f"copied asset checksum failed for paper {paper_id}")
    elif con.execute(
        "SELECT 1 FROM attachments WHERE paper_id = ? AND availability = 'available' LIMIT 1", (paper_id,)
    ).fetchone():
        raise ValueError(f"curated paper {paper_id} is metadata-and-evidence-only but has a bundled attachment")

    csl = _json(row["csl_json"], {})
    csl.update(
        {
            "id": f"demo-{paper_id}",
            "type": "article-journal",
            "title": curated["title"],
            "author": curated["csl_authors"],
            "issued": {"date-parts": [[int(part) for part in curated["publication_date"].split("-")]]},
            "DOI": curated["doi"],
            "URL": curated.get("article_url", curated["canonical_url"]),
            "container-title": curated["venue"],
            "publisher": curated["publisher"],
            "volume": curated["volume"],
            "issue": curated["issue"],
            "page": curated["page"],
            "ISSN": curated["issn"],
        }
    )
    chunk_count = int(con.execute("SELECT count(*) FROM chunks WHERE paper_id = ?", (paper_id,)).fetchone()[0])
    attachment_count = 1 if has_pdf else 0
    priority = next(item.priority for item in library_state.reading_queue if item.id == paper_id)
    list_item = PaperListItem(
        id=paper_id,
        title=curated["title"],
        authors=_authors(csl, curated["authors"]),
        year=curated["year"],
        venue=curated["venue"],
        citation_key=row["citation_key"],
        processing_tier="fully-chunked" if chunk_count > 0 else row["processing_tier"],
        attachment_count=attachment_count,
        chunk_count=chunk_count,
        priority=priority,
    )
    public_attachments = []
    if has_pdf:
        public_attachments = [
            AttachmentResponse(
                id=int(attachment["id"]),
                filename=curated["filename"],
                storage_mode="bundled-demo",
                availability="available",
                checksum=actual_hash,
                file_size=int(attachment["file_size"]),
                content_type="application/pdf",
                import_source="curated-public-demo",
                attachment_type="pdf",
                role="primary",
                oa_license=curated["license_name"],
                oa_landing_page_url=curated["canonical_url"],
            )
        ]
    abstract = curated_abstract(con, paper_id) or row["abstract"] or curated.get("abstract")
    detail = PaperDetailResponse(
        id=paper_id,
        title=curated["title"],
        abstract=abstract,
        abstract_display=abstract,
        abstract_text=abstract,
        authors=curated["authors"],
        year=curated["year"],
        doi=curated["doi"],
        venue=curated["venue"],
        item_type="article-journal",
        language=row["language"] or "en",
        publication_date=curated["publication_date"],
        first_author_family_name=curated["csl_authors"][0]["family"],
        imported_source="curated-public-demo",
        citation_key=row["citation_key"],
        processing_tier="fully-chunked" if chunk_count > 0 else row["processing_tier"],
        csl_json=csl,
        extra_urls=list(
            dict.fromkeys([curated.get("article_url", curated["canonical_url"]), curated["canonical_url"]])
        ),
        attachment_count=attachment_count,
        chunk_count=chunk_count,
        attachments=public_attachments,
        tags=library_state.paper_tags[str(paper_id)],
        priority=priority,
    )
    license_record = DemoLicense(
        work_title=curated["title"],
        authors=curated["authors"],
        license_name=curated["license_name"],
        license_url=curated["license_url"],
        redistribution_basis=curated["redistribution_basis"],
        canonical_url=curated["canonical_url"],
        doi=curated["doi"],
        attribution=f"{curated['title']} ({curated['year']}), {', '.join(curated['authors'])}. DOI: {curated['doi']}.",
        verified_via=curated["verified_via"],
        verified_on=CURATED_ON,
        bundled_material="complete-pdf" if has_pdf else "metadata-and-evidence-only",
        notice=curated["notice"],
    )
    document = (
        DemoDocument(
            paper_id=paper_id,
            asset_path=f"documents/{curated['filename']}",
            media_type="application/pdf",
            sha256=actual_hash,
            license=license_record,
        )
        if has_pdf
        else DemoDocument(paper_id=paper_id, license=license_record)
    )
    return DemoPaper(
        list_item=list_item,
        detail=detail,
        document=document,
        methods=methods,
    )


def _method_snapshots(conn, paper_id: int) -> DemoMethodSnapshots:
    report, coverage = _run_statcheck_for_paper(conn, paper_id)
    pdf_ids = pdf_attachment_ids(conn, (result.attachment_id for result in report.results))
    statcheck = StatcheckCacheResponse(
        cached=True,
        checked=report.checked,
        inconsistent=report.inconsistent,
        decision_errors=report.decision_errors,
        results=[StatcheckResult(**_statcheck_result_payload(conn, result, pdf_ids)) for result in report.results],
        coverage=StatcheckCoverage(**coverage),
        computed_at=f"{CURATED_ON}T00:00:00Z",
        stale=False,
    )
    bayes, _, _ = build_bayes_response(conn, paper_id, validate_paper=False)
    lmm, _ = build_lmm_response(conn, paper_id, validate_paper=False)
    meta_analysis, _ = build_meta_analysis_response(conn, paper_id, validate_paper=False)
    transparency = build_transparency_response(conn, paper_id, persisted_references=[], validate_paper=False)
    return DemoMethodSnapshots(
        statcheck=statcheck,
        transparency=transparency,
        lmm=lmm,
        bayes=bayes,
        meta_analysis=meta_analysis,
    )


def _method_summaries(papers: list[DemoPaper]) -> DemoMethodSummaries:
    methods = [paper.methods for paper in papers]
    data_statuses = [
        next(check.status for check in item.transparency.checks if check.key == "data_availability") for item in methods
    ]
    return DemoMethodSummaries(
        statcheck=StatcheckLibrarySummary(flagged=sum(item.statcheck.inconsistent > 0 for item in methods)),
        transparency=TransparencyLibrarySummary(
            data_detected=sum(status == "present" for status in data_statuses),
            data_not_detected=sum(status == "not-found" for status in data_statuses),
        ),
        lmm=LmmLibrarySummary(
            incomplete=sum(
                item.lmm.is_lmm and any(check.status == "not-found" for check in item.lmm.checks) for item in methods
            )
        ),
        bayes=BayesLibrarySummary(
            flagged=sum(
                item.bayes.completeness.is_bayesian
                and (
                    item.bayes.not_reproduced > 0
                    or any(check.status in ("not-found", "coherence-flag") for check in item.bayes.completeness.items)
                )
                for item in methods
            )
        ),
        meta_analysis=MetaLibrarySummary(
            incomplete=sum(
                item.meta_analysis.is_meta_analysis
                and any(check.status == "not-found" for check in item.meta_analysis.checks)
                for item in methods
            )
        ),
    )


def _summary(con: sqlite3.Connection) -> tuple[SummaryListItem, SummarizeJobResponse]:
    summary = con.execute(
        """SELECT id, scope_type, scope_ref_json, status, created_at
           FROM summaries WHERE id = ?""",
        (SUMMARY_ID,),
    ).fetchone()
    if summary is None:
        raise ValueError(f"curated summary {SUMMARY_ID} is missing")
    scope = _json(summary["scope_ref_json"], {})
    sentences: list[SummarySentenceResponse] = []
    for sentence in con.execute(
        """SELECT id, ordinal, text FROM summary_sentences
           WHERE summary_id = ? ORDER BY ordinal, id""",
        (SUMMARY_ID,),
    ):
        citations = []
        rows = con.execute(
            """SELECT cm.id mapping_id, cm.status, eq.id evidence_quote_id, eq.chunk_id,
                      eq.quote_text, eq.page_start, eq.page_end, eq.bbox_json,
                      eq.retrieval_confidence, eq.quote_confidence, eq.support_confidence,
                      c.paper_id, c.section, c.attachment_id
               FROM citation_mappings cm
               JOIN evidence_quotes eq ON eq.citation_mapping_id = cm.id
               JOIN chunks c ON c.id = eq.chunk_id
               WHERE cm.summary_sentence_id = ? ORDER BY cm.id""",
            (sentence["id"],),
        ).fetchall()
        for row in rows:
            if int(row["paper_id"]) not in CORPUS:
                raise ValueError("summary cites a paper outside the curated corpus")
            bbox = _json(row["bbox_json"], None)
            precision = None
            if isinstance(bbox, list):
                precision = next(
                    (
                        str(item["coordinate_precision"])
                        for item in bbox
                        if isinstance(item, dict) and item.get("coordinate_precision")
                    ),
                    None,
                )
            citations.append(
                SummaryCitationResponse(
                    mapping_id=int(row["mapping_id"]),
                    evidence_quote_id=int(row["evidence_quote_id"]),
                    chunk_id=int(row["chunk_id"]),
                    paper_id=int(row["paper_id"]),
                    paper_title=CORPUS[int(row["paper_id"])]["title"],
                    page_start=row["page_start"],
                    page_end=row["page_end"],
                    section=row["section"],
                    quote=row["quote_text"],
                    retrieval_confidence=float(row["retrieval_confidence"]),
                    quote_confidence=float(row["quote_confidence"]),
                    support_confidence=float(row["support_confidence"]),
                    status=row["status"],
                    coordinate_precision=precision,
                    bbox_json=bbox,
                    attachment_id=int(row["attachment_id"]),
                )
            )
        sentences.append(
            SummarySentenceResponse(
                sentence_id=int(sentence["id"]),
                ordinal=int(sentence["ordinal"]),
                text=sentence["text"],
                flagged=not citations or any(citation.status != "verified" for citation in citations),
                citations=citations,
            )
        )
    verified = sum(not sentence.flagged for sentence in sentences)
    item = SummaryListItem(
        summary_id=SUMMARY_ID,
        scope_type=summary["scope_type"],
        scope_label="What is the anomalous-is-bad bias?",
        status=summary["status"],
        created_at=str(summary["created_at"]),
        sentence_count=len(sentences),
        verified_sentence_count=verified,
        flagged_sentence_count=len(sentences) - verified,
    )
    response = SummarizeJobResponse(
        job_id=f"summary:{SUMMARY_ID}",
        status="done",
        summary_id=SUMMARY_ID,
        summary_status=summary["status"],
        source_chunk_count=len({citation.chunk_id for sentence in sentences for citation in sentence.citations}),
        section_filter=[str(value) for value in scope.get("sections") or []],
        sentences=sentences,
    )
    return item, response


def _public_help_corpus():
    """Bundle the real help corpus without embedding endpoint-shaped loopback URLs in the public artifact."""

    corpus = help_corpus()
    return corpus.model_copy(
        update={
            "sections": [
                section.model_copy(
                    update={
                        "html": re.sub(
                            r"https?://(?:localhost|127\.0\.0\.1):\d+",
                            "the local loopback address shown by Callosum",
                            section.html,
                        )
                    }
                )
                for section in corpus.sections
            ]
        }
    )


def export_snapshot(
    source_db: Path,
    output: Path,
    asset_dir: Path,
    library_state_path: Path = PROJECT_ROOT / "demo" / "library-state-v1.json",
    wip_state_path: Path = PROJECT_ROOT / "demo" / "wip-state-v1.json",
    synthesis_state_path: Path = PROJECT_ROOT / "demo" / "synthesis-state-v1.json",
    extended_state_path: Path = PROJECT_ROOT / "demo" / "extended-state-v1.json",
    ask_overview_path: Path = PROJECT_ROOT / "demo" / "ask-overview-v1.json",
) -> DemoSnapshot:
    if not source_db.is_file():
        raise ValueError(f"dedicated demo database does not exist: {source_db}")
    uri = f"file:{source_db.resolve().as_posix()}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    con.row_factory = sqlite3.Row
    if not library_state_path.is_file():
        raise ValueError(f"generated demo library state does not exist: {library_state_path}")
    library_state = DemoLibraryState.model_validate_json(library_state_path.read_bytes())
    wip_state = DemoWipState.model_validate_json(wip_state_path.read_bytes())
    synthesis_state = DemoSynthesisState.model_validate_json(synthesis_state_path.read_bytes())
    if not ask_overview_path.is_file():
        raise ValueError(f"generated demo Ask Overview does not exist: {ask_overview_path}")
    ask_overview = DemoAskOverviewState.model_validate_json(ask_overview_path.read_bytes())
    if not extended_state_path.is_file():
        raise ValueError(f"generated extended demo state does not exist: {extended_state_path}")
    extended_state = DemoExtendedState.model_validate_json(extended_state_path.read_bytes())
    # The WIP workspace stores compact receipts, not duplicate full results. Derive those receipts from the same
    # authentic saved Discover runs so visitors can see the cross-workspace connection without a second source.
    if extended_state.discover.funding_runs:
        funding_receipt = extended_state.discover.funding_runs[0].model_dump(mode="json")
        journal_report = extended_state.discover.journals.model_dump(mode="json")
        updated_wips = {}
        for manuscript_id, manuscript in wip_state.by_id.items():
            journal_receipt = {
                "id": 500 + int(manuscript_id),
                "manuscript_id": int(manuscript_id),
                "topic_id": journal_report.get("topic_id") or "anomalous-is-bad bias",
                "weighting": 0.35,
                "considered": journal_report.get("considered", 0),
                "shown": journal_report.get("shown", 0),
                "created_at": f"{CURATED_ON}T12:00:00Z",
            }
            updated_wips[manuscript_id] = manuscript.model_copy(
                update={"funding_runs": [funding_receipt], "journal_runs": [journal_receipt]}
            )
        wip_state = DemoWipState.model_validate(
            wip_state.model_copy(update={"by_id": updated_wips}).model_dump(mode="json")
        )
    engine = create_engine(f"sqlite:///file:{source_db.resolve().as_posix()}?mode=ro&uri=true")
    try:
        with engine.connect() as method_conn:
            papers = [
                _paper(con, paper_id, asset_dir, _method_snapshots(method_conn, paper_id), library_state)
                for paper_id in sorted(CORPUS)
            ]
            summary_item, summary = _summary(con)
            citation_ids = sorted({item.paper_id for item in extended_state.work.cite.suggestions})
            citation_renderings = {}
            citation_bibtex = {}
            for paper_id in citation_ids:
                rows = [_citation_row(paper_id)]
                citation_renderings[str(paper_id)] = render_papers(rows, style="apa", locale="en-US")
                citation_bibtex[str(paper_id)] = render_citations(rows, "bibtex")[0]
            workbench_exports = {}
            for project_id, project in extended_state.work.workbench_details.items():
                view = project.model_dump(mode="json")
                workbench_exports[str(project_id)] = {
                    "csv": workbench_export.FORMATS["csv"](view),
                    "metafor": workbench_export.FORMATS["metafor"](view),
                    "revman": workbench_export.FORMATS["revman"](view),
                    "audit": json.dumps(view, indent=2),
                }
            extended_state = extended_state.model_copy(
                update={
                    "work": extended_state.work.model_copy(
                        update={
                            "citation_renderings": citation_renderings,
                            "citation_bibtex": citation_bibtex,
                            "workbench_exports": workbench_exports,
                        }
                    )
                }
            )
    finally:
        con.close()
        engine.dispose()
    if ask_overview.summary_id != SUMMARY_ID:
        raise ValueError("saved demo Ask Overview targets a different synthesis")
    if ask_overview.verified_claim_count != sum(not sentence.flagged for sentence in summary.sentences or []):
        raise ValueError("saved demo Ask Overview claim count drifted; regenerate AI curation")
    if ask_overview.verified_claims_sha256 != verified_claims_sha256(summary):
        raise ValueError("saved demo Ask Overview claims drifted; regenerate AI curation")
    verified_ordinals = {sentence.ordinal for sentence in summary.sentences or [] if not sentence.flagged}
    if any(not set(item.claim_ordinals) <= verified_ordinals for item in ask_overview.overview):
        raise ValueError("saved demo Ask Overview references a non-verified claim")
    summary = summary.model_copy(update={"overview": ask_overview.overview})
    snapshot = DemoSnapshot(
        manifest=DemoManifest(
            snapshot_id="anomalous-is-bad-v1",
            snapshot_schema_version=SNAPSHOT_SCHEMA_VERSION,
            callosum_version="0.1.0",
            compatible_frontend_version="0.1.x",
            curated_on=CURATED_ON,
            title="Callosum demo: anomalous-is-bad bias",
            question="What is the anomalous-is-bad bias?",
            initial_paper_id=67,
            initial_summary_id=SUMMARY_ID,
            capabilities=DemoCapabilities(),
            workspace_capabilities=WORKSPACE_CAPABILITIES,
            trust_boundary="Static files only: no backend, database, credentials, AI calls, telemetry, or network egress.",
        ),
        api=DemoApi(
            health=HealthResponse(
                app="callosum-demo",
                verification_version="local-verifier-v1",
                db_reachable=False,
                db_migrated=False,
                read_only=True,
                onboarding_completed=True,
                app_version="0.1.0-demo",
            ),
            help_corpus=_public_help_corpus(),
            settings=SettingsStatus(
                provider="local",
                api_key_set=False,
                api_key_source=None,
                data_egress_enabled=False,
                egress_source="env",
                usage_events_enabled=True,
                publisher_defaults_set=True,
                publisher_weighting=0.35,
                publisher_breadth="standard",
                account=AccountStatus(configured=False, signed_in=False),
                onboarding_completed=True,
            ).model_dump(),
            papers=papers,
            axes=library_state.axes,
            axis_clusters=library_state.axis_clusters,
            tags=library_state.tags,
            tag_colors=library_state.tag_colors,
            # Scoped to the exported (browsable) papers only -- a metadata-and-evidence-only paper (no PDF)
            # never appears as a Library card, so it carries no suggested-tags entry either.
            suggested_tags={
                key: value
                for key, value in library_state.suggested_tags.items()
                if int(key) in {paper.list_item.id for paper in papers}
            },
            reading_queue=library_state.reading_queue,
            my_publications_profile=library_state.my_publications_profile,
            my_publications_dashboard=library_state.my_publications_dashboard,
            my_publications_citing=library_state.my_publications_citing,
            method_summaries=_method_summaries(papers),
            summary_index=[summary_item],
            summaries={str(SUMMARY_ID): summary},
            status=StatusResponse(
                jobs=[
                    StatusJob(
                        store="summary_jobs",
                        job_id=f"summary:{SUMMARY_ID}",
                        label=JOB_LABELS["summary_jobs"],
                        status="done",
                        nav={"workspace": "synthesis", "tab": "ask", "summary_id": SUMMARY_ID},
                        compute_kind=JOB_COMPUTE_KINDS["summary_jobs"],
                    )
                ]
            ),
            wip=wip_state,
            synthesis=synthesis_state,
            extended=extended_state,
        ),
    )
    payload = (
        json.dumps(snapshot.model_dump(mode="json", exclude_none=True), indent=2, sort_keys=True, ensure_ascii=False)
        + "\n"
    ).encode("utf-8")
    assert_public_snapshot_bytes(payload)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(payload)
    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-db",
        type=Path,
        required=True,
        help="Dedicated curated demo database; never an ordinary working database",
    )
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "demo" / "snapshot-v1.json")
    parser.add_argument("--asset-dir", type=Path, default=PROJECT_ROOT / "demo" / "documents")
    parser.add_argument(
        "--library-state",
        type=Path,
        default=PROJECT_ROOT / "demo" / "library-state-v1.json",
        help="Validated output from generate_demo_library_state.py",
    )
    parser.add_argument("--wip-state", type=Path, default=PROJECT_ROOT / "demo" / "wip-state-v1.json")
    parser.add_argument("--synthesis-state", type=Path, default=PROJECT_ROOT / "demo" / "synthesis-state-v1.json")
    parser.add_argument("--extended-state", type=Path, default=PROJECT_ROOT / "demo" / "extended-state-v1.json")
    parser.add_argument("--ask-overview", type=Path, default=PROJECT_ROOT / "demo" / "ask-overview-v1.json")
    parser.add_argument(
        "--confirm-public-demo-source",
        action="store_true",
        help="Required acknowledgement that the named database is dedicated and every selected byte may be public",
    )
    args = parser.parse_args()
    if not args.confirm_public_demo_source:
        parser.error("--confirm-public-demo-source is required; do not point this exporter at an ordinary library")
    export_snapshot(
        args.source_db,
        args.output,
        args.asset_dir,
        args.library_state,
        args.wip_state,
        args.synthesis_state,
        args.extended_state,
        args.ask_overview,
    )
    print(f"validated public demo snapshot: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
