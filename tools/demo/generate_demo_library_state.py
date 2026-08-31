"""Generate the public demo's saved axes, tags, queue, and My Publications fixture.

The only input database permitted by policy is a deliberately curated public-demo database. Automatic
axis scores use Callosum's production embedding model; suggested tags use its production local c-TF-IDF
implementation. The checked-in result is immutable input to the separate snapshot exporter.
"""

# ruff: noqa: E402 -- direct script execution needs the repository root on sys.path before app imports.

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

from sqlalchemy import create_engine, insert

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.backend.api.routers.axes_models import AxisResponse, ClusterNodeResponse, ClusterPaperResponse
from app.backend.api.routers.my_publications import (
    CitingResponse,
    DashboardMetrics,
    DashboardResponse,
    OpenAlexExtra,
    PaperCitation,
    ProfileResponse,
    YearCount,
    YearImpact,
)
from app.backend.api.routers.paper_models import PaperTagRef
from app.backend.api.routers.reading_queue import ReadingQueueItem
from app.backend.api.routers.tags import SuggestedTagsResponse, TagSummary
from app.backend.clustering.tag_suggestion import suggest_tags_for_paper
from app.backend.demo_library_state import DemoLibraryState
from app.backend.embeddings.models import SentenceTransformerEmbeddingModel
from app.backend.embeddings.pipeline import paper_embedding_text
from app.backend.persistence.schema import metadata, papers
from tools.demo.curated_library import CORPUS, CORPUS_GROWN_ON, CURATED_ON, curated_abstract

AUTOMATED_AXIS_ID = 9001
MY_PUBLICATIONS_AXIS_ID = 9002
AXIS_DESCRIPTION = (
    "facial difference facial anomalies anomalous-is-bad bias beauty-is-good good-is-beautiful bad-is-ugly "
    "stigma dehumanization humanization warmth competence morality attractiveness social perception gaze behavior"
)
PUBLIC_CITATIONS = {
    42: (31, "W4220933859"),
    67: (43, "W3127453023"),
    89: (0, "W7164336181"),
    90: (20, "W4281398376"),
}
MY_PUBLICATIONS_PAPER_IDS = (42, 67, 89, 90)
RESEARCH_SUMMARY = (
    "My work examines how facial appearance shapes social and moral judgment. Across these four publications, "
    "we test complementary directions of that relationship: how visible facial anomalies can elicit an "
    "‘anomalous-is-bad’ stereotype, whether that stereotype is culturally universal or learned, whether it can "
    "be reduced through exposure-based storytelling, and how information about moral character changes "
    "perceived facial attractiveness. Together, they connect behavioral and neurocognitive evidence to "
    "questions about stigma, person perception, morality, and aesthetic judgment."
)


def _source_rows(source_db: Path) -> dict[int, dict]:
    uri = f"file:{source_db.resolve().as_posix()}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    con.row_factory = sqlite3.Row
    try:
        rows = {}
        for paper_id, item in CORPUS.items():
            source = con.execute(
                "SELECT first_author_family_name FROM papers WHERE id = ?",
                (paper_id,),
            ).fetchone()
            if source is None:
                raise ValueError(f"curated paper {paper_id} is missing")
            rows[paper_id] = {
                "id": paper_id,
                "title": item["title"],
                "abstract": curated_abstract(con, paper_id) or item.get("abstract"),
                "venue": item["venue"],
                "year": item["year"],
                "first_author_family_name": source["first_author_family_name"],
            }
        return rows
    finally:
        con.close()


def _suggested_tags(rows: dict[int, dict]) -> dict[str, SuggestedTagsResponse]:
    engine = create_engine("sqlite://")
    metadata.create_all(engine)
    with engine.begin() as conn:
        for row in rows.values():
            conn.execute(
                insert(papers).values(
                    id=row["id"],
                    title=row["title"],
                    abstract=row["abstract"],
                    csl_json={},
                    processing_tier="fully-chunked",
                )
            )
    result = {}
    with engine.connect() as conn:
        for paper_id, item in CORPUS.items():
            result[str(paper_id)] = SuggestedTagsResponse(
                suggestions=suggest_tags_for_paper(
                    conn,
                    paper_id,
                    existing_tag_names=item["automatic_topics"],
                )
            )
    engine.dispose()
    return result


