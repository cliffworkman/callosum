"""Manual review actions for the Import Queue (#61): explain, preview, confirm, retry (#96 lineage).

Split out of ``provisional.py`` (rule #1, 600-line cap). An explicit user decision is recorded as a NEW entry in
`evidence_json["user_actions"]`, appended alongside -- never overwriting -- the candidates and resolutions the
automatic pipeline observed.

Seam policy: this module reaches the core module's functions THROUGH the module (`provisional.attempt_attach_to_paper`,
never `from ... import`), so a test or caller that replaces one on `app.backend.capture.provisional` still affects the
review path exactly as it did when everything lived in one file. The core module never imports this one (it would be
circular); it exposes these names lazily for backwards-compatible imports.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import Connection, Engine

from app.backend.capture import provisional
from app.backend.capture.owned_artifacts import resolve_owned_queue_artifact_id
from app.backend.capture.provisional_evidence import SIDECAR_SCHEMA_VERSION, _Evidence
from app.backend.metadata.doi import normalize_doi
from app.backend.persistence import provisional_artifacts_repo
from app.backend.persistence.repository import find_existing_paper_by_identity
from app.backend.persistence.sqlite_retry import run_write

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
) -> provisional.ProvisionalIngestResult | None:
    """The user explicitly confirmed (or manually supplied) an identity for a queued artifact.

    Uses the SAME `add_paper_by_doi` / `attempt_attach_to_paper` machinery as the automatic pipeline --
    there is no review-specific Paper-creation shortcut. Returns None if the artifact does not exist or
    is already `promoted` (nothing left to confirm).

    `artifact_id` is the caller's CLAIM. It is resolved once against the server-owned active queue IDs
    (`owned_artifacts`); everything after that -- DB updates, the queue file, the staged copy, the sidecar -- uses the
    resolved owned ID, never the claim.
    """
    with engine.connect() as conn:
        owned_id = resolve_owned_queue_artifact_id(conn, artifact_id)
        row = provisional_artifacts_repo.get(conn, owned_id) if owned_id is not None else None
    if owned_id is None or row is None or row["promotion_state"] == "promoted":
        return None

    evidence_dict = _load_evidence(row)
    action = "user_confirmed_candidate" if source == "candidate" else "user_entered_doi"
    evidence_json = _append_user_action(evidence_dict, action=action, doi=doi, disposition="pending_admission")

    def _persist_action(conn: Connection) -> None:
        provisional_artifacts_repo.update_resolution(
            conn,
            owned_id,
            identity_state=row["identity_state"],
            promotion_state=row["promotion_state"],
            resolved_paper_id=row["resolved_paper_id"],
            evidence_json=evidence_json,
        )

    run_write(engine, _persist_action)

    normalized = normalize_doi(doi)
    if normalized is None:
        return provisional.ProvisionalIngestResult(
            artifact_id=owned_id,
            identity_state=str(row["identity_state"]),
            promotion_state=str(row["promotion_state"]),
            resolved_paper_id=row["resolved_paper_id"],
        )

    status, paper_id, created = run_write(
        engine, lambda conn: provisional._resolve_and_admit_doi(conn, normalized, crossref_client)
    )
    evidence = _Evidence()
    evidence.candidates = evidence_dict["candidates"]
    evidence.title_candidates = evidence_dict["title_candidates"]
    evidence.resolutions = evidence_dict["resolutions"]
    if status != "ok" or paper_id is None:
        evidence.decision = "queued"
        evidence.decision_reason = f"user-supplied DOI {normalized!r} did not resolve"
        result = provisional._finish_unresolved(engine, owned_id, library_root, evidence)
        _reattach_user_actions(engine, owned_id, evidence_json)
        return result

    evidence.decision = "promotion_attempted"
    evidence.decision_reason = f"user-confirmed candidate: {normalized}"
    result = provisional.attempt_attach_to_paper(
        engine,
        artifact_id=owned_id,
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
    _reattach_user_actions(engine, owned_id, evidence_json)
    return result


def retry_promotion(
    engine: Engine,
    artifact_id: str,
    *,
    library_root: Path,
    vector_store: Any,
    embedding_model: Any,
) -> provisional.ProvisionalIngestResult | None:
    """Re-attempt attachment against an ALREADY-resolved paper (attachment_conflict / processing_failed /
    indexing_unavailable). Returns None if the artifact doesn't exist, is already promoted, or has no
    resolved_paper_id to retry against (identity was never resolved -- nothing to retry).

    `artifact_id` is the caller's CLAIM, resolved once to a server-owned active queue ID; only that owned ID is used after."""
    with engine.connect() as conn:
        owned_id = resolve_owned_queue_artifact_id(conn, artifact_id)
        row = provisional_artifacts_repo.get(conn, owned_id) if owned_id is not None else None
    if owned_id is None or row is None or row["promotion_state"] == "promoted":
        return None
    if row["identity_state"] != "resolved" or row["resolved_paper_id"] is None:
        return None

    evidence_dict = _load_evidence(row)
    evidence_json = _append_user_action(
        evidence_dict, action="retry_attempted", doi=None, disposition=row["promotion_state"]
    )
    _reattach_user_actions(engine, owned_id, evidence_json)

    evidence = _Evidence()
    evidence.candidates = evidence_dict["candidates"]
    evidence.title_candidates = evidence_dict["title_candidates"]
    evidence.resolutions = evidence_dict["resolutions"]
    evidence.decision = "retry_attempted"
    evidence.decision_reason = "user-initiated retry"

    result = provisional.attempt_attach_to_paper(
        engine,
        artifact_id=owned_id,
        library_root=library_root,
        paper_id=int(row["resolved_paper_id"]),
        created=False,
        vector_store=vector_store,
        embedding_model=embedding_model,
        evidence=evidence,
    )
    _reattach_user_actions(engine, owned_id, evidence_json)
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
