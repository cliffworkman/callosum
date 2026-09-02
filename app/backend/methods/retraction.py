"""Retraction producer (inc 131) — the first real findings producer.

Detect retractions / corrections / expressions-of-concern for a paper from MULTIPLE per-DOI sources (Crossref +
OpenAlex in SP1), merge them, and persist:
  - a FACT in `paper_findings` (the Review-pane FactMark + the ◆-fact card mark) — retracted/flagged papers only;
  - a per-paper CHECK STATUS in `open_science_signals` (the *honesty* record: a checked-clean paper gets a
    positive 'none'; a no-DOI paper is 'unchecked' — silence is never 'clean') + the library "Retracted" filter.

Honesty (Principles): a retraction is a FACT relayed from an authoritative registry — never a 'candidate to
confirm', never an author-level/reputation judgment (the A-A no-accusation veto), and every FACT carries its
evidence (the flagging `sources` + the notice link). The merge/detect/apply logic here is pure + testable; the
network checkers are injected (`RetractionChecker`), so tests and the headed driver run offline.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Connection

from app.backend.acquisition.registry import PaperRef
from app.backend.persistence.findings_repo import upsert_findings
from app.backend.persistence.repository import get_paper
from app.backend.persistence.retraction_repo import lookup_retraction_record
from app.backend.persistence.signals_repo import store_retraction_status
from app.backend.persistence.tags_repo import add_tag_to_paper, remove_tag_from_paper_by_name
from integrations.crossref.adapter import CrossrefClient
from integrations.openalex.adapter import OpenAlexClient

FINDING_SOURCE = "retraction"  # the `paper_findings.source` for retraction FACTs
STATUS_RANK = {"concern": 0, "correction": 1, "retracted": 2}
_NATURE_BY_STATUS = {"retracted": "Retraction", "correction": "Correction", "concern": "Expression of Concern"}
# Backlog #19: the same FACT also projects as a real, non-editable tag (`tags_repo.TAG_SOURCE_NAMESPACES`'s
# reserved `system:` namespace) so it's reachable through the generic tag/tag-filter mechanism (the sidebar Tags
# browser, GET /papers?tag_id=) rather than only the bespoke `signal=retraction-retracted` facet (which stays,
# unchanged — this is additive discovery, not a replacement). Scoped to `status == "retracted"` only, matching
# `signals_repo.count_retraction_flagged`'s existing definition of "flagged" (not correction/concern).
RETRACTION_TAG_SOURCE = "system:retraction"
RETRACTION_TAG_NAME = "system:retraction:retracted"
# A correction is the positive self-correction slice of the same registry fact. Keep a separate system tag so it
# is discoverable/filterable without treating it as a retraction or inventing a second network producer.
SELF_CORRECTION_TAG_SOURCE = "system:self-correction"
SELF_CORRECTION_TAG_NAME = "system:self-correction:correction"


@dataclass(frozen=True)
class RetractionSignal:
    """One source's verdict for a paper. `status` ∈ retracted/correction/concern."""

    source: str
    status: str
    nature: str | None = None
    date: str | None = None
    reason: str | None = None
    notice_doi: str | None = None
    notice_url: str | None = None


@dataclass(frozen=True)
class MergedRetraction:
    status: str
    nature: str
    date: str | None
    reason: str | None
    notice_doi: str | None
    notice_url: str | None
    sources: list[str]


@dataclass(frozen=True)
class RetractionOutcome:
    status_kind: str  # flagged | none (complete clean) | unchecked (no DOI) | unavailable (incomplete check)
    merged: MergedRetraction | None = None
    sources_checked: list[str] = field(default_factory=list)
    sources_failed: list[str] = field(default_factory=list)


@dataclass
class RetractionChecker:
    """A named source checker: `(conn, paper) -> RetractionSignal | None` (None = clean / unresolved)."""

    source: str
    fetch: Callable[[Connection, Mapping[str, Any]], RetractionSignal | None]

    def __call__(self, conn: Connection, paper: Mapping[str, Any]) -> RetractionSignal | None:
        return self.fetch(conn, paper)


def is_evidence_linked_correction(outcome: RetractionOutcome) -> bool:
    """Whether this outcome can support the positive badge: an explicit correction plus an openable record."""
    return bool(outcome.merged is not None and outcome.merged.status == "correction" and outcome.merged.notice_url)


def merge_signals(signals: list[RetractionSignal | None]) -> MergedRetraction | None:
    """Union per-source signals → one finding: escalate the status (retraction > correction > concern), keep the
    richest non-null detail across sources, list all flagging sources. None if nothing flagged."""
    present = [s for s in signals if s is not None]
    if not present:
        return None
    status = max((s.status for s in present), key=lambda st: STATUS_RANK.get(st, 0))

    def first(attr: str) -> Any:
        for s in present:
            value = getattr(s, attr)
            if value:
                return value
        return None

    notice_doi = first("notice_doi")
    notice_url = first("notice_url") or (f"https://doi.org/{notice_doi}" if notice_doi else None)
    return MergedRetraction(
        status=status,
        nature=first("nature") or _NATURE_BY_STATUS.get(status, "Retraction"),
        date=first("date"),
        reason=first("reason"),
        notice_doi=notice_doi,
        notice_url=notice_url,
        sources=sorted({s.source for s in present}),
    )


