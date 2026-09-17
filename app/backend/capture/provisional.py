"""Provisional direct-PDF capture: preserve first, identify opportunistically (#61 / #96).

Replaces the terminal refusal `f03b242c` introduced for an identity-poor direct-PDF capture. That
refusal was correct on one axis (never fabricate a canonical Paper from a filename) and wrong on
another (the user loses the artifact they explicitly clicked "Add" on). See `admission.py`'s
2026-09-16 addendum for the chronology.

Two identities are kept separate throughout this module, because they diverge as soon as identical
bytes are captured more than once (steering: "dedupe the object, not the encounter"):

* **artifact** — the distinct PDF object, keyed by content hash (`provisional_artifacts`).
* **capture event** — one encounter with that object (`capture_events`), keyed by the transport
  `capture_id` minted per `POST /capture/item` call.

Governing priority for every crash/failure path below: an orphaned-but-preserved artifact is always
better than tidy metadata with missing user bytes.
"""

from __future__ import annotations

import json
import os
import shutil
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from hashlib import sha256
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import fitz
from sqlalchemy import Connection, Engine

from app.backend.capture.admission import CAPTURE_SOURCE, attachment_decision
from app.backend.embeddings.models import normalize_text, strip_punctuation
from app.backend.metadata.doi import DOI_PATTERN, find_doi_in_text, normalize_doi
from app.backend.metadata.doi_add import add_paper_by_doi
from app.backend.pdf_processing.ingest import attach_pdf_to_paper
from app.backend.pdf_processing.sections import SectionTracker
from app.backend.persistence import capture_events_repo, provisional_artifacts_repo
from app.backend.persistence.repository import find_existing_paper_by_identity
from app.backend.persistence.sqlite_retry import run_write

# Only the front matter of a direct-PDF capture can ever influence the promotion decision (see
# `_classify_position`), so scanning past this page never changes the outcome -- bounding the scan
# here is a real optimization, not a coverage gap. Kept as a module constant so it is trivially
# revisited if a real-world fixture ever needs more front matter than this.
MAX_SCAN_PAGES = 3
MAX_RESOLVE_CANDIDATES = 3

QUEUE_DIR_NAME = "_Import Queue"
PROVENANCE_DIR_NAME = ".provenance"
PROVENANCE_ARTIFACTS_SUBDIR = "artifacts"
SIDECAR_SCHEMA_VERSION = 1

# Terminal CaptureResult.status values the router surfaces for the two non-promoted outcomes. A
# successful promotion instead reuses admission.py's existing STATUS_ADDED/STATUS_ALREADY_PRESENT --
# the extension's resultKeyFor already renders those correctly, so no third status is needed there.
STATUS_PROVISIONAL_QUEUED = "direct_pdf_queued_for_review"
STATUS_PROVISIONAL_ATTACHMENT_BLOCKED = "direct_pdf_attachment_blocked"


def queue_dir(library_root: Path) -> Path:
    return library_root / QUEUE_DIR_NAME


def provenance_artifacts_dir(library_root: Path) -> Path:
    return library_root / PROVENANCE_DIR_NAME / PROVENANCE_ARTIFACTS_SUBDIR


def sidecar_path(library_root: Path, artifact_id: str) -> Path:
    return provenance_artifacts_dir(library_root) / f"{artifact_id}.json"


def sanitize_source_url(raw: str | None) -> str | None:
    """Scheme + host + path only. Query strings and fragments are dropped unconditionally.

    A direct-PDF URL can carry signed-access parameters, session-ish tokens, or tracking data in its
    query string; none of that is bibliographic provenance, and persisting it would turn
    `.provenance` into incidental credential storage -- exactly what issue #61's "browser context, not
    a credentialed downloader" boundary forbids. Userinfo is dropped for the same reason.
    """
    if not raw:
        return None
    try:
        parts = urlsplit(raw)
    except ValueError:
        return None
    if not parts.scheme or not parts.netloc:
        return None
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    return urlunsplit((parts.scheme, host, parts.path, "", ""))


# --- candidate extraction -------------------------------------------------------------------------


@dataclass(frozen=True)
class DoiCandidate:
    doi: str
    page_number: int
    position_class: str  # "front_matter" | "body" | "references"


@dataclass
class _Evidence:
    candidates: list[dict[str, Any]] = field(default_factory=list)
    title_candidates: list[str] = field(default_factory=list)
    resolutions: list[dict[str, Any]] = field(default_factory=list)
    decision: str = ""
    decision_reason: str = ""

    def as_json(self) -> str:
        return json.dumps(
            {
                "schema_version": SIDECAR_SCHEMA_VERSION,
                "candidates": self.candidates,
                "title_candidates": self.title_candidates,
                "resolutions": self.resolutions,
                "decision": self.decision,
                "decision_reason": self.decision_reason,
            }
        )


def _classify_position(page_number: int, current_section: str | None) -> str:
    if current_section == "references":
        return "references"
    if page_number <= 2 and current_section is None:
        return "front_matter"
    return "body"


