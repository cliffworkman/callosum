"""The short-write `run_write` sweep invariant (inc 281): every short SELECT-then-write API handler wraps its
read+write unit in ``run_write`` (transaction-level retry on a transient SQLite writer lock) rather than taking a
raw ``get_connection`` connection and calling ``conn.commit()``.

This guard fails when a NEW raw ``conn.commit()`` appears in a router — a short write that skipped ``run_write`` and
can still 500 on a snapshot-upgrade BUSY. The allowlist below is the set of handlers that legitimately keep their
own transaction: **heavy ops** (retrying would re-run an expensive extraction / NLI verification), **egress ops**
(retrying would re-fire an LLM call), and **I/O-mixed ops** where a retry could double-fire an external fetch or a
secret write. Add to the allowlist only for one of those genuine reasons — never to skip converting a plain short
write.
"""

from __future__ import annotations

from app.backend.api.startup import PROJECT_ROOT

# file name -> number of intentional raw conn.commit() calls that stay OUTSIDE run_write, with why.
ALLOWED_RAW_COMMITS = {
    # heavy / non-transactional — a lock-retry would re-run the expensive work (or re-touch the vector store).
    "papers.py": 1,  # reprocess-pdf (re-extract + re-embed); purge commits moved to paper_purge.py (file staging)
    "summaries.py": 1,  # summary reverify — local retrieval + NLI + quote-location over the library
    "critical_review.py": 1,  # candidate generate — NLI verification of AI drafts (egress-gated)
    "workbench.py": 1,  # propose_row — the LLM assisted-extraction proposal (egress)
    "analytic_flexibility.py": 1,  # propose_analytic_flexibility — the LLM candidate-proposal call (egress)
    # I/O-mixed — a retry could double-fire an external fetch or a secret write.
    "paper_enrich.py": 2,  # re-resolve + fill-metadata FORCE a fresh Crossref/OpenAlex fetch (double-egress on retry)
    "agent.py": 2,  # agent_save_reference resolves a DOI via Crossref, caching through the request connection
    "sync.py": 1,  # sync setup round-trips the sync server before the commit
}


def test_no_unaccounted_raw_commit_in_routers():
    routers = PROJECT_ROOT / "app" / "backend" / "api" / "routers"
    offenders = {}
    for py in sorted(routers.glob("*.py")):
        count = py.read_text(encoding="utf-8").count("conn.commit()")
        allowed = ALLOWED_RAW_COMMITS.get(py.name, 0)
        if count != allowed:
            offenders[py.name] = (count, allowed)
    assert not offenders, (
        "Unaccounted raw conn.commit() in routers (short writes must go through run_write, inc 281): "
        + ", ".join(f"{name}: found {c}, allowed {a}" for name, (c, a) in offenders.items())
        + ". Convert the handler to run_write, or (only for a genuine heavy/egress/IO-mixed op) update ALLOWED_RAW_COMMITS."
    )
