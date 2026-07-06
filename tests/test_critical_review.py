"""Critical-review supplement (backlog #12) — the single-paper "scrutiny surface" MVP.

Tier 1 is deterministic/local; Tier 2 is egress-gated LLM candidates through the #13 verbatim-quote bar. Tests
inject fakes for the NLI stance scorer / vector store / generator so they stay hermetic + fast (no model loads).
"""

from __future__ import annotations

from sqlalchemy import create_engine

from app.backend.persistence import critical_review_repo as repo
from app.backend.persistence import schema
from app.backend.persistence.repository import create_paper


def test_candidate_store_roundtrip() -> None:
    eng = create_engine("sqlite://")
    schema.metadata.create_all(eng)
    with eng.begin() as c:
        pid = create_paper(c, title="P", csl_json={"title": "P"})
        ids = repo.insert_candidates(
            c,
            pid,
            [
                {
                    "concern": "overstated",
                    "anchor_quote": "we prove causation",
                    "page": 3,
                    "stance": "contrast",
                    "confidence": 0.8,
                    "signature": "sig1",
                }
            ],
        )
        assert len(ids) == 1
        rows = repo.list_candidates(c, pid, statuses=["pending"])
        assert len(rows) == 1
        assert rows[0]["concern"] == "overstated" and rows[0]["status"] == "pending"
        assert rows[0]["anchor_quote"] == "we prove causation" and rows[0]["confidence"] == 0.8
        assert repo.set_status(c, ids[0], "rejected") is True
        assert repo.set_status(c, 99999, "rejected") is False  # unknown id
        assert repo.rejected_signatures(c, pid) == {"sig1"}
        assert repo.list_candidates(c, pid, statuses=["pending"]) == []  # now rejected, not pending
