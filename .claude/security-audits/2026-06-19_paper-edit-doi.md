# Security audit — Editable paper metadata + DOI re-resolve (increment 49)

**Date:** 2026-06-19
**Feature:** A Mendeley-style editable Details pane. New mutating endpoint `PATCH /papers/{id}`
(edit a paper's bibliographic record) and `POST /papers/{id}/re-resolve` (re-run Crossref
enrichment against the paper's DOI). Files touched: `app/backend/api/routers/papers.py`,
`app/backend/metadata/paper_edits.py` (new), `app/backend/metadata/enrichment.py`,
`app/backend/api/app.py`, frontend `25_detail.jsx`.

**Audit triggers:** (1) new API endpoints + a request-schema; (2) a feature spanning 3+ files;
(3) an external fetch path (Crossref). No new file-write path; no new dependency; no auth change.

## Threat review

### Input validation (rule #4 — validate untrusted input at the boundary)
- `PaperUpdateRequest` is fully typed + bounded: every text field has a `max_length` (title 2000,
  abstract 100k, identifiers/scalars 100–2000, doi 255 = the column width); year/month/day are
  ranged ints (`ge`/`le`); authors is a capped list. Pydantic rejects type/range violations → 422.
- Per-field normalisation in `_edits_from_request`: strings stripped, ""→None (clear); an empty
  title is rejected 422 (the one required column). Only fields in `model_fields_set` are applied
  (partial update; omit ≠ clear).
- **Generic "More" passthrough** (`csl` dict — the one place arbitrary keys arrive): bounded by
  `_validate_csl_patch` — ≤60 keys, key matches `^[A-Za-z][A-Za-z0-9_-]*$` and ≤64 chars, value is
  a string ≤4000 chars or null. **Reserved CSL keys are rejected (422)** so the generic path can
  never overwrite the structured/typed fields (author/issued/title/DOI/…); `build_paper_update`
  *also* skips reserved keys defensively (belt-and-suspenders).
- `build_paper_update` is a pure function: it copies the existing `csl_json` and merges only the
  changed keys (no blind re-projection → no accidental wipe of untouched fields); DOI normalised
  (strip+lower); authors stored as CSL `{literal}` (no fragile parsing).

### SQL injection (rule #3)
- All writes go through `update_paper_metadata` → SQLAlchemy Core `update().values(**kw)` with
  bound parameters. `csl_json` is a JSON column (serialised, not interpolated). Generic-patch keys
  become **dict keys inside the JSON value**, never SQL identifiers. No string-built SQL.

### Injection / output encoding
- The abstract is edited as plain text in a `<textarea>` (value-bound, not `dangerouslySetInnerHTML`).
  The read-only `abstract_display` allowlisted-HTML path is unchanged and unused by the editor.
- Metadata values render as React text / input values (auto-escaped). The generic "More" labels are
  humanised key strings, not raw HTML.

### SSRF / external calls (Crossref)
- Re-resolve calls the existing `CrossrefClient` → `https://api.crossref.org/works/{doi}` only; the
  URL host is a hardcoded constant, the DOI is URL-encoded (`quote(doi, safe="")`). The client never
  follows a user-supplied URL. httpx has a 10s timeout (existing). Failure/timeout is caught by the
  resolver and returned as `status="unresolved"` (the endpoint answers 200, never 500).

### Data egress (invariant #3)
- Re-resolve sends **only the DOI** to a public metadata API — exactly what library *import* already
  does. **No library text leaves the machine**, so this is NOT the Gemini library-text egress gate
  and is correctly not behind `CALLOSUM_ALLOW_DATA_EGRESS`. (The Gemini gate remains the only path
  that can send paper content off-machine; untouched here.) Offline → graceful "unresolved".
- A hand-edit marks `imported_source="user-edited"`, which is deliberately NOT in
  `_can_update_from_crossref`'s allowlist → the **batch** library enrich will not silently clobber a
  user's edits. The explicit per-paper re-resolve passes `force=True` (the user asked for it).

### Resource caps / DoS (the local single-user threat model)
- Every field is length/count-capped (above). The generic patch is bounded (≤60 keys × ≤4000 chars).
  No unbounded growth path. Crossref responses are cached (`external_api_cache`), so repeated
  re-resolves of the same DOI don't re-hit the network.

### File-path safety
- No new file path is built or served. The Files list opens a paper's existing primary PDF via the
  unchanged, DB-row-only `/papers/{id}/pdf` route. No client-supplied path is ever followed.

### DOI uniqueness
- `papers.doi` has a UNIQUE constraint. Editing a DOI to one already on another paper raises
  `IntegrityError`, caught → **409** (rollback first); no 500, no partial write.

### Secrets / supply chain
- No secret handling; `CALLOSUM_CROSSREF_MAILTO` (optional, non-secret) unchanged. No new dependency.

## Negative-path checks (run)
- Empty title → **422**; no fields → **422**; reserved key in `csl` → **422**;
  unknown paper → **404**; duplicate DOI → **409** (`tests/test_papers.py`).
- Re-resolve with no DOI → **422**; Crossref non-200 → `crossref-unresolved`, **200** (graceful);
  force overrides a prior user-edit (`tests/test_papers.py`).
- Pure-function mapping (date trailing-None, clear-drops-issued, authors→literal, reserved-key skip,
  untouched-csl preserved) — `tests/test_paper_edits.py`. Full suite: **172 passing**.
- Live E2E (fake Crossref, no network): inline edit auto-saves (prov→user-edited), re-resolve fills
  metadata (prov→crossref), 0 console errors.

## Result
**Security Audit: PASS.** Bounded/validated partial input; parameterised JSON writes; external fetch
limited to a hardcoded host with only the DOI leaving (consistent with import, not the egress gate);
DOI-uniqueness handled as 409; graceful offline; user-edits protected from batch clobber; no new
file-write path, secret, or dependency.
