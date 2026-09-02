from __future__ import annotations

from fastapi.testclient import TestClient

from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_attachment, create_chunk, create_paper
from app.backend.summarization.generators import CandidateCitation, CandidateSummarySentence, SourceChunk
from app.backend.summarization.pipeline import _round_robin_by_paper, _select_ranked_with_paper_coverage
from tests.api_helpers import _summarization_app

# Multi-paper "summarize selected" coverage: a papers-scope summary with no query must spread its top_k
# budget across the selected papers, not fill it from the lowest-id paper and ignore the rest.


def _sc(chunk_id: int, paper_id: int) -> SourceChunk:
    return SourceChunk(
        chunk_id=chunk_id,
        paper_id=paper_id,
        attachment_id=1,
        text=f"c{chunk_id}",
        page_start=1,
        page_end=1,
        chunk_version="v",
    )


def test_round_robin_interleaves_papers() -> None:
    rows = [_sc(1, 10), _sc(2, 10), _sc(3, 10), _sc(4, 20), _sc(5, 20)]  # 3 from paper 10, 2 from paper 20
    out = _round_robin_by_paper(rows)
    assert [c.chunk_id for c in out] == [1, 4, 2, 5, 3]  # p10.c1, p20.c1, p10.c2, p20.c2, p10.c3
    assert {c.paper_id for c in out[:2]} == {10, 20}  # a top_k=2 slice now spans BOTH papers


def test_round_robin_single_paper_is_identity() -> None:
    rows = [_sc(1, 10), _sc(2, 10), _sc(3, 10)]
    assert _round_robin_by_paper(rows) is rows  # ≤1 paper → returned unchanged
    assert _round_robin_by_paper([]) == []


def test_ranked_focus_reserves_each_selected_paper_best_chunk() -> None:
    ranked = [_sc(1, 10), _sc(2, 10), _sc(3, 10), _sc(4, 20), _sc(5, 30), _sc(6, 20)]

    out = _select_ranked_with_paper_coverage(ranked, top_k=4)

    assert [chunk.chunk_id for chunk in out] == [1, 2, 4, 5]
    assert {chunk.paper_id for chunk in out} == {10, 20, 30}


def test_ranked_focus_keeps_global_order_when_budget_cannot_cover_every_paper() -> None:
    ranked = [_sc(1, 10), _sc(2, 20), _sc(3, 30)]

    assert [chunk.chunk_id for chunk in _select_ranked_with_paper_coverage(ranked, top_k=2)] == [1, 2]


def _seed_two_papers_two_chunks(db_url: str) -> dict[str, int]:
    """Paper A (chunks a1,a2) then paper B (chunks b1,b2) — chunk ids ascend A1,A2,B1,B2, so a naive
    rows[:2] would take A1,A2 (paper A only). Round-robin must instead span both papers."""
    engine = make_engine(db_url)
    out: dict[str, int] = {}
    with engine.begin() as conn:
        for key in ("a", "b"):
            paper_id = create_paper(
                conn,
                title=f"Paper {key.upper()}",
                processing_tier="fully-chunked",
                csl_json={"type": "article-journal", "title": f"Paper {key.upper()}"},
            )
            attachment_id = create_attachment(
                conn,
                paper_id=paper_id,
                storage_mode="linked",
                availability="available",
                content_type="application/pdf",
                checksum=f"chk-{key}",
                import_source="test",
                attachment_type="pdf",
                role="primary",
            )
            out[f"p{key}"] = paper_id
            for n in (1, 2):
                chunk_id = create_chunk(
                    conn,
                    paper_id=paper_id,
                    attachment_id=attachment_id,
                    text=f"Paper {key.upper()} chunk {n} discusses cortex.",
                    page_start=n,
                    page_end=n,
                    bbox_coordinate_system="pdf-points-top-left",
                    extraction_tool="fixture",
                    extraction_version="1",
                    chunking_strategy="paragraph",
                    chunk_version=f"{key}{n}",
                    source_attachment_checksum=f"chk-{key}",
                    section="methods" if key == "a" and n == 1 else None,
                    bbox_json=[{"page": n, "x0": 1, "y0": 2, "x1": 3, "y1": 4}],
                )
                out[f"{key}{n}"] = chunk_id
    engine.dispose()
    return out


class CapturingSummaryGenerator:
    name = "capturing-summary-generator"

    def __init__(self, sentences):
        self.sentences = sentences
        self.captured = None

    def generate(self, *, source_chunks, scope_ref, engine=None):
        self.captured = list(source_chunks)
        return list(self.sentences)