def _extract_candidates(pdf_path: Path) -> tuple[list[DoiCandidate], list[str]]:
    """Scan metadata + the first `MAX_SCAN_PAGES` pages for DOI and title candidates.

    Bounded to the front matter deliberately: `_promote_if_strong` only ever treats a
    `front_matter`-classified candidate as eligible, so nothing past this window can change the
    promotion decision.
    """
    candidates: list[DoiCandidate] = []
    title_candidates: list[str] = []
    with fitz.open(pdf_path) as document:
        meta_title = (document.metadata or {}).get("title")
        if meta_title and isinstance(meta_title, str) and len(meta_title.strip()) > 8:
            title_candidates.append(meta_title.strip())

        metadata_text = " ".join(str(v) for v in (document.metadata or {}).values() if v)
        meta_doi = find_doi_in_text(metadata_text)
        if meta_doi:
            candidates.append(DoiCandidate(doi=meta_doi, page_number=1, position_class="front_matter"))

        tracker = SectionTracker()
        page_count = min(document.page_count, MAX_SCAN_PAGES)
        first_page_lines: list[str] = []
        for page_index in range(page_count):
            page = document[page_index]
            page_number = page_index + 1
            text_dict = page.get_text("dict", sort=True)
            for block in text_dict.get("blocks", []):
                if block.get("type") != 0:
                    continue
                lines = []
                for line in block.get("lines", []):
                    line_text = "".join(span.get("text", "") for span in line.get("spans", []))
                    if line_text.strip():
                        lines.append(line_text)
                block_text = "\n".join(lines).strip()
                if not block_text:
                    continue
                tracker.observe_block(block_text)
                if page_number == 1:
                    first_page_lines.extend(lines)
                for match in DOI_PATTERN.finditer(block_text):
                    doi = normalize_doi(match.group(1))
                    if not doi:
                        continue
                    position_class = _classify_position(page_number, tracker.current_section)
                    candidates.append(DoiCandidate(doi=doi, page_number=page_number, position_class=position_class))

        if not title_candidates:
            for line in first_page_lines:
                stripped = line.strip()
                if (
                    len(stripped) > 20
                    and not stripped.isupper()
                    and "doi" not in stripped.lower()
                    and not stripped.lower().startswith(("http://", "https://"))
                ):
                    title_candidates.append(stripped)
                    break

    return candidates, title_candidates


def _titles_agree(wanted: str, found: str | None) -> float:
    """NFKC+casefold+tokenize Jaccard AND difflib ratio -- the same two-part test as OpenAlex's
    private `_title_matches`, reimplemented locally rather than reaching into that module."""
    if not found:
        return 0.0

    def normalized(value: str) -> str:
        folded = unicodedata.normalize("NFKC", strip_punctuation(value)).casefold()
        return normalize_text(folded)

    a, b = normalized(wanted), normalized(found)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    a_tokens, b_tokens = set(a.split()), set(b.split())
    overlap = len(a_tokens & b_tokens) / max(len(a_tokens | b_tokens), 1)
    ratio = SequenceMatcher(None, a, b).ratio()
    return ratio if (overlap >= 0.9 and ratio >= 0.92) else 0.0


# --- resolution + scoring --------------------------------------------------------------------------


def _resolve_and_score(
    conn: Connection,
    candidates: list[DoiCandidate],
    title_candidates: list[str],
    *,
    crossref_client: Any,
    evidence: _Evidence,
) -> str | None:
    """Returns the single strong DOI iff exactly one qualifies; otherwise None. Every candidate and
    disposition is recorded in `evidence` regardless of outcome."""
    seen_dois: dict[str, DoiCandidate] = {}
    for candidate in candidates:
        if candidate.position_class == "references":
            evidence.candidates.append(
                {
                    "doi": candidate.doi,
                    "page": candidate.page_number,
                    "position_class": candidate.position_class,
                    "disposition": "rejected_reference_section",
                }
            )
            continue
        if candidate.doi not in seen_dois:
            seen_dois[candidate.doi] = candidate
        evidence.candidates.append(
            {
                "doi": candidate.doi,
                "page": candidate.page_number,
                "position_class": candidate.position_class,
                "disposition": "observed",
            }
        )

    front_matter_dois = [doi for doi, c in seen_dois.items() if c.position_class == "front_matter"]
    evidence.title_candidates = list(title_candidates)

    strong: list[str] = []
    for doi in front_matter_dois[:MAX_RESOLVE_CANDIDATES]:
        resolution = crossref_client.resolve_doi(conn, doi) if crossref_client is not None else None
        if resolution is None or not resolution.resolved or not resolution.csl_json:
            evidence.resolutions.append({"resolver": "crossref", "doi": doi, "disposition": "unresolved"})
            continue
        csl = resolution.csl_json
        resolved_title = csl.get("title")
        best_similarity = 0.0
        for title in title_candidates:
            best_similarity = max(best_similarity, _titles_agree(title, resolved_title))
        agrees = best_similarity > 0.0
        evidence.resolutions.append(
            {
                "resolver": "crossref",
                "doi": doi,
                "resolved_title": resolved_title,
                "title_similarity": round(best_similarity, 4),
                "disposition": "strong" if agrees else "insufficient_corroboration",
            }
        )
        if agrees:
            strong.append(doi)

    if len(strong) == 1:
        return strong[0]
    return None


