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
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from sqlalchemy import Connection, Engine

from app.backend.capture.admission import CAPTURE_SOURCE, attachment_decision
from app.backend.capture.provisional_evidence import (
    SIDECAR_SCHEMA_VERSION,
    _Evidence,
    _extract_candidates,
    _resolve_and_score,
)
from app.backend.metadata.doi_add import add_paper_by_doi
from app.backend.pdf_processing.ingest import attach_pdf_to_paper
from app.backend.persistence import capture_events_repo, provisional_artifacts_repo
from app.backend.persistence.sqlite_retry import run_write

QUEUE_DIR_NAME = "_Import Queue"
PROVENANCE_DIR_NAME = ".provenance"
PROVENANCE_ARTIFACTS_SUBDIR = "artifacts"

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


# --- backwards-compatible access to names that moved out of this module --------------------------------------
#
# `provisional_review` and `provisional_recovery` import THIS module (they reach its functions through it), so it cannot
# import them at the top without a cycle. These public names are therefore resolved lazily, so existing
# `from app.backend.capture.provisional import best_candidate`-style imports keep working. They are read-only aliases:
# to replace one in a test, patch it on the module that defines it.
_MOVED_PUBLIC_API = {
    "best_candidate": "app.backend.capture.provisional_review",
    "confirm_identity": "app.backend.capture.provisional_review",
    "explain_evidence": "app.backend.capture.provisional_review",
    "preview_doi": "app.backend.capture.provisional_review",
    "retry_promotion": "app.backend.capture.provisional_review",
    "permanently_delete_provisional_artifact": "app.backend.capture.provisional_recovery",
    "recover_at_startup": "app.backend.capture.provisional_recovery",
}


def __getattr__(name: str) -> Any:
    module_name = _MOVED_PUBLIC_API.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    return getattr(importlib.import_module(module_name), name)
