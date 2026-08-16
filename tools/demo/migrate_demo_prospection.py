"""Carry forward public My Publications graph results after a demo-corpus replacement.

This is used only when a fresh provider refresh fails closed. It reads a previously
deployed public snapshot, removes every work/evidence edge tied to the retired paper,
recomputes displayed counts, narrows coverage to the unchanged Workman 2021 source,
and validates the result through the current strict demo models. It never relabels old
graph evidence as evidence for the replacement paper.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.backend.api.routers.my_publication_citing_authors import CitingAuthorListResponse  # noqa: E402
from app.backend.api.routers.my_publication_gaps import CitationGapListResponse  # noqa: E402
from app.backend.api.routers.my_publication_topics import EmergingTopicListResponse  # noqa: E402
from app.backend.api.routers.my_publications import DashboardResponse  # noqa: E402
from app.backend.demo_extended_state import DemoExtendedState, DemoFeedState  # noqa: E402
from app.backend.demo_library_state import DemoLibraryState  # noqa: E402

RETIRED_PAPER_ID = 42
RETIRED_DOI = "10.1111/bjop.12719"
UNCHANGED_PAPER_ID = 67


def _citations(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in values if int(item.get("paper_id") or 0) != RETIRED_PAPER_ID]


def _coverage(payload: dict[str, Any], *, note: str) -> dict[str, Any]:
    coverage = dict(payload)
    for key in ("checked", "library_total", "total", "with_doi"):
        if key in coverage:
            coverage[key] = 1
    coverage["note"] = f"{coverage.get('note', '').strip()} {note}".strip()
    return coverage


def _citation_gaps(payload: dict[str, Any]) -> dict[str, Any]:
    candidates = []
    for candidate in payload["candidates"]:
        evidence = []
        for item in candidate["evidence"]:
            kept = _citations(item["source_papers"])
            if kept:
                evidence.append(dict(item) | {"source_papers": kept})
        if evidence:
            source_ids = {int(source["paper_id"]) for item in evidence for source in item["source_papers"]}
            candidates.append(
                dict(candidate)
                | {
                    "evidence": evidence,
                    "shared_reference_count": len(evidence),
                    "source_publication_count": len(source_ids),
                }
            )
    coverage = _coverage(
        payload["coverage"],
        note="Saved fallback coverage is limited to the unchanged Workman et al. (2021) publication; the replacement DOI was unavailable from the provider during refresh.",
    )
    coverage["shared_anchor_count"] = len(
        {item["reference_openalex_work_id"] for candidate in candidates for item in candidate["evidence"]}
    )
    return dict(payload) | {"candidates": candidates, "coverage": coverage}


def _works(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for work in values:
        if str(work.get("doi") or "").casefold() == RETIRED_DOI:
            continue
        cited = _citations(work["cited_publications"])
        if cited:
            output.append(dict(work) | {"cited_publications": cited})
    return output


def _emerging_topics(payload: dict[str, Any]) -> dict[str, Any]:
    topics = []
    for topic in payload["topics"]:
        previous = _works(topic["previous_works"])
        recent = _works(topic["recent_works"])
        increase = len(recent) - len(previous)
        if (previous or recent) and increase > 0:
            topics.append(
                dict(topic)
                | {
                    "previous_works": previous,
                    "recent_works": recent,
                    "previous_count": len(previous),
                    "recent_count": len(recent),
                    "increase": increase,
                }
            )
    coverage = _coverage(
        payload["coverage"],
        note="Saved fallback coverage is limited to the unchanged Workman et al. (2021) publication; no edge is attributed to the replacement paper.",
    )
    coverage["previous_work_count"] = len(
        {work["openalex_work_id"] for topic in topics for work in topic["previous_works"]}
    )
    coverage["recent_work_count"] = len(
        {work["openalex_work_id"] for topic in topics for work in topic["recent_works"]}
    )
    return dict(payload) | {"topics": topics, "coverage": coverage}


def _citing_authors(payload: dict[str, Any]) -> dict[str, Any]:
    authors = []
    for author in payload["authors"]:
        works = _works(author["citing_works"])
        distinct_titles = {re.sub(r"\W+", " ", str(work.get("title") or "").casefold()).strip() for work in works}
        publications = {int(item["paper_id"]) for work in works for item in work["cited_publications"]}
        if works and len(publications) >= 2 and len(distinct_titles) >= 2:
            authors.append(
                dict(author)
                | {
                    "citing_works": works,
                    "citing_work_count": len(works),
                    "cited_publication_count": len(publications),
                    "latest_year": max(int(work["year"]) for work in works),
                }
            )
    coverage = _coverage(
        payload["coverage"],
        note="Saved fallback coverage is limited to authors citing the unchanged Workman et al. (2021) publication; no edge is attributed to the replacement paper.",
    )
    coverage["citing_work_count"] = len(
        {work["openalex_work_id"] for author in authors for work in author["citing_works"]}
    )
    coverage["coauthor_checked_publication_count"] = 1
    return dict(payload) | {"authors": authors, "coverage": coverage}


def migrate(previous_snapshot: Path, output: Path, library_output: Path) -> tuple[DemoExtendedState, DemoLibraryState]:
    previous_api = json.loads(previous_snapshot.read_text(encoding="utf-8"))["api"]
    previous = previous_api["extended"]["discover"]
    current = DemoExtendedState.model_validate_json(output.read_bytes())
    discover = current.discover.model_copy(
        update={
            "citation_gaps": CitationGapListResponse.model_validate(_citation_gaps(previous["citation_gaps"])),
            "emerging_topics": EmergingTopicListResponse.model_validate(_emerging_topics(previous["emerging_topics"])),
            "citing_authors": CitingAuthorListResponse.model_validate(_citing_authors(previous["citing_authors"])),
        }
    )
    generated_with = dict(current.generated_with)
    generated_with["my_publications_prospection"] = (
        "filtered migration from prior deployed public snapshot after fresh OpenAlex refresh returned empty; "
        f"retired paper {RETIRED_PAPER_ID} removed; coverage limited to paper {UNCHANGED_PAPER_ID}"
    )
    state = DemoExtendedState.model_validate(
        current.model_copy(
            update={
                "discover": discover,
                "feed": DemoFeedState.model_validate(previous_api["extended"]["feed"]),
                "generated_with": generated_with,
            }
        ).model_dump(mode="json")
    )
    output.write_text(
        json.dumps(state.model_dump(mode="json"), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    library = DemoLibraryState.model_validate_json(library_output.read_bytes())
    prior_dashboard = previous_api["my_publications_dashboard"]
    current_dashboard = library.my_publications_dashboard.model_dump(mode="json")
    for key in ("counts_by_year", "domains", "missing_works", "dismissed_works", "openalex_extra"):
        current_dashboard[key] = prior_dashboard[key]
    current_dashboard["paper_citations"] = library.my_publications_dashboard.paper_citations
    current_dashboard["pubs_by_year"] = library.my_publications_dashboard.pubs_by_year
    current_dashboard["in_library"] = 2
    current_dashboard["gap"] = max(0, int(current_dashboard.get("indexed_works") or 2) - 2)
    library_generated = dict(library.generated_with)
    library_generated["my_publications_dashboard"] = (
        "prior deployed public author refresh retained; in-library paper map updated for replacement corpus"
    )
    library = DemoLibraryState.model_validate(
        library.model_copy(
            update={
                "my_publications_dashboard": DashboardResponse.model_validate(current_dashboard),
                "generated_with": library_generated,
            }
        ).model_dump(mode="json")
    )
    library_output.write_text(
        json.dumps(library.model_dump(mode="json"), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return state, library


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--previous-snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "demo" / "extended-state-v1.json")
    parser.add_argument("--library-state", type=Path, default=ROOT / "demo" / "library-state-v1.json")
    parser.add_argument("--confirm-prior-public-snapshot", action="store_true")
    args = parser.parse_args()
    if not args.confirm_prior_public_snapshot:
        parser.error("--confirm-prior-public-snapshot is required")
    state, _library = migrate(args.previous_snapshot, args.output, args.library_state)
    print(
        "migrated filtered public prospection: "
        f"gaps={len(state.discover.citation_gaps.candidates)}, "
        f"topics={len(state.discover.emerging_topics.topics)}, "
        f"authors={len(state.discover.citing_authors.authors)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