# --- crash-safe durability sequence -----------------------------------------------------------------


def _atomic_write_bytes(final_path: Path, data: bytes) -> None:
    final_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = final_path.parent / f".{final_path.name}.{uuid4().hex}.tmp"
    with tmp_path.open("wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp_path, final_path)


def _atomic_write_text(final_path: Path, text: str) -> None:
    final_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = final_path.parent / f".{final_path.name}.{uuid4().hex}.tmp"
    tmp_path.write_text(text, encoding="utf-8")
    os.replace(tmp_path, final_path)


@dataclass(frozen=True)
class ProvisionalIngestResult:
    artifact_id: str
    identity_state: str
    promotion_state: str
    resolved_paper_id: int | None
    # Whether resolved_paper_id was CREATED by this call. False whenever the paper already existed --
    # including every dedupe replay of an already-known artifact -- so the router can pick
    # STATUS_ADDED vs STATUS_ALREADY_PRESENT the same way the non-provisional DOI branch does.
    created: bool = False


def ingest_provisional_pdf(
    engine: Engine,
    *,
    capture_event_id: str,
    validated_pdf_bytes: bytes,
    library_root: Path,
    source_url: str | None,
    captured_at_client: str | None,
    original_filename: str | None,
    producer_kind: str | None,
    crossref_client: Any,
    vector_store: Any,
    embedding_model: Any,
) -> ProvisionalIngestResult:
    """Durability boundaries A-C below are each a real, independently-survivable step. See the
    module docstring and the plan's "Durability sequence and crash boundaries" section for the full
    enumeration of what a crash between any two steps leaves behind and how `recover_at_startup`
    repairs it."""
    content_hash = sha256(validated_pdf_bytes).hexdigest()
    sanitized_url = sanitize_source_url(source_url)

    with engine.connect() as conn:
        existing = provisional_artifacts_repo.find_by_content_hash(conn, content_hash)

    if existing is not None:
        # Dedupe the OBJECT, not the encounter: no new file, no new artifact row -- but this genuinely
        # is new provenance (a fresh capture_event), recorded in its own committed transaction.
        artifact_id = str(existing["id"])
        run_write(
            engine,
            lambda conn: capture_events_repo.create(
                conn,
                capture_event_id=capture_event_id,
                artifact_id=artifact_id,
                source_url=sanitized_url,
                captured_at_client=captured_at_client,
                original_filename=original_filename,
                producer_kind=producer_kind,
            ),
        )
        return ProvisionalIngestResult(
            artifact_id=artifact_id,
            identity_state=str(existing["identity_state"]),
            promotion_state=str(existing["promotion_state"]),
            resolved_paper_id=existing["resolved_paper_id"],
        )

    artifact_id = uuid4().hex
    pdf_path = queue_dir(library_root) / f"{artifact_id}.pdf"

    # Durability boundary A: bytes are safe on disk, independent of the database.
    _atomic_write_bytes(pdf_path, validated_pdf_bytes)

    # Durability boundary B: the sidecar can reconstruct this artifact + its first encounter even if
    # the process dies before the database row is ever created.
    sidecar = {
        "schema_version": SIDECAR_SCHEMA_VERSION,
        "artifact_id": artifact_id,
        "content_hash": content_hash,
        "first_capture_event": {
            "capture_event_id": capture_event_id,
            "source_url": sanitized_url,
            "captured_at_client": captured_at_client,
            "original_filename": original_filename,
            "producer_kind": producer_kind,
        },
    }
    sidecar_state = "ok"
    try:
        _atomic_write_text(sidecar_path(library_root, artifact_id), json.dumps(sidecar))
    except OSError:
        sidecar_state = "error"  # never fails the capture -- see module docstring's DB/JSON rule

    # Durability boundary C: one committed transaction records both the artifact and its first
    # encounter. If this never commits (crash before C), `recover_at_startup` adopts the orphaned
    # file+sidecar from boundary A/B rather than losing it.
    def _record(conn: Connection) -> None:
        provisional_artifacts_repo.create(
            conn,
            artifact_id=artifact_id,
            content_hash=content_hash,
            pdf_path=str(pdf_path),
            provenance_sidecar_state=sidecar_state,
        )
        capture_events_repo.create(
            conn,
            capture_event_id=capture_event_id,
            artifact_id=artifact_id,
            source_url=sanitized_url,
            captured_at_client=captured_at_client,
            original_filename=original_filename,
            producer_kind=producer_kind,
        )

    run_write(engine, _record)

    # Identity inference runs AFTER the commit above, in its own transaction(s), so a crash here never
    # rolls back the fact that the capture was already durably recorded.
    result = _run_identity_pipeline(
        engine,
        artifact_id=artifact_id,
        pdf_path=pdf_path,
        library_root=library_root,
        crossref_client=crossref_client,
        vector_store=vector_store,
        embedding_model=embedding_model,
    )
    return result


def _run_identity_pipeline(
    engine: Engine,
    *,
    artifact_id: str,
    pdf_path: Path,
    library_root: Path,
    crossref_client: Any,
    vector_store: Any,
    embedding_model: Any,
) -> ProvisionalIngestResult:
    evidence = _Evidence()
    try:
        candidates, title_candidates = _extract_candidates(pdf_path)
    except Exception:  # any extraction hiccup degrades to "queued for review" -- never lost, never 500
        candidates, title_candidates = [], []
        evidence.decision = "queued"
        evidence.decision_reason = "extraction failed; treated as unresolved"
        return _finish_unresolved(engine, artifact_id, library_root, evidence)

    def _score(conn: Connection) -> str | None:
        return _resolve_and_score(
            conn, candidates, title_candidates, crossref_client=crossref_client, evidence=evidence
        )

    try:
        strong_doi = run_write(engine, _score)
    except Exception:
        evidence.decision = "queued"
        evidence.decision_reason = "resolution failed; treated as unresolved"
        return _finish_unresolved(engine, artifact_id, library_root, evidence)

    if strong_doi is None:
        evidence.decision = "queued"
        evidence.decision_reason = "no uniquely strong front-matter DOI candidate"
        return _finish_unresolved(engine, artifact_id, library_root, evidence)

    evidence.decision = "promotion_attempted"
    evidence.decision_reason = f"unique strong candidate: {strong_doi}"
    return _attempt_promotion(
        engine,
        artifact_id=artifact_id,
        pdf_path=pdf_path,
        library_root=library_root,
        doi=strong_doi,
        crossref_client=crossref_client,
        vector_store=vector_store,
        embedding_model=embedding_model,
        evidence=evidence,
    )


def _finish_unresolved(
    engine: Engine, artifact_id: str, library_root: Path, evidence: _Evidence
) -> ProvisionalIngestResult:
    def _update(conn: Connection) -> None:
        provisional_artifacts_repo.update_resolution(
            conn,
            artifact_id,
            identity_state="unresolved",
            promotion_state="pending_review",
            evidence_json=evidence.as_json(),
        )

    run_write(engine, _update)
    _refresh_sidecar(engine, artifact_id, library_root)
    return ProvisionalIngestResult(
        artifact_id=artifact_id, identity_state="unresolved", promotion_state="pending_review", resolved_paper_id=None
    )


def _resolve_and_admit_doi(conn: Connection, doi: str, crossref_client: Any) -> tuple[str, int | None, bool]:
    """Normalize + duplicate-check + Crossref-resolve + create-or-surface, via the SAME shared primitive
    every other capture/import path uses. Never a second identity path."""
    result = add_paper_by_doi(conn, doi, crossref_client=crossref_client, imported_source=CAPTURE_SOURCE)
    if result.status in {"invalid", "unresolved"} or result.paper_id is None:
        return "unresolved", None, False
    created = result.status == "created"
    return "ok", int(result.paper_id), created


def attempt_attach_to_paper(
    engine: Engine,
    *,
    artifact_id: str,
    pdf_path: Path,
    library_root: Path,
    paper_id: int,
    created: bool,
    vector_store: Any,
    embedding_model: Any,
    evidence: _Evidence,
) -> ProvisionalIngestResult:
    """Never relinquishes the queue copy until canonical promotion is durable.

    `attachment_decision` runs first (metadata only). If promotion is safe, the queue bytes are COPIED
    to a staged canonical path; only after `attach_pdf_to_paper` succeeds is the original queue file
    deleted. Any failure at any point after the copy leaves the queue file untouched and removes only
    the staged duplicate. Shared by the automatic pipeline, the manual "confirm identity" review action,
    and "retry" -- there is exactly one attach subroutine, never a review-specific shortcut.
    """

    def _check_attachment(conn: Connection) -> tuple[bool, str]:
        return attachment_decision(conn, paper_id, newly_created=created)

    accepted, reason = run_write(engine, _check_attachment)
    if not accepted:
        return _finish_attachment_blocked(
            engine,
            artifact_id,
            library_root,
            paper_id=paper_id,
            created=created,
            promotion_state="attachment_conflict",
            evidence=evidence,
            detail=reason,
        )

    staged_path = library_root / f"capture-{artifact_id}.pdf"
    try:
        shutil.copy2(pdf_path, staged_path)
    except OSError:
        return _finish_attachment_blocked(
            engine,
            artifact_id,
            library_root,
            paper_id=paper_id,
            created=created,
            promotion_state="processing_failed",
            evidence=evidence,
            detail="could not stage the canonical file copy",
        )

    def _attach(conn: Connection) -> dict[str, Any]:
        return attach_pdf_to_paper(
            conn,
            paper_id,
            staged_path,
            storage_mode="managed",
            original_path=str(staged_path),
            import_source=CAPTURE_SOURCE,
            vector_store=vector_store,
            embedding_model=embedding_model,
        )

    try:
        run_write(engine, _attach)
    except Exception as exc:
        staged_path.unlink(missing_ok=True)  # remove ONLY the staged duplicate; queue copy is untouched
        promotion_state = "indexing_unavailable" if _looks_like_embedding_failure(exc) else "processing_failed"
        return _finish_attachment_blocked(
            engine,
            artifact_id,
            library_root,
            paper_id=paper_id,
            created=created,
            promotion_state=promotion_state,
            evidence=evidence,
            detail=str(exc)[:300],
        )

    # Success: the staged copy IS the canonical file now. Only now does the queue copy go away.
    pdf_path.unlink(missing_ok=True)
    evidence.decision = "promoted"

    def _update(conn: Connection) -> None:
        provisional_artifacts_repo.update_resolution(
            conn,
            artifact_id,
            identity_state="resolved",
            promotion_state="promoted",
            resolved_paper_id=paper_id,
            pdf_path=str(staged_path),
            evidence_json=evidence.as_json(),
        )

    run_write(engine, _update)
    _refresh_sidecar(engine, artifact_id, library_root)
    return ProvisionalIngestResult(
        artifact_id=artifact_id,
        identity_state="resolved",
        promotion_state="promoted",
        resolved_paper_id=paper_id,
        created=created,
    )


def _attempt_promotion(
    engine: Engine,
    *,
    artifact_id: str,
    pdf_path: Path,
    library_root: Path,
    doi: str,
    crossref_client: Any,
    vector_store: Any,
    embedding_model: Any,
    evidence: _Evidence,
) -> ProvisionalIngestResult:
    """The automatic pipeline's promotion attempt: admit by DOI, then attach. See
    `attempt_attach_to_paper` for the shared, safety-critical second half."""
    status, paper_id, created = run_write(engine, lambda conn: _resolve_and_admit_doi(conn, doi, crossref_client))
    if status != "ok" or paper_id is None:
        evidence.decision_reason += " (DOI admission failed unexpectedly after resolution succeeded)"
        return _finish_unresolved(engine, artifact_id, library_root, evidence)

    return attempt_attach_to_paper(
        engine,
        artifact_id=artifact_id,
        pdf_path=pdf_path,
        library_root=library_root,
        paper_id=paper_id,
        created=created,
        vector_store=vector_store,
        embedding_model=embedding_model,
        evidence=evidence,
    )


def _looks_like_embedding_failure(exc: Exception) -> bool:
    text = str(exc).lower()
    return "embed" in text or "model" in text


def _finish_attachment_blocked(
    engine: Engine,
    artifact_id: str,
    library_root: Path,
    *,
    paper_id: int,
    created: bool,
    promotion_state: str,
    evidence: _Evidence,
    detail: str,
) -> ProvisionalIngestResult:
    evidence.decision = "attachment_blocked"
    evidence.decision_reason = detail

    def _update(conn: Connection) -> None:
        provisional_artifacts_repo.update_resolution(
            conn,
            artifact_id,
            identity_state="resolved",
            promotion_state=promotion_state,
            resolved_paper_id=paper_id,
            evidence_json=evidence.as_json(),
        )

    run_write(engine, _update)
    _refresh_sidecar(engine, artifact_id, library_root)
    return ProvisionalIngestResult(
        artifact_id=artifact_id,
        identity_state="resolved",
        promotion_state=promotion_state,
        resolved_paper_id=paper_id,
        created=created,
    )


def _refresh_sidecar(engine: Engine, artifact_id: str, library_root: Path) -> None:
    """Best-effort: DB is authoritative; the sidecar is a mirror. A failure here never fails the
    capture, and never blocks the caller -- it just leaves `provenance_sidecar_state="error"` for a
    later integrity pass to repair."""
    with engine.connect() as conn:
        row = provisional_artifacts_repo.get(conn, artifact_id)
        events = capture_events_repo.list_for_artifact(conn, artifact_id) if row else []
    if row is None:
        return
    payload = {
        "schema_version": SIDECAR_SCHEMA_VERSION,
        "artifact_id": artifact_id,
        "content_hash": row["content_hash"],
        "identity_state": row["identity_state"],
        "promotion_state": row["promotion_state"],
        "resolved_paper_id": row["resolved_paper_id"],
        "evidence": json.loads(row["evidence_json"]) if row["evidence_json"] else None,
        "capture_events": [
            {
                "capture_event_id": e["id"],
                "source_url": e["source_url"],
                "captured_at_client": e["captured_at_client"],
                "received_at_server": str(e["received_at_server"]),
                "original_filename": e["original_filename"],
            }
            for e in events
        ],
    }
    try:
        _atomic_write_text(sidecar_path(library_root, artifact_id), json.dumps(payload))
        state = "ok"
    except OSError:
        state = "error"
    with engine.connect() as conn:
        provisional_artifacts_repo.update_sidecar_state(conn, artifact_id, state)
        conn.commit()


# --- manual review actions (confirm / retry / preview) ----------------------------------------------
#
# "Observation ≠ inference ≠ canonical fact" (#96), applied here: an explicit user decision is recorded
# as a NEW entry in `evidence_json["user_actions"]`, appended alongside -- never overwriting or removing
# -- the original `candidates`/`resolutions` the automatic pipeline already observed. A later reader can
# always distinguish "Callosum's own scoring rejected this" from "the user confirmed it anyway".


def _load_evidence(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("evidence_json")
    if raw:
        try:
            evidence = json.loads(raw)
        except json.JSONDecodeError:
            evidence = {}
    else:
        evidence = {}
    evidence.setdefault("schema_version", SIDECAR_SCHEMA_VERSION)
    evidence.setdefault("candidates", [])
    evidence.setdefault("title_candidates", [])
    evidence.setdefault("resolutions", [])
    evidence.setdefault("decision", "")
    evidence.setdefault("decision_reason", "")
    evidence.setdefault("user_actions", [])
    return evidence


def _append_user_action(evidence: dict[str, Any], *, action: str, doi: str | None, disposition: str) -> str:
    """Append one user-decision record and re-serialize. Never mutates any existing entry."""
    evidence = dict(evidence)
    user_actions = list(evidence.get("user_actions") or [])
    user_actions.append(
        {
            "action": action,
            "doi": doi,
            "disposition": disposition,
            "at": datetime.now(timezone.utc).isoformat(),
        }
    )
    evidence["user_actions"] = user_actions
    return json.dumps(evidence)


def explain_evidence(evidence: dict[str, Any]) -> str:
    """A short, human evidence sentence for the review card -- never a raw score.

    Derived purely from what the automatic pipeline already observed/recorded; this function makes no
    new inference of its own.
    """
    resolutions = evidence.get("resolutions") or []
    candidates = evidence.get("candidates") or []
    strong = [r for r in resolutions if r.get("disposition") == "strong"]
    if len(strong) >= 2:
        return "Multiple plausible DOI candidates found."
    insufficient = [r for r in resolutions if r.get("disposition") == "insufficient_corroboration"]
    if insufficient:
        return "DOI found, but the PDF title did not corroborate the resolved work."
    if len(strong) == 1:
        return "DOI found in the PDF front matter; the resolved title closely matches the PDF's own title."
    front_matter = [c for c in candidates if c.get("position_class") == "front_matter"]
    if front_matter:
        return "DOI found in the PDF front matter, but it could not be resolved to a scholarly record."
    references_only = candidates and all(c.get("position_class") == "references" for c in candidates)
    if references_only:
        return "A DOI was found only in the References section, so it was not treated as this document's own identity."
    return "No DOI-shaped text was found in this PDF's first pages."


def best_candidate(evidence: dict[str, Any]) -> dict[str, Any] | None:
    """The single most useful DOI/title/evidence pairing to show on a review card, or None."""
    resolutions = evidence.get("resolutions") or []
    for wanted in ("strong", "insufficient_corroboration"):
        for r in resolutions:
            if r.get("disposition") == wanted:
                return {
                    "doi": r.get("doi"),
                    "title": r.get("resolved_title"),
                    "disposition": r.get("disposition"),
                }
    return None


def preview_doi(conn: Connection, raw_doi: str, crossref_client: Any) -> dict[str, Any]:
    """Read-only: normalize -> check for an existing Library match -> Crossref-resolve. NEVER calls
    `add_paper_by_doi` (which can create), so this genuinely mutates nothing -- callable freely before
    the user commits to a confirmation."""
    doi = normalize_doi(raw_doi)
    if doi is None:
        return {"status": "invalid", "error": "That does not look like a valid DOI."}
    existing = find_existing_paper_by_identity(conn, doi=doi)
    if existing is not None:
        row = existing[1]
        return {"status": "existing", "doi": doi, "paper_id": int(row["id"]), "title": row["title"]}
    resolution = crossref_client.resolve_doi(conn, doi) if crossref_client is not None else None
    if resolution is None or not resolution.resolved or not resolution.csl_json:
        error = resolution.error if resolution is not None else "no metadata provider configured"
        return {"status": "unresolved", "doi": doi, "error": error}
    csl = resolution.csl_json
    year = None
    date_parts = (csl.get("issued") or {}).get("date-parts")
    if isinstance(date_parts, list) and date_parts and isinstance(date_parts[0], list) and date_parts[0]:
        year = date_parts[0][0]
    authors = []
    for author in csl.get("author") or []:
        if not isinstance(author, dict):
            continue
        literal = author.get("literal")
        if literal:
            authors.append(literal)
        else:
            name = " ".join(part for part in (author.get("given"), author.get("family")) if part)
            if name:
                authors.append(name)
    return {"status": "resolved", "doi": doi, "title": csl.get("title"), "year": year, "authors": authors}


def confirm_identity(
    engine: Engine,
    artifact_id: str,
    *,
    doi: str,
    source: str,
    library_root: Path,
    crossref_client: Any,
    vector_store: Any,
    embedding_model: Any,
) -> ProvisionalIngestResult | None:
    """The user explicitly confirmed (or manually supplied) an identity for a queued artifact.

    Uses the SAME `add_paper_by_doi` / `attempt_attach_to_paper` machinery as the automatic pipeline --
    there is no review-specific Paper-creation shortcut. Returns None if the artifact does not exist or
    is already `promoted` (nothing left to confirm).
    """
    with engine.connect() as conn:
        row = provisional_artifacts_repo.get(conn, artifact_id)
    if row is None or row["promotion_state"] == "promoted":
        return None

    evidence_dict = _load_evidence(row)
    action = "user_confirmed_candidate" if source == "candidate" else "user_entered_doi"
    evidence_json = _append_user_action(evidence_dict, action=action, doi=doi, disposition="pending_admission")

    def _persist_action(conn: Connection) -> None:
        provisional_artifacts_repo.update_resolution(
            conn,
            artifact_id,
            identity_state=row["identity_state"],
            promotion_state=row["promotion_state"],
            resolved_paper_id=row["resolved_paper_id"],
            evidence_json=evidence_json,
        )

    run_write(engine, _persist_action)

    normalized = normalize_doi(doi)
    if normalized is None:
        return ProvisionalIngestResult(
            artifact_id=artifact_id,
            identity_state=str(row["identity_state"]),
            promotion_state=str(row["promotion_state"]),
            resolved_paper_id=row["resolved_paper_id"],
        )

    status, paper_id, created = run_write(
        engine, lambda conn: _resolve_and_admit_doi(conn, normalized, crossref_client)
    )
    evidence = _Evidence()
    evidence.candidates = evidence_dict["candidates"]
    evidence.title_candidates = evidence_dict["title_candidates"]
    evidence.resolutions = evidence_dict["resolutions"]
    if status != "ok" or paper_id is None:
        evidence.decision = "queued"
        evidence.decision_reason = f"user-supplied DOI {normalized!r} did not resolve"
        result = _finish_unresolved(engine, artifact_id, library_root, evidence)
        _reattach_user_actions(engine, artifact_id, evidence_json)
        return result

    pdf_path = Path(str(row["pdf_path"]))
    evidence.decision = "promotion_attempted"
    evidence.decision_reason = f"user-confirmed candidate: {normalized}"
    result = attempt_attach_to_paper(
        engine,
        artifact_id=artifact_id,
        pdf_path=pdf_path,
        library_root=library_root,
        paper_id=paper_id,
        created=created,
        vector_store=vector_store,
        embedding_model=embedding_model,
        evidence=evidence,
    )
    # attempt_attach_to_paper's own update_resolution calls overwrite evidence_json with `evidence`'s
    # serialization (candidates/resolutions preserved above) -- but that would DROP the user_actions
    # entry just persisted. Re-append it so the confirmation is never lost from the final record.
    _reattach_user_actions(engine, artifact_id, evidence_json)
    return result


def retry_promotion(
    engine: Engine,
    artifact_id: str,
    *,
    library_root: Path,
    vector_store: Any,
    embedding_model: Any,
) -> ProvisionalIngestResult | None:
    """Re-attempt attachment against an ALREADY-resolved paper (attachment_conflict / processing_failed /
    indexing_unavailable). Returns None if the artifact doesn't exist, is already promoted, or has no
    resolved_paper_id to retry against (identity was never resolved -- nothing to retry)."""
    with engine.connect() as conn:
        row = provisional_artifacts_repo.get(conn, artifact_id)
    if row is None or row["promotion_state"] == "promoted":
        return None
    if row["identity_state"] != "resolved" or row["resolved_paper_id"] is None:
        return None

    evidence_dict = _load_evidence(row)
    evidence_json = _append_user_action(
        evidence_dict, action="retry_attempted", doi=None, disposition=row["promotion_state"]
    )
    _reattach_user_actions(engine, artifact_id, evidence_json)

    evidence = _Evidence()
    evidence.candidates = evidence_dict["candidates"]
    evidence.title_candidates = evidence_dict["title_candidates"]
    evidence.resolutions = evidence_dict["resolutions"]
    evidence.decision = "retry_attempted"
    evidence.decision_reason = "user-initiated retry"

    pdf_path = Path(str(row["pdf_path"]))
    result = attempt_attach_to_paper(
        engine,
        artifact_id=artifact_id,
        pdf_path=pdf_path,
        library_root=library_root,
        paper_id=int(row["resolved_paper_id"]),
        created=False,
        vector_store=vector_store,
        embedding_model=embedding_model,
        evidence=evidence,
    )
    _reattach_user_actions(engine, artifact_id, evidence_json)
    return result


def _reattach_user_actions(engine: Engine, artifact_id: str, evidence_json_with_actions: str) -> None:
    """`attempt_attach_to_paper`'s own `update_resolution` calls overwrite `evidence_json` with a freshly
    serialized `_Evidence` that has no `user_actions` -- merge the just-recorded user action(s) back in
    so a confirm/retry is never silently dropped from the durable record."""

    def _merge(conn: Connection) -> None:
        row = provisional_artifacts_repo.get(conn, artifact_id)
        if row is None:
            return
        current = json.loads(row["evidence_json"]) if row["evidence_json"] else {}
        recorded = json.loads(evidence_json_with_actions)
        current["user_actions"] = recorded.get("user_actions", [])
        provisional_artifacts_repo.update_resolution(
            conn,
            artifact_id,
            identity_state=row["identity_state"],
            promotion_state=row["promotion_state"],
            resolved_paper_id=row["resolved_paper_id"],
            evidence_json=json.dumps(current),
        )

    run_write(engine, _merge)


# --- startup recovery -------------------------------------------------------------------------------


def recover_at_startup(engine: Engine, library_root: Path) -> None:
    """Reconcile `_Import Queue/*.pdf` against `provisional_artifacts`. Called once at backend
    startup. Never deletes a real, unrecoverable user artifact -- see the plan's enumerated crash
    windows. A file with no matching row is ADOPTED (using the sidecar if present, else an honest
    "context unrecoverable" record), never discarded, unless its content hash proves it is a
    redundant physical copy of bytes already tracked under a different artifact_id."""
    directory = queue_dir(library_root)
    if not directory.is_dir():
        return

    with engine.connect() as conn:
        known_ids = provisional_artifacts_repo.all_ids(conn)
        known_hashes = {
            str(row["content_hash"]): str(row["id"])
            for row in (provisional_artifacts_repo.get(conn, i) for i in known_ids)
            if row is not None
        }

    for pdf_file in sorted(directory.glob("*.pdf")):
        artifact_id = pdf_file.stem
        if artifact_id in known_ids:
            continue  # legitimate: row exists, inference may simply not have run yet -- left as-is

        try:
            data = pdf_file.read_bytes()
        except OSError:
            continue
        content_hash = sha256(data).hexdigest()

        if content_hash in known_hashes:
            # A redundant physical copy of bytes already tracked under a different artifact_id --
            # nothing is lost by removing the duplicate file itself.
            pdf_file.unlink(missing_ok=True)
            continue

        sidecar = sidecar_path(library_root, artifact_id)
        first_event = None
        if sidecar.is_file():
            try:
                payload = json.loads(sidecar.read_text(encoding="utf-8"))
                first_event = payload.get("first_capture_event")
            except (OSError, json.JSONDecodeError):
                first_event = None

        def _adopt(
            conn: Connection,
            artifact_id=artifact_id,
            content_hash=content_hash,
            pdf_file=pdf_file,
            first_event=first_event,
        ) -> None:
            provisional_artifacts_repo.create(
                conn,
                artifact_id=artifact_id,
                content_hash=content_hash,
                pdf_path=str(pdf_file),
                provenance_sidecar_state="ok" if first_event else "pending",
            )
            capture_events_repo.create(
                conn,
                capture_event_id=(first_event or {}).get("capture_event_id") or uuid4().hex,
                artifact_id=artifact_id,
                source_url=(first_event or {}).get("source_url"),
                captured_at_client=(first_event or {}).get("captured_at_client"),
                original_filename=(first_event or {}).get("original_filename"),
                producer_kind=(first_event or {}).get("producer_kind"),
            )

        run_write(engine, _adopt)


# --- permanent deletion -------------------------------------------------------------------------------


def permanently_delete_provisional_artifact(engine: Engine, artifact_id: str, library_root: Path) -> bool:
    """Delete the queue PDF (if not already promoted-and-moved-out), the sidecar, and the DB rows
    (cascading to capture_events). Never time-based -- only explicit user action reaches this."""
    with engine.connect() as conn:
        row = provisional_artifacts_repo.get(conn, artifact_id)
    if row is None:
        return False

    pdf_path = Path(str(row["pdf_path"]))
    if pdf_path.is_file() and pdf_path.parent == queue_dir(library_root):
        pdf_path.unlink(missing_ok=True)
    sidecar_path(library_root, artifact_id).unlink(missing_ok=True)

    def _delete(conn: Connection) -> bool:
        return provisional_artifacts_repo.delete_artifact(conn, artifact_id)

    return run_write(engine, _delete)
