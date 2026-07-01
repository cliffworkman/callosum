# Security Audit — Portable library bundle (B2 SP1, inc 234)

**Date:** 2026-07-01
**Feature:** export/import a callosum library (or a selection) as a versioned JSON file carrying metadata + tags +
annotations + axis definitions — **NO PDFs**. Files: `app/backend/metadata/library_bundle.py` (build + import),
`app/backend/api/routers/library.py` (`POST /library/bundle/export` + `POST/GET /library/bundle/import`),
`app/backend/api/app.py` (JobStore wiring), `app/frontend/js/28b_bundle.jsx` (import modal) + `00_lib.jsx`
(`downloadBundle`) + menu/bulk-bar controls.

**Audit-gate triggers:** new API endpoints (#1) + a new file-ingestion path (#3 — the import reads a user file).
**NOT triggered:** no new external fetch (#2 — no network at all), no new dependency (#6).

## Threat review

- **No egress / no PDFs (the core promise).** A bundle is a **local file the user hands off** — export serializes DB
  rows to JSON returned to the browser; import reads the file text (POSTed in the JSON `content` string) and merges
  it. There is **no network call off-machine** at any point, and **no PDF bytes / no `attachment` file data** in the
  payload (only metadata + the user's own tags/annotations + axis definitions). This is NOT the Gemini gate and NOT
  any egress channel; it honors the acquisition / no-paywall-circumvention veto (the recipient re-acquires their own
  PDFs via the OA lane).
- **No path traversal.** The import takes the file **text in the JSON body** (`content: str`), never a server-side
  path — the browser reads the file client-side (`file.text()`). There is no filesystem read/write from request data.
  The export writes nothing to disk (a `Response` body) and the download filename is a **constant**
  (`callosum-library-bundle.json`).
- **Input validation + resource caps (rule #4).** `content` is a Pydantic `Field(min_length=1, max_length=
  MAX_BUNDLE_BYTES + slack)`; `parse_bundle` re-checks `MAX_BUNDLE_BYTES = 20 MB` and rejects a missing/unknown
  `callosum_bundle` version or a non-list `papers` (→ `BundleError` → a graceful job error, never a crash). The worker
  caps `MAX_BUNDLE_PAPERS = 20 000`, `MAX_TAGS_PER_PAPER = 200`, `MAX_ANNOTATIONS_PER_PAPER = 500`; each paper/axis
  runs in its own `begin_nested()` savepoint so a malformed record is skipped + counted, never fatal. Empty-selection
  export → 422; unknown job id → 404.
- **SQL injection (rule #3).** All reads/writes go through SQLAlchemy Core bound parameters
  (`find_existing_paper_by_identity`, `create_paper`, `tags_repo`, `annotations_repo`, the curated-axis helpers, the
  direct `select`s). No user/bundle value is interpolated into SQL text; table/column names are constants.
- **Merge is additive & non-destructive.** An existing paper (matched by identity) is the merge target — **its
  metadata is never overwritten** and its `imported_source` is not downgraded (proven by test); the bundle only *adds*
  its tags (get-or-create, idempotent link; a tag is only colored if uncolored) + annotations (deduped by page/bbox/
  note). New papers are stamped `imported_source="bundle-import"`, kept **out of** the enrich-clobber allowlist (like
  user-edited / discovery-import) so a later enrich never silently rewrites them. Re-import is idempotent.
- **Coordinate honesty (invariant #2).** An imported annotation's `attachment_id` is dropped (applied NULL — the
  per-device PDF pointer); the note + page + bboxes travel, and the overlay only draws once the recipient has the
  same PDF. No fabricated box against an absent PDF.
- **Output encoding.** Bundle strings (titles, tags, notes) are rendered by React as text (auto-escaped — no
  `dangerouslySetInnerHTML`). The export writes JSON via `json.dumps` (no HTML). `my_publications` axes are **never
  exported** (authorship, resolver-only); only `standard` + `curated` axis definitions travel.
- **Auth/egress channel.** The frontend `downloadBundle` uses a tokened `fetch` through the auth shim (carries the
  Remote-access bearer token under inc-168 Remote access; a plain `<a download>` would 401 — the inc-172 lesson).
- **Supply chain.** No new pip / JS dependency; no migration (reuses papers/tags/paper_tags/annotations/axes/
  cluster_node_papers).

## Negative-path checks (`tests/test_library_bundle.py`, hermetic — two throwaway SQLite DBs, no network/model)

- Round-trip into an empty library: papers/tags/annotations/axes land; imported papers stamped `bundle-import`. ✔
- Re-import is idempotent (no duplicate papers/annotations; `annotations_added == 0`, `axes_members_added == 0`). ✔
- Merge is non-destructive: an existing paper keeps its title + `user-edited` provenance, gains the tags + highlight. ✔
- Selection export carries only the chosen papers + **no** axes. ✔
- Curated members resolve by identity; a keyword axis imports definition-only. ✔
- Annotation `attachment_id` applied NULL. ✔
- `parse_bundle` rejects non-JSON / unknown version / no-papers / oversized. ✔
- Endpoint round-trip + 422 (empty selection) + 404 (unknown job) via TestClient. ✔

**Security Audit: PASS.** A local, PDF-less, no-egress file the user controls (honors the copyright veto);
no path traversal (text-in-body); bounded + fail-closed; bound-param SQL; additive/non-destructive merge with
`bundle-import` provenance; coordinate-honest imported annotations; no new dependency, no migration. Re-audit if PDF
bytes, syntheses, or an automatic (non-user-initiated) share channel are ever added.
