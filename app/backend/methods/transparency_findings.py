"""Transparency persistence producer (backlog #44 increment 1b, inc 251).

Turns the inc-250 ephemeral per-paper transparency audit into persistent, library-wide signal. For a paper:
- **detected-present** disclosures become **findings-FACTs** (`paper_findings`, source `"transparency"`) — evidence-
  carrying positive facts that render as marks in the Review pane (inc 130). **An absence is NEVER a FACT** (silence≠
  certificate; the A-A no-accusation boundary — the inc-250-declined "NO open data" fact).
- every disclosure's check **status** (detected / not-detected / not-applicable) is stored in `open_science_signals`
  (a check RESULT, not a claim about the paper) to power the review-queue library filter + the chip.

The consumer-side statcheck/retraction persistence pattern (inc 97/131), applied to transparency. Local, no egress,
no LLM. See methods/transparency.py (the detector) + persistence/signals_repo.py (the status store).
"""

from __future__ import annotations

from sqlalchemy import Connection

from app.backend.methods.transparency import detect_transparency
from app.backend.persistence.findings_repo import upsert_findings
from app.backend.persistence.signals_repo import store_transparency_status

FINDING_SOURCE = "transparency"


def persist_transparency(conn: Connection, paper_id: int, chunks: list) -> dict:
    """Run the transparency detector over a paper's chunks and persist: present-disclosure FACTs (evidence-carrying)
    + every disclosure's check status. Idempotent — a re-run that no longer detects a disclosure supersedes its stale
    FACT (via `upsert_findings`' content_key) and flips its status row to `not-detected`. Returns a small summary."""
    report = detect_transparency(chunks)

    facts = [
        {
            "kind": "fact",
            "payload": {
                "key": c.key,
                "label": c.label,
                "desc": f"{c.label} — disclosed",
                "evidence": c.evidence,
                "page": c.page,
                "basis": c.basis,
            },
        }
        for c in report.checks
        if c.status == "present"
    ]
    # An empty list supersedes any prior transparency FACTs for this paper (a re-run that detects fewer).
    upsert_findings(conn, paper_id, FINDING_SOURCE, facts)
    store_transparency_status(conn, paper_id, report)

    return {"present": len(facts), "checks": len(report.checks)}