def _automatic_tags() -> tuple[list[TagSummary], dict[str, list[PaperTagRef]]]:
    counts = Counter(topic for item in CORPUS.values() for topic in item["automatic_topics"])
    ids = {name: 1001 + index for index, name in enumerate(sorted(counts))}
    summaries = [
        TagSummary(id=ids[name], name=name, paper_count=count, source="keyword:openalex")
        for name, count in sorted(counts.items())
    ]
    refs = {
        str(paper_id): [
            PaperTagRef(id=ids[name], name=name, source="keyword:openalex", locked=False)
            for name in item["automatic_topics"]
        ]
        for paper_id, item in CORPUS.items()
    }
    return summaries, refs


def _axis_state(rows: dict[int, dict], model) -> tuple[list[AxisResponse], dict[str, list[ClusterNodeResponse]]]:
    ordered_ids = sorted(rows)
    texts = [AXIS_DESCRIPTION] + [paper_embedding_text(rows[paper_id]) for paper_id in ordered_ids]
    vectors = model.encode_texts(texts)
    scores = {
        paper_id: round(sum(a * b for a, b in zip(vectors[0], vector, strict=True)), 2)
        for paper_id, vector in zip(ordered_ids, vectors[1:], strict=True)
    }
    axes = [
        AxisResponse(
            id=AUTOMATED_AXIS_ID,
            label="Anomalous-is-bad bias",
            description=AXIS_DESCRIPTION,
            scored=True,
            stale=False,
            assignment_count=len(ordered_ids),
            created_at=f"{CURATED_ON}T00:00:00Z",
            scoring_gain=0.35,
            kind="standard",
        ),
        AxisResponse(
            id=MY_PUBLICATIONS_AXIS_ID,
            label="My Publications",
            description="Clifford I. Workman's publications in the curated demo library.",
            assignment_count=len(MY_PUBLICATIONS_PAPER_IDS),
            created_at=f"{CURATED_ON}T00:00:00Z",
            kind="my_publications",
        ),
    ]
    automated_papers = [
        ClusterPaperResponse(
            id=paper_id,
            title=CORPUS[paper_id]["title"],
            confidence=scores[paper_id],
            status="assigned" if scores[paper_id] >= 0.35 else "uncertain",
        )
        for paper_id in ordered_ids
    ]
    if any(paper.status != "assigned" for paper in automated_papers):
        raise ValueError("the generated demo axis no longer comprises every curated paper; review its vocabulary")
    my_papers = [
        ClusterPaperResponse(
            id=paper_id,
            title=CORPUS[paper_id]["title"],
            status="manual",
            manual=True,
            domain="Facial difference and social perception",
        )
        for paper_id in MY_PUBLICATIONS_PAPER_IDS
    ]
    clusters = {
        str(AUTOMATED_AXIS_ID): [
            ClusterNodeResponse(
                id=9101,
                axis_id=AUTOMATED_AXIS_ID,
                label="Anomalous-is-bad bias",
                description="Automatically scored against the complete curated demo library.",
                papers=automated_papers,
            )
        ],
        str(MY_PUBLICATIONS_AXIS_ID): [
            ClusterNodeResponse(
                id=9102,
                axis_id=MY_PUBLICATIONS_AXIS_ID,
                label="My Publications",
                description="Confirmed author matches within this curated demo corpus.",
                papers=my_papers,
            )
        ],
    }
    return axes, clusters


