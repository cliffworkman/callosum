"""Data access for `open_science_signals` — the deterministic Methods producers' per-paper findings (inc 97).

First (and so far only) producer: **statcheck**. One summary row per (paper, signal_type, source); re-running
the batch `OR REPLACE`s it (idempotent, never duplicates) on the table's UniqueConstraint. The library filter
(`repository.list_papers(signal=…)`) reads these rows. A finding here is a deterministic FACT (no LLM); the
per-test evidence is recomputed/shown live in the Details pane (inc 95) — this row just carries the count + flag.
"""

from __future__ import annotations

import json

from sqlalchemy import Connection, RowMapping, func, insert, select

from app.backend.persistence.schema import open_science_signals

STATCHECK_SIGNAL = "statcheck"
STATCHECK_SOURCE = "statcheck"


def store_statcheck(conn: Connection, paper_id: int, *, checked: int, inconsistent: int, decision_errors: int) -> None:
    """Upsert a paper's statcheck summary. `status='inconsistent'` iff any test flagged (inconsistent OR
    decision-error), else `'consistent'`; the counts live in `evidence_snippet`. OR-REPLACE on the
    `(paper_id, signal_type, source)` unique constraint so a re-run overwrites rather than duplicating."""
    flagged = (inconsistent + decision_errors) > 0
    conn.execute(
        insert(open_science_signals)
        .prefix_with("OR REPLACE")
        .values(
            paper_id=paper_id,
            signal_type=STATCHECK_SIGNAL,
            source=STATCHECK_SOURCE,
            status="inconsistent" if flagged else "consistent",
            evidence_snippet=json.dumps(
                {"checked": checked, "inconsistent": inconsistent, "decision_errors": decision_errors}
            ),
        )
    )


def count_statcheck_flagged(conn: Connection) -> int:
    """How many papers the last batch run flagged (status='inconsistent') — drives the library 'N flagged' chip."""
    total = conn.execute(
        select(func.count())
        .select_from(open_science_signals)
        .where(open_science_signals.c.signal_type == STATCHECK_SIGNAL, open_science_signals.c.status == "inconsistent")
    ).scalar()
    return int(total or 0)


def get_statcheck_summary(conn: Connection, paper_id: int) -> RowMapping | None:
    """The stored statcheck summary row for a paper (or None if it's never been batch-checked)."""
    return (
        conn.execute(
            select(open_science_signals).where(
                open_science_signals.c.paper_id == paper_id,
                open_science_signals.c.signal_type == STATCHECK_SIGNAL,
                open_science_signals.c.source == STATCHECK_SOURCE,
            )
        )
        .mappings()
        .first()
    )
