# Security Audit — Managed-file permanent delete (increment 340)

**Date:** 2026-07-22
**Trigger:** Permanent deletion now removes local files, extending an irreversible file-delete path across the
repository, API, frontend, tests, and help surface. No new endpoint, request schema, dependency, or migration.

## What changed

`DELETE /papers/{id}/permanent` and `POST /papers/trash/empty` now remove attachment files that Callosum owns.
Eligibility requires both `attachments.storage_mode == "managed"` and a resolved regular-file path contained by
the configured `CALLOSUM_LIBRARY_DIR`. Linked and URL attachments, paths outside that root, symlinks, directories,
and files still referenced by a surviving paper are preserved.

Eligible files are atomically renamed into `.callosum-delete-staging/` inside the managed root before database and
vector cleanup. A staging or purge failure rolls the database transaction back and restores every moved file. Only
after the database commit succeeds are staged files unlinked. A file-lock/staging failure returns 409 and leaves the
paper recoverable in Trash.

## Values check

This does not trigger the literature-claim Principles gate: it changes no claim, signal, evidence, provenance,
fact/candidate, or egress surface. It does touch Approach/Avoidance **A4, user ownership of irreversible acts**.
The change is **confirmed**, not an emergent value: it extends the existing explicit, trashed-only permanent-delete
flow. The easier divergent implementation would unlink every attachment path recorded in the database; that was
rejected because it could delete a Zotero or other externally linked file that Callosum does not own.

## Threat review

- **Irreversibility / authorization of intent:** unchanged two-step gate. A live paper cannot be purged; it must
  first be moved to Trash, then the user confirms Delete forever or Empty Trash. Active merge participants remain
  unpurgeable.
- **Ownership boundary:** a file must be marked `managed`; `linked` and `url` are never candidates. This prevents
  deletion of Zotero folders, watched folders, and other external user-owned paths.
- **Path containment:** paths are expanded and resolved before comparison, then must be descendants of the resolved
  managed-library root. Out-of-root paths, directories, missing paths, and symlinks are skipped. The staging path
  must resolve to itself inside the root, preventing a symlink/junction redirect.
- **Shared files:** normalized paths referenced by any non-purged paper are excluded. A shared managed file is
  removed only when its final referencing paper is purged.
- **Failure atomicity:** same-volume rename stages files first. Any normal staging/database/vector exception rolls
  back SQLite and restores already-moved files; the API exposes a 409 for staging failures rather than silently
  purging only the record.
- **Database/vector integrity:** the existing embedding/vector-before-paper ordering remains unchanged. The service
  coordinates filesystem staging around that audited repository operation.
- **Injection / input validation:** no raw SQL. IDs remain typed path integers; SQLAlchemy Core builds every query.
  Staging names use a bounded original stem plus a UUID and never use request data.
- **Egress / secrets / external calls:** none. The operation is entirely local and reads no secret.
- **Resource bounds:** one attachment-row scan and at most one rename/unlink per unique eligible path. Empty Trash is
  bounded by the local library and existing Trash set.
- **Supply chain:** no new dependency.

## Negative-path checks

- Live paper permanent-delete -> 404; no file movement. **PASS.**
- Trashed paper with managed, linked, and mislabeled out-of-root managed paths -> only the contained managed file is
  deleted. **PASS.**
- Managed path shared with a live paper -> preserved until the final referencing paper is purged. **PASS.**
- Second of two staging moves raises a simulated file-lock error -> first move is restored, API returns 409, paper
  remains in Trash, both files remain. **PASS.**
- Simulated database purge failure after staging -> transaction rolls back, managed file is restored, paper remains
  in Trash. **PASS.**
- Empty Trash -> exclusively owned managed file removed; live paper retained. **PASS.**
- Full suite -> **1388 passed, 1 skipped**. Frontend assembly -> **46 passed**. QA surface map -> **260/260 API
  surfaces covered**. Line budget -> **351/351 application files at or below 600 lines**.

## Residual

A hard process termination in the narrow interval after a managed file is staged and before normal restoration or
post-commit unlink can leave bytes in `CALLOSUM_LIBRARY_DIR/.callosum-delete-staging/`. The original filename stem is
retained in the staged name for diagnosis. This fails toward preservation rather than deleting an external file;
normal Python/SQLite errors are covered by restoration. Automatic crash-recovery reconciliation would require a
durable manifest and startup hook and is not warranted for this local, explicit operation.

**Security Audit: PASS.**
