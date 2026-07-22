"""Data access for `open_science_signals` — the deterministic Methods producers' per-paper findings (inc 97).

First (and so far only) producer: **statcheck**. One summary row per (paper, signal_type, source); re-running
the batch `OR REPLACE`s it (idempotent, never duplicates) on the table's UniqueConstraint. The library filter
(`repository.list_papers(signal=…)`) reads these rows. A finding here is a deterministic FACT (no LLM); the
per-test evidence is recomputed/shown live in the Details pane (inc 95) — this row just carries the count + flag.
"""

from __future__ import annotations

import json

from sqlalchemy import Connection, RowMapping, delete, func, insert, select

from app.backend.persistence.schema import open_science_signals

STATCHECK_SIGNAL = "statcheck"
STATCHECK_SOURCE = "statcheck"

RETRACTION_SIGNAL = "retraction"
RETRACTION_SOURCE = "retraction"

TRANSPARENCY_SIGNAL = "transparency"
# inc 250 status -> the persisted per-disclosure check status (a check RESULT, not a claim about the paper).
_TRANSPARENCY_STATUS = {"present": "detected", "not-found": "not-detected", "not-applicable": "not-applicable"}


def store_transparency_status(conn: Connection, paper_id: int, report) -> None:
    """Upsert a paper's per-disclosure transparency check status (inc 251), ONE `open_science_signals` row per
    disclosure (`signal_type='transparency'`, `source=<disclosure_key>`). `status` ∈ detected / not-detected /
    not-applicable — a check RESULT (the auditor ran and did/didn't find it in the text), NEVER a claim that the
    paper lacks the artifact (silence≠certificate; the A-A no-accusation boundary). The present-disclosure FACT
    (with evidence) lives in `paper_findings`; this row carries the status for the library review-queue filter
    (`repository.SIGNAL_FILTERS['transparency-*']`) + the chip. OR-REPLACE on the unique (paper, signal_type,
    source) → idempotent re-runs. `report` is a `methods.transparency.TransparencyReport`."""
    for check in report.checks:
        conn.execute(
            insert(open_science_signals)
            .prefix_with("OR REPLACE")
            .values(
                paper_id=paper_id,
                signal_type=TRANSPARENCY_SIGNAL,
                source=check.key,
                status=_TRANSPARENCY_STATUS.get(check.status, check.status),
                evidence_snippet=check.evidence if check.status == "present" else None,
            )
        )


def count_transparency_status(
    conn: Connection, disclosure_key: str = "data_availability", status: str = "detected"
) -> int:
    """How many papers have a persisted status for one disclosure. Used by Library chips; a detected count is a
    checkable signal with evidence, while a not-detected count is only a review queue."""
    total = conn.execute(
        select(func.count())
        .select_from(open_science_signals)
        .where(
            open_science_signals.c.signal_type == TRANSPARENCY_SIGNAL,
            open_science_signals.c.source == disclosure_key,
            open_science_signals.c.status == status,
        )
    ).scalar()
    return int(total or 0)


def count_transparency_review(conn: Connection, disclosure_key: str = "data_availability") -> int:
    """How many papers have a `not-detected` status for a disclosure — a REVIEW QUEUE ('the auditor ran and didn't
    surface it — go look'), never 'papers that hide their data'."""
    return count_transparency_status(conn, disclosure_key, "not-detected")


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


def store_retraction_status(
    conn: Connection, paper_id: int, *, status: str, sources: list[str], checked_at: str
) -> None:
    """Upsert a paper's per-paper retraction CHECK status (inc 131). `status` ∈ retracted/correction/concern/none/
    unchecked. This is the *honesty* record (a checked-clean paper gets a positive 'none'; no-DOI → 'unchecked' —
    silence is never 'clean'). The FACT itself (when retracted) lives in `paper_findings`; this row carries the
    status + the library filter (`repository.SIGNAL_FILTERS['retraction-retracted']`). OR-REPLACE on the unique
    (paper_id, signal_type, source) → idempotent re-runs."""
    conn.execute(
        insert(open_science_signals)
        .prefix_with("OR REPLACE")
        .values(
            paper_id=paper_id,
            signal_type=RETRACTION_SIGNAL,
            source=RETRACTION_SOURCE,
            status=status,
            evidence_snippet=json.dumps({"sources": list(sources), "checked_at": checked_at}),
        )
    )


def count_retraction_flagged(conn: Connection) -> int:
    """How many papers a registry records as retracted (status='retracted') — drives the 'N retracted' chip."""
    total = conn.execute(
        select(func.count())
        .select_from(open_science_signals)
        .where(open_science_signals.c.signal_type == RETRACTION_SIGNAL, open_science_signals.c.status == "retracted")
    ).scalar()
    return int(total or 0)


def get_retraction_status(conn: Connection, paper_id: int) -> RowMapping | None:
    """The stored retraction check-status row for a paper (or None if it's never been checked)."""
    return (
        conn.execute(
            select(open_science_signals).where(
                open_science_signals.c.paper_id == paper_id,
                open_science_signals.c.signal_type == RETRACTION_SIGNAL,
                open_science_signals.c.source == RETRACTION_SOURCE,
            )
        )
        .mappings()
        .first()
    )


LMM_SIGNAL = "lmm"
LMM_SOURCE = "lmm"


def store_lmm(conn: Connection, paper_id: int, *, is_lmm: bool, incomplete_keys: list[str]) -> None:
    """Upsert a paper's LMM-reporting-completeness status (backlog #23). `status='incomplete'` when ≥1 check is
    `not-found`, else `'complete'`. When `is_lmm` is False (not detectably a mixed-model paper), no row is worth
    keeping — DELETE any prior one instead (a non-mixed-model paper isn't a "not-applicable" fact worth persisting
    library-wide; this also keeps re-extraction/un-gating honest if a paper's detected genre ever changes)."""
    if not is_lmm:
        conn.execute(
            delete(open_science_signals).where(
                open_science_signals.c.paper_id == paper_id, open_science_signals.c.signal_type == LMM_SIGNAL
            )
        )
        return
    conn.execute(
        insert(open_science_signals)
        .prefix_with("OR REPLACE")
        .values(
            paper_id=paper_id,
            signal_type=LMM_SIGNAL,
            source=LMM_SOURCE,
            status="incomplete" if incomplete_keys else "complete",
            evidence_snippet=json.dumps({"missing": list(incomplete_keys)}) if incomplete_keys else None,
        )
    )


def count_lmm_flagged(conn: Connection) -> int:
    """How many papers have an incomplete LMM-reporting checklist — drives the library 'N incomplete' chip."""
    total = conn.execute(
        select(func.count())
        .select_from(open_science_signals)
        .where(open_science_signals.c.signal_type == LMM_SIGNAL, open_science_signals.c.status == "incomplete")
    ).scalar()
    return int(total or 0)


def get_lmm_summary(conn: Connection, paper_id: int) -> RowMapping | None:
    """The stored LMM status row for a paper, or None if it's never been persisted (not a mixed-model paper, or
    never viewed/batch-checked)."""
    return (
        conn.execute(
            select(open_science_signals).where(
                open_science_signals.c.paper_id == paper_id,
                open_science_signals.c.signal_type == LMM_SIGNAL,
                open_science_signals.c.source == LMM_SOURCE,
            )
        )
        .mappings()
        .first()
    )
