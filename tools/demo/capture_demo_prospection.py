"""Capture public My Publications graph snapshots from a fresh five-paper sandbox.

This explicit curation command performs OpenAlex metadata egress. It never reads an
ordinary Callosum database: it migrates a temporary database, inserts the allowlisted
demo corpus, confirms the four Workman publications, runs the three production graph
workflows plus the real domain-decomposition job, validates their live response models,
and replaces only those fields in the saved extended demo state.
"""

# ruff: noqa: E402, I001

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.backend.api import create_app
from app.backend.api.routers.beyond_library_saved import SavedBeyondLibraryListResponse
from app.backend.api.routers.gaps import GapsListResponse
from app.backend.api.routers.my_publication_citing_authors import CitingAuthorListResponse
from app.backend.api.routers.my_publication_gaps import CitationGapListResponse
from app.backend.api.routers.my_publication_topics import EmergingTopicListResponse
from app.backend.api.routers.my_publications import (
    CitingResponse,
    CitingWorkResponse,
    DashboardMetrics,
    DashboardResponse,
    PaperCitation,
    ProfileResponse,
    YearCount,
    YearImpact,
)
from app.backend.api.routers.overlooked import OverlookedListResponse
from app.backend.demo_extended_state import DemoExtendedState
from app.backend.demo_library_state import DemoLibraryState
from tools.demo.capture_demo_extended_state import CITE_CLAIM, _seed_papers
from tools.demo.curated_library import CORPUS, CURATED_ON
from tools.demo.generate_demo_library_state import AUTOMATED_AXIS_ID, MY_PUBLICATIONS_PAPER_IDS, RESEARCH_SUMMARY

PROFILE = {
    "display_name": "Clifford I. Workman",
    "name_variants": ["Clifford Workman", "Cliff Workman"],
    "orcid": "0000-0002-2206-0325",
}
OPENALEX_ROOT = "https://api.openalex.org"
OPENALEX_MAILTO = "cliff.workman@nih.gov"


def _openalex_json(path: str, params: dict[str, str]) -> dict[str, Any]:
    response = httpx.get(
        f"{OPENALEX_ROOT}{path}",
        params={**params, "mailto": OPENALEX_MAILTO},
        headers={"User-Agent": f"Callosum public-demo curation; mailto:{OPENALEX_MAILTO}"},
        timeout=30,
    )
    response.raise_for_status()
    value = response.json()
    if not isinstance(value, dict):
        raise ValueError("OpenAlex returned a non-object response")
    return value


