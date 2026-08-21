# Security audit — native Zotero library import (backlog #57 Phase 1, inc 484)

**Date:** 2026-08-20
**Feature:** a shipped entry point (Library "+ Add" → "Read Zotero library…" + a third onboarding-wizard option)
for the already-built, full-fidelity Zotero importer (`app/backend/importers/zotero.py`,
`integrations/zotero/adapter.py`) — previously reachable only from the dev validation harness and tests. **Gate
trigger:** a new API endpoint (`POST /library/zotero/import` + its poll route) + a net-new feature spanning 3+
files (12 touched across the whole plan).

## Surface added

- `app/backend/api/routers/library_zotero.py` (new, 150 lines) — `POST /library/zotero/import {zotero_data_dir}`
  (async job, `zotero_import_jobs` `JobStore`) + `GET /library/zotero/import/{job_id}` (poll). Post-processing
  embeds/retraction-checks newly created papers and embeds newly created chunks on matched papers too.
- `app/backend/importers/zotero.py` — two small additive fields on `ZoteroImportResult`
  (`created_paper_ids`/`chunk_ids_by_paper`) so the router's caller can drive the above without re-deriving it.
- `app/backend/api/app.py` / `routers/status.py` — `zotero_import_jobs` registered on `api.state`, `JOB_LABELS`,
  `JOB_NAV_DEFAULTS` (`{"workspace": "library", "modal": "zotero-import"}`), `JOB_COMPUTE_KINDS` ("Local AI",
  matching `library_import_jobs`'s own label — the local embedding model, not an LLM).
- Frontend: `27b_zotero_import.jsx` (new) — `ZoteroImportModal`/`ZoteroImportModalBody`, mirroring
  `27_scan.jsx`'s exact resume-on-remount `localStorage` poll lifecycle. Wired into the Library "+ Add" menu
  (`10b_libmenus.jsx`) and the onboarding wizard's import-choice step (`04e_onboarding.jsx`).

Not a security property, but for completeness across this branch's artifact set: a known, disclosed limitation
carries over unchanged — imported annotation *positions* stay in raw Zotero-reader-JSON form
(`integrations/zotero/README.md`), so imported highlights show their quoted text/comment but can't be
jumped-to or drawn on the PDF yet (backlog #57 Phase 4). This is a pre-existing gap unrelated to this branch's
threat surface, not fixed by it.

## Threat review

**File-path safety.** Identical posture to the already-audited `POST /library/scan`
(`.claude/security-audits/2026-06-21_library-scan.md`): local-only, no auth, the server *is* the user's
machine, so reading a directory the user typed is the intended behavior, not a traversal/SSRF vuln — there is
no untrusted remote caller. This endpoint is guarded *more tightly* than scan, not less:

- `ZoteroImportRequest.zotero_data_dir` is length-capped (`_ZOTERO_DIR_MAX_LEN = 4096`, rule #4's boundary-cap
  discipline) before it ever reaches the filesystem.
- The router's own pre-check (`data_dir.is_dir()`) rejects anything that isn't an existing directory with a
  clean 422, before a background job is even created.
- `read_zotero_library_copy` (`integrations/zotero/adapter.py`) can only ever open **one specifically-named
  file** inside that directory — `zotero_data_dir / "zotero.sqlite"` — never an arbitrary path the request
  could otherwise influence. There is no filename-from-request-data path here at all (unlike, say, an
  upload-and-name-a-file flow); the only user-supplied value is the *directory*, and the filename it's joined
  with is a hardcoded literal.
- That file is opened **read-only, off a copy, never the live database**: `shutil.copy2(source_db, copied_db)`
  into a `tempfile.TemporaryDirectory` (auto-cleaned on context exit), then
  `sqlite3.connect(f"file:{copied_db.as_posix()}?mode=ro", uri=True)` — a URI-mode read-only connection to the
  *copy*, not the source. Callosum never writes to, locks, or even opens the user's live Zotero database, so
  running this while Zotero itself is open (a real usage pattern the modal's own copy calls out) is safe.
  `tests/test_zotero_importer.py::test_zotero_importer_maps_metadata_attachments_chunks_and_is_idempotent`
  proves this empirically, not just by code inspection: it snapshots `file_sha256(source_db)` and a full
  `_tree_hashes(zotero_dir)` (every file under the Zotero directory, hashed) before two successive import runs,
  then asserts both are byte-identical afterward — the whole Zotero data directory, not just the one database
  file, is provably untouched.
- PDF **attachments** (the other files this feature reads) are resolved from `itemAttachments.path` entries the
  copied database itself names (`storage/{key}/{filename}` for imported files, or an absolute linked-file path)
  — read-only via the existing, already-audited `extract_pdf`/`file_sha256` pipeline. Nothing is written back
  into Zotero's `storage/` tree; callosum's own copy semantics (`storage_mode="linked"`) mean it never even
  copies the PDF bytes into its own managed store for this importer, only records the resolved path + checksum.

**Zero egress (invariant #3).** `grep -n "httpx\|requests\|urllib" app/backend/importers/zotero.py
integrations/zotero/adapter.py` → **zero matches**, confirmed live, not asserted from memory. The importer and
adapter are pure local SQLite reads + local PDF extraction; no network client is imported anywhere in either
file. The one post-processing step that *does* touch the network per created paper —
`auto_check_retractions(conn, [paper_id], checkers=app.state.retraction_checkers)` in
`library_zotero.py::_run_zotero_import_job` — is the same already-audited public-metadata retraction lookup
every other import path (`library_import_jobs`, `library_bundle_import_jobs`) already performs; it is not the
Gemini `CALLOSUM_ALLOW_DATA_EGRESS` gate, and no library/manuscript *text* leaves the machine at any point in
this feature.

**Untrusted PDF content (rule #4).** Inherits the already-audited `extract_pdf`/PyMuPDF decode-and-fail-closed
pipeline unchanged — this feature adds no new PDF-parsing code. Per-attachment failures are isolated:
`import_zotero_library`'s attachment loop wraps `_extract_attachment_chunks` in a `try/except Exception`, routes
any failure through the caller-supplied `on_attachment_error` callback, and continues the run — one corrupt or
unreadable PDF cannot abort the whole library import or leave a half-written paper. The router surfaces this as
a bounded `attachment_error_details` list (capped at `_ATTACHMENT_ERROR_DETAIL_CAP = 25`) in the job summary,
never a raw exception to the client.

**No resource cap (deliberate).** Unlike `POST /library/scan`'s per-file `MAX_SCAN_PDF_BYTES` cap, this importer
does not size-cap the Zotero SQLite copy or individual PDF attachments before reading them. This mirrors the
already-accepted posture for a **whole-library, one-shot** import (the generic BibTeX/RIS/CSL-JSON path in
`library.py` and the callosum-bundle importer are the same shape: a user pointing the local app at their own,
already-on-disk data, sized by however large their existing reference library happens to be — there is no
untrusted remote party who could inflate it). A resource cap here would functionally block a user with a large
but entirely legitimate Zotero library from importing it at all, which is a worse outcome for a local single-user
tool than a long-running but honestly-tracked job (Status popover, invariant #5, `mark_progress` per item).
`extract_pdf` itself still fails closed on a malformed/corrupt file regardless of size, so this is a scope
decision, not a missing input-validation guard.

**Dedup / idempotence.** `find_existing_paper_by_identity` (DOI, then `zotero_library_id`+`zotero_item_key`,
then title/year/first-author fallback — unmodified, the same identity resolution every import path already
uses) decides matched-vs-created per item; a second run against the same directory creates zero duplicate
papers/attachments/collections/tags/notes/annotations. Proven directly by
`tests/test_zotero_importer.py::test_zotero_importer_maps_metadata_attachments_chunks_and_is_idempotent`, which
calls `import_zotero_library` twice in the same transaction and asserts `second_result.papers_created == 0`,
`second_result.papers_matched == 3`, and exactly 3 total paper rows exist. Attachment/collection/tag/note/
annotation upserts each check-then-insert against a stable external key
(`import_source`+`external_id`/`original_path`/`role`, or a UNIQUE-constraint-backed `_insert_ignore` for the
membership join tables), so re-running never duplicates any of those either.

**Parameterized SQL, no new dependency, no schema change, no new secret.** `integrations/zotero/adapter.py`
builds every query as a literal SQL string with **no string-interpolated values** — every WHERE-clause value
that does vary (the `zotero.sqlite` path itself) is a filesystem path passed to `sqlite3.connect`, not
interpolated into SQL text; `app/backend/importers/zotero.py` uses SQLAlchemy Core bound parameters throughout
(rule #3). `git diff` against the fork point for `alembic/`, `pyproject.toml`, `requirements.txt`, and
`requirements-dev.txt` is empty — this feature ships with zero schema migrations and zero new third-party
dependencies. No secret, API key, or credential is involved anywhere in this surface.

## Negative-path checks (recorded)

- **Nonexistent directory → 422.** `tests/test_library_zotero_import.py::test_zotero_import_endpoint_nonexistent_directory_422`
  posts a path under `tmp_path` that was never created; the router's `is_dir()` pre-check rejects it before a
  job is even created. ✓
- **A directory with no `zotero.sqlite` → honest job error, no raw traceback.**
  `tests/test_library_zotero_import.py::test_zotero_import_endpoint_missing_zotero_sqlite` posts a real,
  existing, empty directory (passes the router's `is_dir()` check, so a job starts) and asserts the job ends
  `status == "error"` with `"zotero.sqlite"` named plainly in the detail and, explicitly, `"Traceback" not in
  result["detail"]` — the router's `except FileNotFoundError` branch turns the adapter's own
  `FileNotFoundError(f"Zotero database not found: {source_db}")` into a friendly message rather than letting a
  raw Python traceback reach the client. ✓
- **An empty-but-valid Zotero profile → a clean zero-count "done."**
  `tests/test_library_zotero_import.py::test_zotero_import_endpoint_empty_library` builds a real Zotero schema
  (`_create_zotero_schema`) with zero rows and asserts the job finishes `status == "done"` with every summary
  field at `0` and an empty `attachment_error_details` list — an empty library is a legitimate, successfully
  completed run, not an error. ✓
- **A fabricated job id → 404, not a crash.**
  `tests/test_library_zotero_import.py::test_zotero_import_status_404_for_unknown_job` confirms
  `GET /library/zotero/import/does-not-exist` returns 404. ✓
- **Copy-then-read, proven empirically.**
  `tests/test_zotero_importer.py::test_zotero_importer_maps_metadata_attachments_chunks_and_is_idempotent`'s
  `file_sha256(source_db) == source_checksum_before` + whole-tree `_tree_hashes(zotero_dir) == source_tree_before`
  assertions (see Threat review above). ✓
- **One bad attachment doesn't abort the run.** Covered structurally by `import_zotero_library`'s per-attachment
  `try/except` + `on_attachment_error` callback (see Threat review above) — no dedicated adversarial-PDF fixture
  was added in this task, since the underlying `extract_pdf` fail-closed behavior is already covered by its own
  existing test suite (`test_pdf_processing.py`); this task's own tests exercise the *isolation* path (a
  `missing`-availability linked file that can't be extracted at all still completes the run cleanly) rather than
  a *corrupt-file* path, which was already proven at the `extract_pdf` layer.

## Flag

**Before any hosted/public deployment**, this endpoint (like `/library/scan` and every other server-side
directory-read path) MUST be gated or removed — a remote caller could otherwise enumerate/read server files.
No new CLAUDE.md checklist entry is needed: it is covered verbatim by the existing "Before any public/
internet-facing deployment" list's `POST /library/scan` bullet, which already generalizes to "these" (the
watched-folder and library-folder auto-read paths) — this endpoint joins that same, already-tracked list.

## Result

**Security Audit: PASS.** On a local single-user app, reading a user-pointed Zotero data directory is the
intent, not a vulnerability; the endpoint is guarded more tightly than the already-audited scan endpoint (a
length cap + an `is_dir()` pre-check + a hardcoded single filename), reads the live Zotero database only via a
read-only connection to a disposable copy (proven byte-identical before/after, not just asserted), isolates
per-attachment PDF failures without aborting the run, is idempotent on re-run, ships zero new dependencies and
zero schema changes, and has zero network egress in the importer/adapter themselves (confirmed by direct grep).
The one deliberate gap — no resource cap on the Zotero database/attachment sizes — is a documented scope
decision consistent with every other whole-library import path in the app, not a missing boundary check.