def test_multi_paper_summary_covers_all_selected_papers(temp_db_url: str) -> None:
    seed = _seed_two_papers_two_chunks(temp_db_url)
    gen = CapturingSummaryGenerator(
        [
            CandidateSummarySentence(
                text="Cortex is discussed across the selection.",
                citations=[CandidateCitation(chunk_id=seed["a1"], quote="Paper A chunk 1 discusses cortex.")],
            )
        ]
    )
    client = TestClient(_summarization_app(temp_db_url, generator=gen))

    started = client.post(
        "/summarize", json={"scope_type": "papers", "paper_ids": [seed["pa"], seed["pb"]], "top_k": 2}
    )
    result = client.get(f"/summarize/{started.json()['job_id']}").json()

    assert started.status_code == 202
    assert result["status"] == "done"
    assert result["sentences"][0]["citations"][0]["section"] == "methods"
    assert gen.captured is not None
    assert {c.paper_id for c in gen.captured} == {seed["pa"], seed["pb"]}  # round-robin spanned both papers
    assert len(gen.captured) == 2  # within the top_k=2 budget


def _seed_two_papers_frontmatter_then_content(db_url: str) -> dict[str, int]:
    """Each paper's FIRST chunk (lowest id) is front matter, its SECOND is body content. A naive selection that
    takes the first chunk of each paper (the old _round_robin_by_paper[:top_k]) would feed the LLM mastheads;
    the fix must prefer the content chunks."""
    engine = make_engine(db_url)
    fm = {
        "a": "Original Manuscript",
        "b": "Social Psychological and Personality Science 1-10 © The Author(s) 2021 DOI: 10.1177/19485506211031722",
    }
    body = {
        "a": "Anomalous faces were rated more negatively in warmth and competence than typical faces.",
        "b": "Participants allocated more money to partners whose faces appeared more typical.",
    }
    out: dict[str, int] = {}
    with engine.begin() as conn:
        for key in ("a", "b"):
            paper_id = create_paper(
                conn,
                title=f"Paper {key.upper()}",
                processing_tier="fully-chunked",
                csl_json={"type": "article-journal", "title": f"Paper {key.upper()}"},
            )
            attachment_id = create_attachment(
                conn,
                paper_id=paper_id,
                storage_mode="linked",
                availability="available",
                content_type="application/pdf",
                checksum=f"chk-{key}",
                import_source="test",
                attachment_type="pdf",
                role="primary",
            )
            out[f"p{key}"] = paper_id
            for n, text in ((1, fm[key]), (2, body[key])):
                chunk_id = create_chunk(
                    conn,
                    paper_id=paper_id,
                    attachment_id=attachment_id,
                    text=text,
                    page_start=n,
                    page_end=n,
                    bbox_coordinate_system="pdf-points-top-left",
                    extraction_tool="fixture",
                    extraction_version="1",
                    chunking_strategy="paragraph",
                    chunk_version=f"{key}{n}",
                    source_attachment_checksum=f"chk-{key}",
                    bbox_json=[{"page": n, "x0": 1, "y0": 2, "x1": 3, "y1": 4}],
                )
                out[f"{key}{n}"] = chunk_id
    engine.dispose()
    return out


def test_no_query_papers_scope_prefers_content_over_front_matter(temp_db_url: str) -> None:
    seed = _seed_two_papers_frontmatter_then_content(temp_db_url)
    gen = CapturingSummaryGenerator(
        [
            CandidateSummarySentence(
                text="Typicality shapes social judgments.",
                citations=[CandidateCitation(chunk_id=seed["a2"], quote="")],
            )
        ]
    )
    client = TestClient(_summarization_app(temp_db_url, generator=gen))

    started = client.post(
        "/summarize", json={"scope_type": "papers", "paper_ids": [seed["pa"], seed["pb"]], "top_k": 2}
    )
    result = client.get(f"/summarize/{started.json()['job_id']}").json()

    assert started.status_code == 202
    assert result["status"] == "done"
    assert gen.captured is not None
    captured_ids = {c.chunk_id for c in gen.captured}
    assert captured_ids == {seed["a2"], seed["b2"]}  # the two CONTENT chunks, not the front-matter first-chunks
    assert seed["a1"] not in captured_ids and seed["b1"] not in captured_ids
    assert {c.paper_id for c in gen.captured} == {seed["pa"], seed["pb"]}  # still spans both papers


def test_focus_query_ranks_within_the_selection_only(temp_db_url: str) -> None:
    # inc 111: a papers-scope summary with a focus query routes through query-RANKING (not round-robin) and must
    # stay restricted to the SELECTED papers — a focus query never pulls in chunks from unselected papers.
    seed = _seed_two_papers_two_chunks(temp_db_url)
    gen = CapturingSummaryGenerator(
        [
            CandidateSummarySentence(
                text="Cortex is discussed.",
                citations=[CandidateCitation(chunk_id=seed["a1"], quote="Paper A chunk 1 discusses cortex.")],
            )
        ]
    )
    client = TestClient(_summarization_app(temp_db_url, generator=gen))

    started = client.post(
        "/summarize",
        json={"scope_type": "papers", "paper_ids": [seed["pa"]], "query": "cortex", "top_k": 5},
    )
    result = client.get(f"/summarize/{started.json()['job_id']}").json()

    assert started.status_code == 202
    assert result["status"] == "done"
    assert gen.captured  # the focus query returned chunks
    assert {c.paper_id for c in gen.captured} == {seed["pa"]}  # ranked WITHIN paper A — no paper-B leakage