def _curated_publication_state() -> tuple[DashboardResponse, dict[str, CitingResponse]]:
    paper_citations: dict[str, PaperCitation] = {}
    citing: dict[str, CitingResponse] = {}
    by_year: dict[int, YearImpact] = {}
    for paper_id in MY_PUBLICATIONS_PAPER_IDS:
        item = CORPUS[paper_id]
        payload = _openalex_json(
            "/works",
            {
                "filter": f"doi:{item['doi']}",
                "select": "id,doi,title,publication_year,cited_by_count,authorships",
                "per-page": "5",
            },
        )
        exact = [
            work
            for work in payload.get("results") or []
            if str(work.get("doi") or "").lower().removeprefix("https://doi.org/") == item["doi"]
        ]
        expected_work_id = item.get("openalex_work_id")
        if len(exact) != 1 and expected_work_id:
            # A very recently indexed work can briefly have two not-yet-merged OpenAlex work records sharing
            # the same DOI (a real, verified data-quality artifact, not a bug here) -- disambiguate using the
            # canonical work id already verified when this paper was curated, rather than relaxing to "first".
            exact = [work for work in exact if str(work.get("id") or "").rsplit("/", 1)[-1] == expected_work_id]
        if len(exact) != 1:
            raise ValueError(f"OpenAlex did not return exactly one exact work for curated DOI {item['doi']}")
        work = exact[0]
        authors = [str((row.get("author") or {}).get("display_name") or "") for row in work.get("authorships") or []]
        if "Clifford I. Workman" not in authors:
            raise ValueError(f"curated DOI {item['doi']} no longer resolves to the expected Workman authorship")
        work_id = str(work.get("id") or "").rsplit("/", 1)[-1]
        if not work_id.startswith("W"):
            raise ValueError(f"curated DOI {item['doi']} has no valid OpenAlex work id")
        cited_by_count = int(work.get("cited_by_count") or 0)
        paper_citations[str(paper_id)] = PaperCitation(
            cited_by_count=cited_by_count,
            openalex_work_id=work_id,
        )
        by_year[item["year"]] = YearImpact(year=item["year"], works_count=1, cited_by_count=cited_by_count)

        citing_payload = _openalex_json(
            "/works",
            {
                "filter": f"cites:{work_id}",
                "select": "doi,title,publication_year,cited_by_count,authorships",
                "per-page": "100",
            },
        )
        works = []
        for cited in citing_payload.get("results") or []:
            raw_doi = str(cited.get("doi") or "").lower().removeprefix("https://doi.org/") or None
            works.append(
                CitingWorkResponse(
                    doi=raw_doi,
                    title=cited.get("title"),
                    year=cited.get("publication_year"),
                    cited_by_count=int(cited.get("cited_by_count") or 0),
                    authors=[
                        str((row.get("author") or {}).get("display_name") or "")
                        for row in cited.get("authorships") or []
                        if (row.get("author") or {}).get("display_name")
                    ],
                    in_library=bool(raw_doi and raw_doi in {entry["doi"] for entry in CORPUS.values()}),
                )
            )
        works.sort(key=lambda row: (-(row.year or 0), (row.title or "").casefold(), row.doi or ""))
        total = int((citing_payload.get("meta") or {}).get("count") or len(works))
        citing[work_id] = CitingResponse(works=works, total=total, capped=total > len(works))

    counts = [item.cited_by_count for item in paper_citations.values()]
    pubs_by_year = [YearCount(year=year, count=impact.works_count) for year, impact in sorted(by_year.items())]
    return (
        DashboardResponse(
            status="ok",
            name="Clifford I. Workman — demo corpus",
            as_of=f"{CURATED_ON}T00:00:00Z",
            metrics=DashboardMetrics(
                works_count=len(counts),
                cited_by_count=sum(counts),
                h_index=sum(count >= rank for rank, count in enumerate(sorted(counts, reverse=True), start=1)),
                i10_index=sum(count >= 10 for count in counts),
            ),
            pubs_by_year=pubs_by_year,
            counts_by_year=[by_year[year] for year in sorted(by_year)],
            indexed_works=len(counts),
            in_library=len(counts),
            gap=0,
            research_summary=RESEARCH_SUMMARY,
            # domains is populated afterward in capture() from the real /my-publications/domains job output --
            # never fabricated here (a hardcoded placeholder Domain object previously lived at this exact spot).
            domains=[],
            missing_works=[],
            dismissed_works=[],
            paper_citations=paper_citations,
        ),
        citing,
    )


def _must(response: Any, label: str) -> Any:
    if response.status_code >= 400:
        raise ValueError(f"{label} failed ({response.status_code}): {response.text[:800]}")
    return response.json() if response.content else None


def _job(client: TestClient, start_path: str, poll_path: str, body: dict[str, Any]) -> dict[str, Any]:
    started = _must(client.post(start_path, json=body), start_path)
    for _ in range(300):
        result = _must(client.get(f"{poll_path}/{started['job_id']}"), poll_path)
        if result.get("status") == "done":
            return result
        if result.get("status") == "error":
            raise ValueError(f"{start_path} failed: {result.get('detail')}")
        time.sleep(0.25)
    raise ValueError(f"timed out waiting for {start_path}")


