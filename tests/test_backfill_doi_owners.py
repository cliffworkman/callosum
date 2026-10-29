"""T7: a merged/soft-deleted duplicate never captures a live paper's cached reference metadata.

Regression for DOI 10.5498/wjp.v11.i6.201 (Artin et al. 2021): live paper 171 lost its 120 Crossref references --
and therefore its whole anchored reference region -- to merged duplicate 202, because the DOI map was built over
every row and the last duplicate won.
"""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import text

from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper
from app.backend.persistence.schema import papers
from tools.backfill_chunk_structure import doi_owners, load_reference_metadata

DOI = "10.5498/wjp.v11.i6.201"


def _paper(conn, title: str, doi: str, *, merged_into: int | None = None, deleted: bool = False) -> int:
    paper_id = create_paper(conn, title=title, csl_json={"title": title})
    conn.execute(
        papers.update()
        .where(papers.c.id == paper_id)
        .values(doi=doi, merged_into=merged_into, deleted_at=datetime(2026, 7, 10) if deleted else None)
    )
    return paper_id


def _cache(conn, doi: str, n_refs: int) -> None:
    payload = {
        "message": {"reference": [{"article-title": f"Reference {i}", "DOI": f"10.1/{i}"} for i in range(n_refs)]}
    }
    conn.execute(
        text(
            "INSERT INTO external_api_cache (provider, cache_key, response_json, fetched_at) "
            "VALUES ('crossref', :k, :v, '2026-09-07')"
        ),
        {"k": doi, "v": json.dumps(payload)},
    )


def test_merged_duplicates_resolve_to_the_live_canonical_paper(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        live = _paper(conn, "Artin 2021", DOI)
        for _ in range(2):  # inserted AFTER the live paper, exactly the order that made the old map pick them
            _paper(conn, "Artin 2021 (duplicate)", DOI.upper(), merged_into=live, deleted=True)
        _cache(conn, DOI, 120)
        diagnostics: dict = {}
        assert doi_owners(conn, diagnostics)[DOI] == (live,)
        refs = load_reference_metadata(conn)
        assert len(refs[live]) == 120
        assert diagnostics["ambiguous_dois"] == {}
    engine.dispose()


def test_doi_held_only_by_a_merged_row_resolves_through_merged_into(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        survivor = _paper(conn, "Survivor without DOI", "")
        _paper(conn, "Merged preprint", "10.31234/osf.io/abcde", merged_into=survivor, deleted=True)
        diagnostics: dict = {}
        assert doi_owners(conn, diagnostics)["10.31234/osf.io/abcde"] == (survivor,)
        assert diagnostics["resolved_through_merge"] == ["10.31234/osf.io/abcde"]
    engine.dispose()


def test_two_live_papers_sharing_a_doi_both_receive_it_and_are_reported(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        first = _paper(conn, "Copy A", "10.1371/journal.pbio.3003277")
        second = _paper(conn, "Copy B", "10.1371/journal.pbio.3003277")
        _cache(conn, "10.1371/journal.pbio.3003277", 3)
        diagnostics: dict = {}
        refs = load_reference_metadata(conn, diagnostics)
        assert len(refs[first]) == len(refs[second]) == 3  # neither silently wins, neither is starved
        assert diagnostics["ambiguous_dois"] == {"10.1371/journal.pbio.3003277": sorted([first, second])}
    engine.dispose()


def test_deleted_paper_without_live_survivor_owns_nothing(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        _paper(conn, "Trashed", "10.9/trashed", deleted=True)
        _cache(conn, "10.9/trashed", 5)
        assert "10.9/trashed" not in doi_owners(conn)
        assert load_reference_metadata(conn) == {}
    engine.dispose()