def generate_state(source_db: Path, output: Path, *, model=None) -> DemoLibraryState:
    rows = _source_rows(source_db)
    model = model or SentenceTransformerEmbeddingModel(local_files_only=True)
    axes, axis_clusters = _axis_state(rows, model)
    tags, paper_tags = _automatic_tags()
    state = DemoLibraryState(
        generated_with={
            "axis": f"cosine scoring with {model.name} ({model.version})",
            "automatic_tags": (
                "OpenAlex topics retrieved for the three original DOI records on 2026-08-11; two more on "
                f"{CORPUS_GROWN_ON}"
            ),
            "suggested_tags": "Callosum local c-TF-IDF",
        },
        axes=axes,
        axis_clusters=axis_clusters,
        tags=tags,
        paper_tags=paper_tags,
        tag_colors=["blue", "green", "purple", "orange", "red", "pink", "teal", "yellow"],
        suggested_tags=_suggested_tags(rows),
        reading_queue=[
            ReadingQueueItem(
                id=paper_id,
                title=CORPUS[paper_id]["title"],
                authors=CORPUS[paper_id]["authors"],
                year=CORPUS[paper_id]["year"],
                priority={67: "high", 88: "normal", 42: None, 89: None, 90: None}[paper_id],
            )
            for paper_id in (67, 88, 42, 89, 90)
        ],
        my_publications_profile=ProfileResponse(
            display_name="Clifford I. Workman",
            name_variants=["Cliff Workman", "C. I. Workman"],
            orcid="0000-0002-2206-0325",
            has_author_id=True,
        ),
        # NOTE: this whole my_publications_dashboard is a transient placeholder -- the documented pipeline
        # (demo/README.md) always runs tools/demo/capture_demo_prospection.py next, which fully replaces every
        # field here (including a real, non-fabricated `domains`) with live-endpoint output. It survives only if
        # someone reads library-state-v1.json before that later step runs.
        my_publications_dashboard=DashboardResponse(
            status="ok",
            name="Clifford I. Workman — demo corpus",
            as_of=f"{CURATED_ON}T00:00:00Z",
            metrics=DashboardMetrics(
                works_count=len(MY_PUBLICATIONS_PAPER_IDS),
                cited_by_count=sum(count for count, _work_id in PUBLIC_CITATIONS.values()),
                h_index=sum(
                    count >= rank
                    for rank, count in enumerate(
                        sorted((c for c, _w in PUBLIC_CITATIONS.values()), reverse=True), start=1
                    )
                ),
                i10_index=sum(count >= 10 for count, _work_id in PUBLIC_CITATIONS.values()),
            ),
            pubs_by_year=sorted(
                (YearCount(year=CORPUS[pid]["year"], count=1) for pid in MY_PUBLICATIONS_PAPER_IDS),
                key=lambda item: item.year,
            ),
            counts_by_year=sorted(
                (
                    YearImpact(year=CORPUS[pid]["year"], works_count=1, cited_by_count=PUBLIC_CITATIONS[pid][0])
                    for pid in MY_PUBLICATIONS_PAPER_IDS
                ),
                key=lambda item: item.year,
            ),
            indexed_works=len(MY_PUBLICATIONS_PAPER_IDS),
            in_library=len(MY_PUBLICATIONS_PAPER_IDS),
            gap=0,
            research_summary=RESEARCH_SUMMARY,
            # Never fabricated -- left empty here; capture_demo_prospection.py fills this from the real
            # /my-publications/domains job's own output before the artifact is ever exported.
            domains=[],
            missing_works=[],
            dismissed_works=[],
            openalex_extra=OpenAlexExtra(
                two_year_mean_citedness=3.1,
                affiliation="University of Delaware",
                openalex_author_id="A5034020375",
            ),
            paper_citations={
                str(paper_id): PaperCitation(cited_by_count=count, openalex_work_id=work_id)
                for paper_id, (count, work_id) in PUBLIC_CITATIONS.items()
            },
        ),
        my_publications_citing={work_id: CitingResponse() for _count, work_id in PUBLIC_CITATIONS.values()},
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(state.model_dump(mode="json", exclude_none=True), indent=2, sort_keys=True, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    return state


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-db", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "demo" / "library-state-v1.json")
    parser.add_argument("--confirm-public-demo-source", action="store_true")
    parser.add_argument("--allow-model-download", action="store_true")
    args = parser.parse_args()
    if not args.confirm_public_demo_source:
        parser.error("--confirm-public-demo-source is required; never use an ordinary working library")
    model = SentenceTransformerEmbeddingModel(local_files_only=not args.allow_model_download)
    generate_state(args.source_db, args.output, model=model)
    print(f"generated validated demo library state: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