def detect_retraction(
    conn: Connection, paper: Mapping[str, Any], *, checkers: list[RetractionChecker]
) -> RetractionOutcome:
    """Run each checker over a paper (best-effort — a source error is skipped, never aborts), merge the signals.
    No DOI → 'unchecked' (no source is even consulted). DOI + nothing flagged → 'none' (honestly checked-clean)."""
    if not _paper_doi(paper):
        return RetractionOutcome(status_kind="unchecked")
    signals: list[RetractionSignal | None] = []
    checked: list[str] = []
    failed: list[str] = []
    for checker in checkers:
        try:
            signal = checker(conn, paper)
        except Exception:  # a source being down must never abort the whole check
            failed.append(checker.source)
            continue
        checked.append(checker.source)
        if signal is not None:
            signals.append(signal)
    merged = merge_signals(signals)
    sources_checked = sorted(set(checked))
    sources_failed = sorted(set(failed))
    if merged is not None:
        return RetractionOutcome(
            status_kind=merged.status,
            merged=merged,
            sources_checked=sources_checked,
            sources_failed=sources_failed,
        )
    if sources_failed:
        return RetractionOutcome(
            status_kind="unavailable", sources_checked=sources_checked, sources_failed=sources_failed
        )
    return RetractionOutcome(status_kind="none", merged=None, sources_checked=sources_checked)


def apply_retraction(conn: Connection, paper_id: int, outcome: RetractionOutcome) -> None:
    """Persist an outcome: the FACT when flagged (else supersede any prior FACT), the check-status row, and the
    #19 system-fact tags (retracted and positive correction — kept in lockstep so both the batch job and the
    on-import hook stay covered from this one call site)."""
    if outcome.status_kind == "unavailable":
        return  # An incomplete check cannot erase or restamp previously established evidence.
    checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if outcome.merged is not None:
        merged = outcome.merged
        payload: dict[str, Any] = {"status": merged.status, "nature": merged.nature, "sources": merged.sources}
        for key in ("date", "reason", "notice_doi", "notice_url"):
            value = getattr(merged, key)
            if value:
                payload[key] = value
        upsert_findings(conn, paper_id, FINDING_SOURCE, [{"kind": "fact", "payload": payload}])
        store_retraction_status(conn, paper_id, status=merged.status, sources=merged.sources, checked_at=checked_at)
    else:
        upsert_findings(conn, paper_id, FINDING_SOURCE, [])  # supersede any prior FACT (un-retraction)
        store_retraction_status(
            conn, paper_id, status=outcome.status_kind, sources=outcome.sources_checked, checked_at=checked_at
        )
    if outcome.merged is not None and outcome.merged.status == "retracted":
        add_tag_to_paper(conn, paper_id, RETRACTION_TAG_NAME, import_source=RETRACTION_TAG_SOURCE)
    else:
        remove_tag_from_paper_by_name(conn, paper_id, RETRACTION_TAG_NAME)
    if is_evidence_linked_correction(outcome):
        add_tag_to_paper(conn, paper_id, SELF_CORRECTION_TAG_NAME, import_source=SELF_CORRECTION_TAG_SOURCE)
    else:
        remove_tag_from_paper_by_name(conn, paper_id, SELF_CORRECTION_TAG_NAME)


def auto_check_retractions(conn: Connection, paper_ids: list[int], *, checkers: list[RetractionChecker]) -> int:
    """Best-effort retraction check over a set of papers — the **on-import** hook (inc 134). A failure for any one
    paper (a missing row, a source error) is swallowed and never aborts the others, so it can't break an import.
    Returns the number flagged retracted. (The Crossref checker reads the cache a just-run enrich populated.)"""
    flagged = 0
    for paper_id in paper_ids:
        try:
            outcome = detect_retraction(conn, get_paper(conn, paper_id), checkers=checkers)
            apply_retraction(conn, paper_id, outcome)
            if outcome.merged is not None and outcome.merged.status == "retracted":
                flagged += 1
        except Exception:
            continue
    return flagged


def _paper_doi(paper: Mapping[str, Any]) -> str | None:
    doi = paper.get("doi") if hasattr(paper, "get") else None
    if doi:
        return str(doi).strip()
    csl = paper.get("csl_json") if hasattr(paper, "get") else None
    if isinstance(csl, dict):
        value = csl.get("DOI") or csl.get("doi")
        if value:
            return str(value).strip()
    return None


def _crossref_fetch(conn: Connection, paper: Mapping[str, Any]) -> RetractionSignal | None:
    doi = _paper_doi(paper)
    if not doi:
        return None
    raw = CrossrefClient().lookup_retraction(conn, doi)
    return RetractionSignal(source="crossref", **raw) if raw else None


def _openalex_fetch(conn: Connection, paper: Mapping[str, Any]) -> RetractionSignal | None:
    doi = _paper_doi(paper)
    if not doi:
        return None
    raw = OpenAlexClient().lookup_retraction(conn, PaperRef(doi=doi))
    return RetractionSignal(source="openalex", **raw) if raw else None


def _retraction_watch_fetch(conn: Connection, paper: Mapping[str, Any]) -> RetractionSignal | None:
    # The local Retraction Watch mirror (inc 132) — offline, the richest source (nature/date/reason/notice).
    doi = _paper_doi(paper)
    if not doi:
        return None
    raw = lookup_retraction_record(conn, doi)
    return RetractionSignal(source="retraction-watch", **raw) if raw else None


CROSSREF_CHECKER = RetractionChecker("crossref", _crossref_fetch)
OPENALEX_CHECKER = RetractionChecker("openalex", _openalex_fetch)
RETRACTION_WATCH_CHECKER = RetractionChecker("retraction-watch", _retraction_watch_fetch)
# RW first → its richer detail (reason/date/notice) wins merge_signals' first-non-null pick. If the mirror is
# empty (never downloaded), it returns None and the per-DOI sources still work.
DEFAULT_CHECKERS: list[RetractionChecker] = [RETRACTION_WATCH_CHECKER, CROSSREF_CHECKER, OPENALEX_CHECKER]
