"""Set (multi-paper) critical review — backlog #12. Engine + Tier-2 + endpoint tests, hermetic (injected fakes)."""

from __future__ import annotations

from app.backend.persistence import critical_review_repo as repo
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper


def test_related_paper_ids_roundtrips(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="A", csl_json={"title": "A"})
        [cid] = repo.insert_candidates(
            conn,
            pid,
            [
                {
                    "concern": "small sample",
                    "anchor_quote": "n = 12",
                    "signature": "sig1",
                    "stance": "contrast",
                    "confidence": 0.7,
                    "related_paper_ids": [pid + 1, pid + 2],
                }
            ],
        )
        rows = repo.list_candidates(conn, pid)
    engine.dispose()
    assert cid > 0
    assert rows[0]["related_paper_ids_json"] == [pid + 1, pid + 2]
