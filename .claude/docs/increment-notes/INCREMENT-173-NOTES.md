# Increment 173 — import reports parse-time skipped records (backlog #4)

The autonomous remainder of backlog **#4** (progress/feedback for long ops). The citation import (BibTeX/RIS/
CSL-JSON, inc 93) **silently dropped** entries with no title AND no DOI *at parse* — before any count — so a
50-entry `.bib` could quietly become 47 imported with no explanation. Now those drops are reported, symmetric with
inc-155's "which files couldn't be read" on the scan side.

## Implemented
- **`metadata/citation_import.py`** — the three parsers now return `(records, skipped)`:
  `parse_bibtex`/`parse_ris` count real entries (not `@comment`/`@preamble`/`@string`; ER-delimited for RIS) whose
  `_*_to_csl` yielded None; `parse_csl_json` counts array items that are non-dict or lack title+DOI. `parse_records`
  returns `(records, resolved, skipped)` and folds **record-cap truncation** into `skipped` too (anything beyond
  `MAX_IMPORT_RECORDS` is also a silent drop). `import_citations` returns `{…, "skipped": skipped}`.
- **`routers/library.py`** — `ImportSummary.skipped: int` (additive) + mapped from the result.
- **`28_import.jsx`** — the done-summary now shows `· N skipped (no title or DOI)`, and the old mislabel is fixed:
  `failed` (import-time errors) and `skipped` (parse drops) are now distinct lines.

## Key detail
`skipped` (parse drops / over-cap) and `failed` (per-record exceptions during create, in a savepoint) are
**distinct + complementary** — a record only reaches `import_citations` if it had a title or DOI, so the
`(untitled import)` guard there almost never fires now; the real "this entry never made it" signal is `skipped`.

## Gates
- Backend additive (one new response field); **no migration, no egress, no new endpoint** → no audit trigger;
  Principles non-triggering (honest feedback, "silence is not a certificate").
- **QA (rule #10):** `skipped` is an additive field on an existing response — surface unchanged (121/121 API +
  608/608 FE, 0 uncovered).

## Pytest / checks
**`test_citation_import.py` 9/9** (parser skip counts: bibtex junk→1, ris→0, csl malformed-array→2; `import_citations`
result `skipped == 1`); `ruff` clean + formatted; frontend rebuilt; `test_frontend_assembly` 5/5. Full suite
unchanged at **619** (the 2 new assertions ride existing tests + 1 new sub-assertion).

## Remaining on #4 (not autonomous)
Per-item **filename** in the progress label + a rough **ETA**, and a **cancel** button — smaller-but-infra (needs
cooperative job cancellation). Left below the cut.
