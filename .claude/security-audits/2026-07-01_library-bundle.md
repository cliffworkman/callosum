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

---

## Addendum — B2 SP2: syntheses in the bundle (relayed, not re-verified; inc 235)

**Date:** 2026-07-01. **Change:** syntheses now travel in a bundle and import as **relayed display artifacts**.
Files: `metadata/library_bundle.py` (`_synthesis_entries` export + `_import_syntheses` import), `summaries.py`
(the read branch + Optional citation ids + `imported` flags), migration **0032** (`summaries.imported_json`, nullable
JSON, guarded), `20_synthesis.jsx` (the imported banner + region handling) + the modal copy.

**Audit-gate triggers:** a request/response schema change (#1 — `SummarizeJobResponse.imported`, `SummaryListItem.imported`,
Optional citation ids) + a schema change (the additive migration). **NOT triggered:** no new endpoint (rides the SP1
bundle endpoints + the existing `/summaries*`), no new external fetch, no new dependency.

### Threat review (delta vs. SP1)

- **The honesty gate (invariants #1/#4) — the load-bearing control.** A synthesis's statuses were computed against the
  *sender's* chunks. An imported synthesis is stored as a **self-contained display blob** (`summaries.imported_json`,
  `status="imported"`) — **never** in `summary_sentences` / `citation_mappings` / `evidence_quotes`, so it can't be
  read as, or mistaken for, a locally-verified synthesis. `_persisted_summary_response` branches on `imported_json`
  and returns `imported=True`; the frontend shows the **"the sender's assessment, not re-checked in your library"**
  banner. It is never re-verified locally (re-verify is deferred SP3). Provenance stays clean: only **native**
  syntheses (`imported_json IS NULL`) are exported — a bundle never re-relays a relayed artifact.
- **Coordinate honesty (#2).** Every imported citation is **region precision** (`coordinate_precision="region"`),
  never a fabricated exact box (the sender's bbox is for the sender's PDF and is not carried). Save-as-highlight
  (exact-only) is inert for imported citations (`paper_id`/coordinate gating already excludes them).
- **Evidence always shown (#4).** Each imported citation carries its quote + page + the sender's status. A citation
  whose source paper the recipient lacks shows the quote + "Source not in your library" (no Open link) — evidence
  stays visible; silence is not a certificate.
- **No egress, no PDFs.** Unchanged from SP1 — a local file, no network call, no PDF bytes.
- **SQL / injection (rule #3).** All synthesis reads/writes are SQLAlchemy Core bound parameters
  (`_synthesis_entries` joins; the single `insert(summaries)` on import). No user/bundle value reaches SQL text.
- **Input validation + resource caps (rule #4).** `MAX_BUNDLE_SYNTHESES = 2000`, `MAX_SYNTHESIS_SENTENCES = 400`,
  `MAX_CITATIONS_PER_SENTENCE = 50`; each synthesis imports in a `begin_nested()` savepoint (a bad one is skipped,
  never fatal); confidences coerced via a safe `_f`; malformed shapes skipped. Import is **idempotent** (dedup by
  content among imported summaries). The migration is additive + guarded + no-op-downgrade (the 0031 pattern).
- **Output encoding.** Blob strings (sentence text, quotes, titles) render through React as text (auto-escaped).

### Negative-path checks (`tests/test_library_bundle.py` synthesis tests, hermetic)

- Export carries the sentence + citation quote/status + **source-by-identity**; native only (a relayed synthesis is
  never re-exported). ✔
- Import stores a `status="imported"` row with a display blob (not in the verification tables); `GET /summaries/{id}`
  returns `imported: true` + **region**-precision citations; `GET /summaries` flags it. ✔
- Re-import is idempotent (dedup by content → one imported summary). ✔
- A citation whose source paper isn't present → `paper_id: null`, the quote still carried. ✔
- Selection export carries a fully-contained papers-scope synthesis, excludes an out-of-selection one. ✔

**Security Audit: PASS (addendum).** The honest structural separation (a relayed display blob, region precision, never
in the verification tables, clearly flagged) upholds invariants #1/#2/#4; additive/guarded migration; bound-param SQL;
bounded + fail-closed; no egress, no PDFs, no new dependency, no new endpoint. Re-audit if imported syntheses ever
become locally re-verifiable (SP3) or gain exact coordinates.