def capture(output: Path, library_output: Path) -> tuple[DemoExtendedState, DemoLibraryState]:
    current = DemoExtendedState.model_validate_json(output.read_bytes())
    library_current = DemoLibraryState.model_validate_json(library_output.read_bytes())
    with tempfile.TemporaryDirectory(prefix="callosum-demo-prospection-") as temporary:
        database = Path(temporary) / "sandbox.sqlite"
        db_url = f"sqlite:///{database.as_posix()}"
        config = Config(str(ROOT / "alembic.ini"))
        config.set_main_option("sqlalchemy.url", db_url)
        command.upgrade(config, "head")
        _seed_papers(db_url)
        with TestClient(create_app(db_url=db_url)) as client:
            _must(client.put("/my-publications/profile", json=PROFILE), "save demo profile")
            refresh = _job(client, "/my-publications/refresh", "/my-publications/refresh", {})
            summary = refresh.get("summary") or {}
            expected_in_library = len(MY_PUBLICATIONS_PAPER_IDS)
            if summary.get("status") != "ok" or int(summary.get("in_library") or 0) != expected_in_library:
                raise ValueError(
                    f"demo author resolution did not identify exactly {expected_in_library} in-library works: {summary}"
                )
            decisions = [(paper_id, "confirmed") for paper_id in MY_PUBLICATIONS_PAPER_IDS] + [(88, "rejected")]
            for paper_id, decision in decisions:
                _must(
                    client.post(
                        "/my-publications/decide",
                        json={"paper_id": paper_id, "decision": decision},
                    ),
                    f"set My Publications decision for {paper_id}",
                )

            jobs = (
                ("/my-publications/citation-gaps", "/my-publications/citation-gaps/refresh"),
                (
                    "/my-publications/emerging-citing-topics",
                    "/my-publications/emerging-citing-topics/refresh",
                ),
                ("/my-publications/citing-authors", "/my-publications/citing-authors/refresh"),
            )
            for _read_path, refresh_path in jobs:
                _job(client, refresh_path, refresh_path, {"domain_keys": []})
            citation_gaps = CitationGapListResponse.model_validate(_must(client.get(jobs[0][0]), "read citation gaps"))
            emerging_topics = EmergingTopicListResponse.model_validate(
                _must(client.get(jobs[1][0]), "read emerging topics")
            )
            citing_authors = CitingAuthorListResponse.model_validate(
                _must(client.get(jobs[2][0]), "read citing authors")
            )
            profile = ProfileResponse.model_validate(
                _must(client.get("/my-publications/profile"), "read My Publications profile")
            )
            # Real domain decomposition (cap-domains, backlog #57-adjacent 2026-08-30 demo-coverage fixwave):
            # requires MIN_DOMAIN_PAPERS=4 confirmed My-Publications papers, now met above. Never a hardcoded
            # placeholder -- this is the live job's own output, fetched back via the dashboard read below.
            _job(client, "/my-publications/domains", "/my-publications/domains", {})
            live_dashboard = DashboardResponse.model_validate(
                _must(client.get("/my-publications/dashboard"), "read My Publications dashboard")
            )
            # cap-overlooked (same 2026-08-30 fixwave): the axis-scoped Overlooked-work lens, scored against the
            # curated axis (not a My-Publications concept) -- was previously hardcoded to {} in
            # capture_demo_extended_state.py, never a real refresh. compute_overlooked() only needs a real axis
            # row + label (get_axis(conn, axis_id) -- no local paper-scoring is required), so this sandbox
            # creates its own throwaway axis rather than reusing the curated snapshot's fixed AUTOMATED_AXIS_ID
            # (a stable id from a different database that doesn't exist in this temp sandbox). The label must
            # resolve to a real OpenAlex Topic (compute_overlooked's own external-fetch step) -- the curated
            # axis's real display label "Anomalous-is-bad bias" is a bespoke in-house construct name that does
            # NOT resolve (confirmed empirically), so this uses "Face Recognition and Perception", one of the
            # corpus's own real OpenAlex automatic_topics (curated_library.py), shared by 3 of the 5 papers.
            sandbox_axis = _must(
                client.post("/axes", json={"label": "Face Recognition and Perception"}), "create sandbox axis"
            )
            sandbox_axis_id = sandbox_axis["id"]
            _job(client, "/overlooked/refresh", "/overlooked/refresh", {"axis_id": sandbox_axis_id})
            overlooked = OverlookedListResponse.model_validate(
                _must(client.get(f"/overlooked?axis_id={sandbox_axis_id}"), "read overlooked-work lens")
            )
            # cap-literature-gaps (same fixwave): the whole-library backward gap-finder (works cited by >=
            # GAP_MIN_CITATIONS=3 of the curated papers, absent from the library) -- previously hardcoded to
            # {candidates: [], computed_at: null} in demo-runtime.js. Whole-library scope (no axis_id), matching
            # the "backward" default; the thematically tight 5-paper corpus is likely to share common citations.
            _job(client, "/gaps/refresh", "/gaps/refresh", {"direction": "backward"})
            literature_gaps = GapsListResponse.model_validate(
                _must(client.get("/gaps?direction=backward"), "read literature gaps")
            )
            # cap-beyond-library (same fixwave): a real /citations/suggest call (the same live search the web
            # Cite pane and LibreOffice Suggest dialog already use) against a real claim sentence, explicitly
            # "Saved for later" via the unchanged save endpoint -- previously hardcoded to {items: []}.
            suggest_result = _must(
                client.post(
                    "/citations/suggest",
                    json={"text": CITE_CLAIM, "top_k": 3, "include_beyond_library": True, "beyond_top_k": 5},
                ),
                "citation suggest (beyond-library)",
            )
            beyond_candidates = suggest_result.get("beyond_library_suggestions") or []
            if beyond_candidates:
                saved = _must(
                    client.post(
                        "/citations/beyond-library/save",
                        json={k: v for k, v in beyond_candidates[0].items() if k not in ("in_library", "stance")},
                    ),
                    "save beyond-library suggestion",
                )
                beyond_library_saved = SavedBeyondLibraryListResponse(items=[saved])
            else:
                beyond_library_saved = current.discover.beyond_library_saved

    dashboard, citing = _curated_publication_state()
    dashboard.openalex_extra = live_dashboard.openalex_extra
    dashboard.domains = live_dashboard.domains

    if not emerging_topics.topics:
        raise ValueError(
            "public prospection capture returned an empty core result-bearing surface: "
            f"gaps={len(citation_gaps.candidates)}, topics={len(emerging_topics.topics)}, "
            f"authors={len(citing_authors.authors)}"
        )
    if not citation_gaps.candidates:
        citation_gaps = current.discover.citation_gaps
    if dashboard.status != "ok" or dashboard.in_library != expected_in_library or not dashboard.counts_by_year:
        raise ValueError(
            f"public My Publications dashboard did not return the expected {expected_in_library}-paper chart snapshot"
        )
    if not dashboard.domains:
        raise ValueError(
            "the real /my-publications/domains job returned no domains against the now-4-paper curated corpus "
            "-- refusing to silently fall back to a fabricated placeholder"
        )
    if not overlooked.candidates:
        raise ValueError(
            "the real /overlooked/refresh job returned no candidates for the curated axis -- refusing to "
            "silently fall back to an empty placeholder"
        )
    discover = current.discover.model_copy(
        update={
            "citation_gaps": citation_gaps,
            "emerging_topics": emerging_topics,
            "citing_authors": citing_authors,
            "overlooked_by_axis": {str(AUTOMATED_AXIS_ID): overlooked},
            "literature_gaps": literature_gaps,
            "beyond_library_saved": beyond_library_saved,
        }
    )
    generated_with = dict(current.generated_with)
    generated_with["my_publications_prospection"] = (
        "fresh dedicated five-paper sandbox (four confirmed My Publications); explicit bounded OpenAlex "
        "metadata refresh; real /my-publications/domains decomposition; saved one-paper citation-gap fallback "
        "retained when the four-paper refresh returned no candidates"
    )
    state = DemoExtendedState.model_validate(
        current.model_copy(update={"discover": discover, "generated_with": generated_with}).model_dump(mode="json")
    )
    output.write_text(
        json.dumps(state.model_dump(mode="json"), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    library_generated_with = dict(library_current.generated_with)
    library_generated_with["my_publications_dashboard"] = (
        "fresh dedicated five-paper sandbox (four confirmed My Publications); explicit OpenAlex author and "
        "works refresh; real /my-publications/domains decomposition"
    )
    library_state = DemoLibraryState.model_validate(
        library_current.model_copy(
            update={
                "generated_with": library_generated_with,
                "my_publications_profile": profile,
                "my_publications_dashboard": dashboard,
                "my_publications_citing": citing,
            }
        ).model_dump(mode="json")
    )
    library_output.write_text(
        json.dumps(library_state.model_dump(mode="json"), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return state, library_state


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "demo" / "extended-state-v1.json")
    parser.add_argument("--library-state", type=Path, default=ROOT / "demo" / "library-state-v1.json")
    parser.add_argument("--confirm-public-demo-source", action="store_true")
    parser.add_argument("--confirm-metadata-egress", action="store_true")
    args = parser.parse_args()
    if not args.confirm_public_demo_source or not args.confirm_metadata_egress:
        parser.error("both --confirm-public-demo-source and --confirm-metadata-egress are required")
    state, library_state = capture(args.output, args.library_state)
    dashboard = library_state.my_publications_dashboard
    print(
        "saved public My Publications snapshots: "
        f"citation-years={len(dashboard.counts_by_year)}; "
        f"citation-gaps={len(state.discover.citation_gaps.candidates)}; "
        f"emerging-topics={len(state.discover.emerging_topics.topics)}; "
        f"citing-authors={len(state.discover.citing_authors.authors)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
