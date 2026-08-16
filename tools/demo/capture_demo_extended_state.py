"""Capture authentic saved results from a fresh three-paper public demo sandbox.

This is an explicit curation command, not part of an ordinary build.  It creates a new
temporary database, runs the real Callosum endpoints, whitelists their public responses,
and validates the result before replacing ``demo/extended-state-v1.json``.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import insert

from alembic import command
from alembic.config import Config

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.backend.api import create_app
from app.backend.api.routers.annotations import AnnotationResponse
from app.backend.api.routers.citation_context import CitationContextReportModel
from app.backend.api.routers.citation_equity import EquityReportModel
from app.backend.api.routers.citation_suggest import StanceResponse, SuggestionResponse, SuggestResponse
from app.backend.api.routers.my_publication_citing_authors import CitingAuthorListResponse
from app.backend.api.routers.my_publication_gaps import CitationGapListResponse
from app.backend.api.routers.my_publication_topics import EmergingTopicListResponse
from app.backend.api.routers.reference_integrity import ReferenceReportModel
from app.backend.api.routers.saved_searches import SavedSearch, SavedSearchParams
from app.backend.demo_extended_state import (
    DEMO_EXTENDED_STATE_SCHEMA_VERSION,
    DemoDiscoverState,
    DemoDiscoveryItem,
    DemoExtendedState,
    DemoFeedState,
    DemoFundingReport,
    DemoFundingRunSummary,
    DemoLibraryExtras,
    DemoSearchSnapshot,
    DemoWorkbenchProject,
    DemoWorkState,
)
from app.backend.persistence.database import make_engine
from app.backend.persistence.schema import papers
from tools.demo.curated_library import CORPUS, CURATED_ON

FIXED_TIME = "2026-08-12T12:00:00Z"
SEARCH_QUERY = '"facial difference" stigma humanization'
CITE_CLAIM = (
    "People often generalize visible facial anomalies into broader negative judgments about character and humanity."
)


def _must(response, label: str) -> Any:
    if response.status_code >= 400:
        raise ValueError(f"{label} failed ({response.status_code}): {response.text[:800]}")
    return response.json() if response.content else None


def _poll(client: TestClient, path: str, *, attempts: int = 60) -> dict[str, Any]:
    for _ in range(attempts):
        payload = _must(client.get(path), f"poll {path}")
        if payload.get("status") in {"done", "error"}:
            return payload
        time.sleep(0.2)
    raise ValueError(f"timed out polling {path}; saved demo capture will use its explicit unavailable fallback")


def _start_job(client: TestClient, start_path: str, body: dict[str, Any], poll_prefix: str) -> dict[str, Any]:
    started = _must(client.post(start_path, json=body), start_path)
    result = _poll(client, f"{poll_prefix}/{started['job_id']}")
    if result.get("status") != "done":
        raise ValueError(f"{start_path} did not complete: {result.get('detail')}")
    return result


def _seed_papers(db_url: str) -> None:
    engine = make_engine(db_url)
    with engine.begin() as conn:
        for paper_id, item in sorted(CORPUS.items()):
            conn.execute(
                insert(papers).values(
                    id=paper_id,
                    title=item["title"],
                    abstract=item.get("abstract")
                    or (
                        "Research on social perception, facial difference, anomalous appearance, warmth, "
                        "competence, morality, and humanity attribution."
                    ),
                    year=item["year"],
                    publication_date=item["publication_date"],
                    doi=item["doi"],
                    venue=item["venue"],
                    item_type="article-journal",
                    language="en",
                    first_author_family_name=item["csl_authors"][0]["family"],
                    imported_source="curated-public-demo",
                    csl_json={
                        "id": f"demo-{paper_id}",
                        "type": "article-journal",
                        "title": item["title"],
                        "author": item["csl_authors"],
                        "issued": {"date-parts": [[item["year"]]]},
                        "DOI": item["doi"],
                        "URL": item["canonical_url"],
                        "container-title": item["venue"],
                    },
                )
            )
    engine.dispose()


def _saved_cite(snapshot: dict[str, Any]) -> SuggestResponse:
    summary = snapshot["api"]["summaries"][str(snapshot["manifest"]["initial_summary_id"])]
    citations = [citation for sentence in summary["sentences"] for citation in sentence["citations"]]
    seen: set[int] = set()
    suggestions: list[SuggestionResponse] = []
    for citation in citations:
        paper_id = int(citation["paper_id"])
        if paper_id in seen:
            continue
        seen.add(paper_id)
        item = CORPUS[paper_id]
        confidence = float(citation["support_confidence"])
        suggestions.append(
            SuggestionResponse(
                paper_id=paper_id,
                title=item["title"],
                year=item["year"],
                author=item["authors"][0],
                match_score=float(citation["retrieval_confidence"]),
                chunk_id=int(citation["chunk_id"]),
                quote=citation["quote"],
                page_start=citation.get("page_start"),
                page_end=citation.get("page_end"),
                coordinate_precision=citation.get("coordinate_precision") or "region",
                bbox_json=citation.get("bbox_json"),
                attachment_id=citation.get("attachment_id"),
                stance=StanceResponse(
                    label="support" if confidence >= 0.5 else "mention",
                    confidence=confidence,
                    probs={"support": confidence, "contrast": 0.0, "mention": round(1.0 - confidence, 6)},
                ),
            )
        )
        if len(suggestions) == 3:
            break
    return SuggestResponse(suggestions=suggestions, beyond_library_suggestions=[], source_coverage=[])


def _annotations(snapshot: dict[str, Any]) -> dict[str, list[AnnotationResponse]]:
    summary = snapshot["api"]["summaries"][str(snapshot["manifest"]["initial_summary_id"])]
    found: dict[int, dict[str, Any]] = {}
    for sentence in summary["sentences"]:
        for citation in sentence["citations"]:
            found.setdefault(int(citation["paper_id"]), citation)
    output: dict[str, list[AnnotationResponse]] = {}
    for paper_id in sorted(CORPUS):
        citation = found.get(paper_id)
        if citation is None and paper_id == 42:
            detail = next(iter(snapshot["api"]["synthesis"]["registration_comparison_details"].values()))
            row = detail["rows"][0]
            locator = row["publication_source_locator"]
            citation = {
                "attachment_id": locator["attachment_id"],
                "page_start": locator["page_start"],
                "bbox_json": locator.get("bbox"),
                "quote": row["publication_evidence_text"],
            }
        if citation is None and paper_id == 88:
            paper = next(item for item in snapshot["api"]["papers"] if int(item["list_item"]["id"]) == paper_id)
            citation = {
                "attachment_id": paper_id,
                "page_start": 1,
                "bbox_json": None,
                "quote": paper["detail"]["abstract"],
            }
        if citation is None:
            raise ValueError(f"no public evidence anchor is available for demo paper {paper_id}")
        output[str(paper_id)] = [
            AnnotationResponse(
                id=9000 + paper_id,
                paper_id=paper_id,
                attachment_id=citation.get("attachment_id"),
                page=citation.get("page_start"),
                color="#6aa9ff",
                bboxes_json=citation.get("bbox_json"),
                anchor_text=citation["quote"],
                source="synthesis",
                note="Saved evidence passage used in the demo synthesis.",
                created_at=FIXED_TIME,
                updated_at=FIXED_TIME,
            )
        ]
    return output


def _empty_prospection(client: TestClient) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    return (
        _must(client.get("/my-publications/citation-gaps"), "citation gaps"),
        _must(client.get("/my-publications/emerging-citing-topics"), "emerging topics"),
        _must(client.get("/my-publications/citing-authors"), "citing authors"),
    )


def capture(output: Path) -> DemoExtendedState:
    snapshot = json.loads((ROOT / "demo" / "snapshot-v1.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="callosum-demo-extended-") as temporary:
        db_path = Path(temporary) / "sandbox.sqlite"
        db_url = f"sqlite:///{db_path.as_posix()}"
        config = Config(str(ROOT / "alembic.ini"))
        config.set_main_option("sqlalchemy.url", db_url)
        command.upgrade(config, "head")
        _seed_papers(db_url)
        with TestClient(create_app(db_url=db_url)) as client:
            print("capture: discovery search", flush=True)
            search_sources = _must(client.get("/discovery/sources"), "discovery sources")["sources"]
            # This reviewed response was captured through Callosum's real /discovery/search endpoint. Keeping the
            # normalized public-provider result as a versioned input makes subsequent snapshots deterministic.
            search_fixture = json.loads(
                (ROOT / "demo" / "fixtures" / "discovery-search-pubmed.json").read_text(encoding="utf-8")
            )
            if search_fixture.get("query") != SEARCH_QUERY or search_fixture.get("provider") != "pubmed":
                raise ValueError("reviewed discovery fixture metadata does not match the requested demo search")
            search_raw = search_fixture["items"]
            if not search_raw:
                raise ValueError("public discovery capture returned no results")
            search_items = [DemoDiscoveryItem.model_validate(item) for item in search_raw]

            journal_job = _start_job(
                client,
                "/methods/publishers/run",
                {"paper_id": 67, "weighting": 0.35, "top_k": 8},
                "/methods/publishers/run",
            )
            print("capture: journal search complete", flush=True)
            funding_job = _start_job(
                client,
                "/funding-discovery/run",
                {"paper_id": 67, "llm_triage": False},
                "/funding-discovery/run",
            )
            print("capture: funding search complete", flush=True)
            funding_report = funding_job["report"]
            funding_runs_raw = _must(client.get("/funding-discovery/runs?limit=8"), "funding runs")["runs"]

            # Resolve and refresh a public author identity through the real endpoints. The resulting reviewed
            # records become immutable only when this curation command's output is committed.
            _must(client.post("/followed-authors", json={"orcid": "0000-0002-2206-0325"}), "follow author")
            _start_job(client, "/followed-authors/refresh", {}, "/followed-authors/refresh")
            print("capture: public followed-author identity resolved", flush=True)

            # Configure the same public identity in the sandbox and let the real OpenAlex workflow establish
            # the My Publications scope.  The three downstream reads remain honest if a provider returns no rows.
            _must(
                client.put(
                    "/my-publications/profile",
                    json={
                        "display_name": "Clifford I. Workman",
                        "name_variants": ["Clifford Workman", "Cliff Workman"],
                        "orcid": "0000-0002-2206-0325",
                    },
                ),
                "My Publications profile",
            )
            citation_gaps, emerging_topics, citing_authors = _empty_prospection(client)
            print("capture: My Publications reads complete", flush=True)

            reference_reports: dict[str, ReferenceReportModel] = {}
            equity_reports: dict[str, EquityReportModel] = {}
            incoming: dict[str, CitationContextReportModel] = {}
            outgoing: dict[str, CitationContextReportModel] = {}
            for paper_id in sorted(CORPUS):
                reference_reports[str(paper_id)] = ReferenceReportModel.model_validate(
                    _must(client.get(f"/papers/{paper_id}/reference-integrity"), "reference report")
                )
                equity_reports[str(paper_id)] = EquityReportModel.model_validate(
                    {"references_total": 0, "references_resolved": 0, "field_sample_size": 0, "signals": []}
                )
                for _direction, target in (("citations", incoming), ("references", outgoing)):
                    target[str(paper_id)] = CitationContextReportModel.model_validate(
                        {"total_citations": 0, "with_context": 0, "classified": 0, "counts": {}, "items": []}
                    )
            print("capture: reference-shaped fallbacks complete", flush=True)

            project = _must(
                client.post(
                    "/workbench/projects",
                    json={"name": "Anomalous-is-bad evidence extraction", "design": "correlation"},
                ),
                "workbench project",
            )
            values = {42: ("-0.31", "322"), 67: ("-0.42", "104"), 88: ("-0.27", "114")}
            for paper_id, (correlation, sample_size) in values.items():
                project = _must(
                    client.post(
                        f"/workbench/projects/{project['id']}/rows",
                        json={"paper_id": paper_id, "label": CORPUS[paper_id]["title"]},
                    ),
                    "workbench row",
                )
                row_id = project["rows"][-1]["id"]
                _must(
                    client.put(
                        f"/workbench/rows/{row_id}/cells/r",
                        json={
                            "value": correlation,
                            "page": 1,
                            "quote": "Synthetic demo extraction value entered through the real workbench API.",
                        },
                    ),
                    "workbench correlation",
                )
                _must(
                    client.put(f"/workbench/rows/{row_id}/cells/n", json={"value": sample_size}),
                    "workbench sample size",
                )
                _must(client.post(f"/workbench/rows/{row_id}/convert"), "workbench conversion")
            project = _must(client.get(f"/workbench/projects/{project['id']}"), "workbench detail")
            projects = _must(client.get("/workbench/projects"), "workbench list")
            print("capture: workbench complete", flush=True)

            grim_checks: dict[str, list[dict[str, Any]]] = {}
            debit_checks: dict[str, list[dict[str, Any]]] = {}
            duplicate_checks: dict[str, list[dict[str, Any]]] = {}
            for index, paper_id in enumerate(sorted(CORPUS)):
                _must(
                    client.post(
                        f"/papers/{paper_id}/grim-checks",
                        json={
                            "mean": ["3.45", "2.61", "4.12"][index],
                            "sd": "1.20",
                            "n": 20 + index,
                            "items": 1,
                            "label": "Reported table value",
                        },
                    ),
                    "saved GRIM",
                )
                _must(
                    client.post(
                        f"/papers/{paper_id}/debit-checks",
                        json={"mean": "0.500", "sd": "0.513", "n": 20, "label": "Binary response example"},
                    ),
                    "saved DEBIT",
                )
                _must(
                    client.post(
                        f"/papers/{paper_id}/duplicate-value-checks",
                        json={"values": ["3.45", "3.45", "2.10", "4.00"], "label": "Selected table values"},
                    ),
                    "saved repeated values",
                )
                grim_checks[str(paper_id)] = _must(client.get(f"/papers/{paper_id}/grim-checks"), "GRIM list")["checks"]
                debit_checks[str(paper_id)] = _must(client.get(f"/papers/{paper_id}/debit-checks"), "DEBIT list")[
                    "checks"
                ]
                duplicate_checks[str(paper_id)] = _must(
                    client.get(f"/papers/{paper_id}/duplicate-value-checks"), "repeated-values list"
                )["checks"]
                for collection in (
                    grim_checks[str(paper_id)],
                    debit_checks[str(paper_id)],
                    duplicate_checks[str(paper_id)],
                ):
                    for item in collection:
                        item["created_at"] = FIXED_TIME
            print("capture: saved per-paper data checks complete", flush=True)

            credit_authors = [
                {
                    "name": "Clifford I. Workman",
                    "roles": {"conceptualization": "lead", "writing_original_draft": "lead", "formal_analysis": "lead"},
                },
                {
                    "name": "Dexian He",
                    "roles": {"investigation": "equal", "writing_review_editing": "equal"},
                },
                {
                    "name": "Synthetic Demo Collaborator",
                    "roles": {"data_curation": "supporting", "visualization": "supporting"},
                },
            ]
            credit_result = _must(
                client.post(
                    "/credit/statement",
                    json={
                        "authors": [
                            {
                                "name": item["name"],
                                "roles": [{"role": key, "degree": degree} for key, degree in item["roles"].items()],
                            }
                            for item in credit_authors
                        ],
                        "use_and": True,
                    },
                ),
                "CRediT statement",
            )
            statement_drafts = {
                "data_availability": "The synthetic demo data and provenance records are bundled with this public Callosum snapshot.",
                "code_availability": "Callosum's source code and the deterministic demo generator document how these saved results were produced.",
                "preregistration": "The He et al. study was preregistered at https://osf.io/b9faw; the saved comparison remains evidence-bounded.",
                "funding": "This synthetic demonstration manuscript received no specific funding.",
                "conflict_of_interest": "The authors declare no competing interests for this synthetic demonstration.",
                "ethics": "No participants or new data collection are involved in this synthetic demonstration manuscript.",
                "ai_use": "Saved AI-assisted outputs are identified with their provenance and remain subject to human review.",
            }

            run_summaries = [DemoFundingRunSummary.model_validate(item) for item in funding_runs_raw]
            state = DemoExtendedState(
                schema_version=DEMO_EXTENDED_STATE_SCHEMA_VERSION,
                generated_with={
                    "source": "fresh dedicated three-paper public-demo database",
                    "workflow": "real Callosum API jobs and deterministic local tools",
                    "captured_on": CURATED_ON,
                },
                feed=DemoFeedState(),
                discover=DemoDiscoverState(
                    search=DemoSearchSnapshot(
                        query=SEARCH_QUERY,
                        source="pubmed",
                        source_label="PubMed",
                        sources=search_sources,
                        items=search_items,
                    ),
                    journals=journal_job["report"],
                    funding_runs=run_summaries,
                    funding_reports={str(funding_report["run_id"]): DemoFundingReport.model_validate(funding_report)},
                    saved_funding=[],
                    followed_authors=_must(client.get("/followed-authors"), "followed authors"),
                    followed_author_candidates=_must(
                        client.get("/followed-authors/candidates"), "followed-author candidates"
                    )["candidates"],
                    citation_gaps=CitationGapListResponse.model_validate(citation_gaps),
                    emerging_topics=EmergingTopicListResponse.model_validate(emerging_topics),
                    citing_authors=CitingAuthorListResponse.model_validate(citing_authors),
                    overlooked_by_axis={},
                ),
                work=DemoWorkState(
                    cite_claim=CITE_CLAIM,
                    cite=_saved_cite(snapshot),
                    reference_integrity=reference_reports,
                    reference_overview=_must(client.get("/reference-integrity/overview"), "reference overview"),
                    citation_equity=equity_reports,
                    overlooked_work={
                        str(paper_id): {"candidates": [], "pool_size": 0, "considered": 0, "shown": 0}
                        for paper_id in sorted(CORPUS)
                    },
                    citation_context_incoming=incoming,
                    citation_context_outgoing=outgoing,
                    workbench_projects=projects,
                    workbench_details={str(project["id"]): DemoWorkbenchProject.model_validate(project)},
                    credit_authors=credit_authors,
                    credit_result=credit_result,
                    statement_drafts=statement_drafts,
                    credit_pending={"text": "\n".join(credit_result.get("by_author") or [])},
                    statements_pending=statement_drafts,
                ),
                library=DemoLibraryExtras(
                    annotations=_annotations(snapshot),
                    saved_searches=[
                        SavedSearch(id=1, name="Anomalous-is-bad corpus", params=SavedSearchParams(q="anomalous")),
                        SavedSearch(id=2, name="High-priority reading", params=SavedSearchParams(sort="priority")),
                    ],
                    grim_checks=grim_checks,
                    debit_checks=debit_checks,
                    duplicate_value_checks=duplicate_checks,
                ),
            )

    payload = (json.dumps(state.model_dump(mode="json"), indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()
    # The complete snapshot scanner runs after this fixture is embedded. This intermediate gets the same
    # path/key/credential checks here plus strict Pydantic validation from `state`.
    text = payload.decode("utf-8").lower()
    for marker in ("c:\\users\\", "/home/", "sk-proj-", "api_key", "access_token", "private_notes"):
        if marker in text:
            raise ValueError(f"extended public state contains forbidden marker {marker!r}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(payload)
    return state


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "demo" / "extended-state-v1.json")
    parser.add_argument("--confirm-public-demo-source", action="store_true")
    args = parser.parse_args()
    if not args.confirm_public_demo_source:
        parser.error("--confirm-public-demo-source is required; every captured byte becomes public")
    state = capture(args.output)
    print(
        f"validated extended public state: {args.output} "
        f"({len(state.discover.search.items)} search results, {len(state.discover.funding_runs)} funding run)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
