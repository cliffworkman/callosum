<!-- qa-coverage
api: /library/bundle*
fe: 28b_bundle.jsx
-->

# ROUTE 54 - Portable library bundle (export / import)

**Tier:** 1 local-stateful
**Goal:** Exercise the file-based library bundle (metadata + tags + annotations + axis definitions, **NO PDFs**)
while preserving the load-bearing posture: a file the user hands off (**no server, no automatic egress**);
**copyright-safe** (no PDF bytes); merge on import is **additive & non-destructive** (an existing paper keeps its
own metadata and only gains the bundle's tags + annotations); and the annotation-box caveat is honest (a highlight's
box only re-renders once the recipient has the same PDF; the note + page always land).

## Environment

Clean seeded instance (`_TEMPLATE.md` → Environment). The seed should have at least one paper with a tag + a
highlight, and one curated axis, so a round-trip is meaningful. Register listeners before navigation.

## Standing assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **No egress at all (veto-level here).** A bundle export/import is a *local file* — the browser reads/writes it and
  POSTs the text to the local app. There is **no network call off-machine** and **no PDF** in the payload. ANY
  outbound request to a non-loopback host during export/import is **Critical**; a PDF/attachment in the exported JSON
  is **Critical** (copyright).
- **Additive & non-destructive merge.** Importing a bundle whose paper matches an existing one (by identity) **must
  not overwrite** the existing paper's title/metadata or downgrade its `imported_source`; it only *adds* the bundle's
  tags + annotations. Re-importing the same bundle is **idempotent** (no duplicate papers / tags / annotations / axis
  members). A silent overwrite of the recipient's metadata is **High**.
- **Coordinate honesty.** An imported annotation carries its note + page + color; its box overlay renders only when
  the same PDF is present (the bundle has no PDF). The imported annotation's `attachment_id` is NULL. A fabricated box
  against an absent PDF is **High**.
- **Relayed syntheses, not re-verified (B2 SP2 — the honesty gate).** Syntheses travel in the bundle and import as
  **relayed artifacts**: a loaded imported synthesis shows the **"Imported — the sender's assessment, not re-checked
  in your library"** banner (`.synth-imported`), its citations open at **region precision only** (never a fabricated
  exact box — the sender's bbox is for the sender's PDF), and its response carries `imported: true`. Presenting an
  imported synthesis as a locally-verified one (no banner / exact highlights / in the native verification tables) is
  **Critical** (invariants #1/#4). A citation whose source paper isn't present shows its **quote** + "Source not in
  your library" (evidence stays visible), no Open link. The history list flags imported syntheses (`imported: true`).
- **Bounded input.** Oversized / malformed / unknown-version bundle text → a graceful job error (422 at the endpoint
  for empty/oversized `content`; the worker errors cleanly on bad JSON / unknown version), never a crash.

## Adversarial checklist

- `POST /library/bundle/export {scope:"selection", paper_ids:[]}` → **422**.
- `POST /library/bundle/import {content:"not a bundle"}` → 202, then the job status is **error** with a clear message
  (not a crash).
- Import a bundle with `callosum_bundle: 99` (unknown version) → job **error**.
- `GET /library/bundle/import/<bogus-job-id>` → **404**.
- The exported JSON has **no** `pdf` / `attachment` / file-bytes fields anywhere.

## Steps

1. Library header → **+ Add ▾** → **Export library bundle…** → confirm a `callosum-library-bundle.json` downloads
   (`POST /library/bundle/export {scope:"library"}`) and its content is valid JSON with `callosum_bundle: 1`, a
   `papers` array (each with `identity` + `csl_json` + `tags` + `annotations`), and an `axes` array — and **no PDF**.
2. Select some papers (checkbox) → the selection bulk-bar **bundle** action → a selection bundle downloads
   (`{scope:"selection"}`) carrying only those papers + tags + annotations and **no** `axes`.
3. **+ Add ▾** → **Import bundle…** → pick a bundle file → **Import** (`POST /library/bundle/import` → poll
   `GET .../import/{job_id}` with the `ProgressBar`). Confirm the summary reports created / merged / tags / highlights
   / axes / skipped, and **no off-machine request** fired.
4. Confirm the merge is **non-destructive** (a paper already present keeps its own title/metadata, gains the bundle's
   tags + a highlight) and a re-import is **idempotent** (no duplicates).
5. Adversarial: empty-selection export → 422; a non-bundle / unknown-version file → a clean job error; a bogus job id
   → 404; resize to `375x812` → no horizontal overflow.

## Pass criteria

- Export downloads a **PDF-less** JSON bundle (library: incl. axes; selection: papers-only). Import merges it and
  reports the summary.
- **0 console/page errors; 0 off-machine requests; no PDF in the payload.**
- Merge is **additive & non-destructive**; re-import is **idempotent**; imported annotations are coordinate-honest
  (note+page land; box only with the same PDF; `attachment_id` NULL).
- 422 (empty selection) / clean job error (bad file / unknown version) / 404 (unknown job) honored; mobile → no overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_54_library_bundle.md` + `screenshots/` (see `_TEMPLATE.md`).
