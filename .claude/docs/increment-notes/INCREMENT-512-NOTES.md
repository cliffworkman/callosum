# Increment 512 — Word Document diagnostics + a real CSL-id reliability fix found while scoping it

## Implemented

Continuing the phased Word/Docs parity roadmap (`INCREMENT-BACKLOG.md` #33/#34) at the P0 remainder: a
**Document diagnostics** command mirroring LibreOffice's `diagnose_document`/`citation_integrity_preflight`
(inc 459) — malformed/unresolvable citations, orphaned or retraction-flagged cited works, and bibliography
health, read-only, no document mutation.

**Scoping this surfaced a real, previously-latent correctness gap, found by tracing actual code rather than
assumption**: Word's composer embedded whatever `id` value `/papers/export`'s CSL-JSON happened to carry for a
paper — the **stored, un-normalized** `csl_json.id` (`to_csl_json` returns the record verbatim, confirmed by
reading `citation_export.py`), which is not guaranteed to equal the paper's real numeric database id (depends
on how the paper was originally imported — a Zotero key, a DOI-based id, etc. could end up there). This never
broke *rendering* (`render_document` is self-contained; `id` is only an internal citeproc correlation key
within one request) but it breaks anything needing to know "which library paper does this citation reference"
— exactly what diagnostics needs. **LibreOffice already solved this** — confirmed by reading
`callosum_cite.py:307`, `_build_records` stamps `out["id"] = f"callosum-{paper_id}"` at insert time, never
trusting the stored value. Word now does the same.

**A second design correction during scoping**: the original plan called for a `/papers/export` batch call to
detect orphaned papers (comparing requested ids against the response's own `.id` field) — but that has the
*exact same* stored-id-unreliability problem just described, applied to the export response instead of the
citation tag. Caught before writing the code. `POST /methods/retraction/check-selected` already returns a
`not_found: [int]` field for exactly the real requested ids that don't exist, so one call does both jobs
(orphan detection + retraction status) using real, unambiguous ids throughout — no `/papers/export` call needed
for diagnostics at all.

### Files

- `adapters/word/taskpane_core.js`:
  - `stampCallosumId(csl, paperId)` / `extractPaperId(cslId)` — stamp/extract the `"callosum-<paperId>"` id
    convention, mirroring `callosum_cite.py:307` exactly.
  - `summarizeDiagnostics(tags, notFoundPaperIds, retractionChecked)` — pure report builder: classifies every
    content-control tag (citation / malformed / bibliography / ignored-other), extracts distinct resolvable
    paper ids, and cross-references against the retraction-check-selected response's `not_found`/`checked`.
    **Explicit scope boundary vs. LibreOffice's `diagnose_document`, stated in the code comment**: Word has no
    embedded schema-version field and no random mark identity separate from Word's own (always-unique,
    Word-managed) content-control id, so "unsupported schema version" and "duplicate mark identity" have no
    Word equivalent and are deliberately not checked — narrower on purpose, not silently.
- `adapters/word/taskpane_core.test.js` — 8 new tests (27 total, was 19): `stampCallosumId`/`extractPaperId`
  round-trip + no-mutation, and `summarizeDiagnostics` across clean/malformed/unresolvable/orphaned/
  retraction-flagged/no-bibliography/no-citations fixtures.
- `adapters/word/taskpane.js`: `onPick` now stamps a reliable id before adding to the assembly; new
  `runDiagnostics()`/`renderDiagnosticsReport()` — one `Word.run` pass reading every content control's tag
  (same `ccs.load("items/tag")` pattern `refreshDocument`/`doFlatten` already use), one
  `/methods/retraction/check-selected` call (capped at 100 distinct ids client-side, matching the backend's
  own `MAX_CHECK_SELECTED`, with an honest "only the first 100 were checked" disclosure if truncated — a
  silently-clean report past the cap would violate the project's own signal-not-verdict / silence-is-not-a-
  certificate posture), and a plain-text results summary rendered into a new `#diagnostics` panel.
- `adapters/word/taskpane.html`/`.css` — "Document diagnostics…" button + the results panel (auto-hides when
  empty via `:empty`, matching the assembly section's show/hide pattern without needing extra JS).

**No backend changes** — `POST /methods/retraction/check-selected` was already adapter-agnostic.

## Key technical detail

Diagnostics' orphan/retraction checks are honestly bounded, not silently degraded: `distinctPaperIds` (used for
citation/malformed/bibliography counts) always reflects the FULL document, but `orphanedPaperIds`/
`retractionFlagged` only cover whichever ids actually got checked (capped at 100). A citation beyond that cap
isn't reported "clean" by omission — the UI explicitly states not everything was checked whenever truncation
happens, rather than letting an unchecked citation look identical to a verified-clean one.

## Manual verification script

Not yet run live (this session's established pattern — build, verify with `node --test`, then hand off for a
real-Word check). In real Word: insert a fresh citation via the composer (gets the new stamped id), run
**Document diagnostics…**, confirm it reports 0 malformed/unresolvable/orphaned and the correct bibliography
state. Delete the cited paper from the library (Library → trash/delete) and re-run diagnostics — confirm it's
now reported orphaned. If a retracted paper exists in the library, cite it and confirm diagnostics flags it.
Any citation inserted before this fix (during this session's earlier testing) should be reported as
"unresolvable," not orphaned or crash the scan — confirms the backward-compatible degradation path works.

## Pytest / tests

`node --test adapters/word/taskpane_core.test.js` → 27/27 passed (19 existing + 8 new). No Python test changes
— confirmed by reading that `methods_retraction.py`/`paper_query_repo.py` needed zero changes; this is 100%
adapter-side (Word) work reusing an already-adapter-agnostic backend endpoint.
