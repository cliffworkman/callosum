# Increment 385 — Writer journal-abbreviation controls

**Date:** 2026-07-25
**Status:** implemented; local gates complete

## Outcome

`Callosum → Journal abbreviations…` gives each Writer document three explicit choices:

1. **Library abbreviations (default)** — retain the historical CSL behavior using embedded
   `container-title-short`/`journalAbbreviation` metadata.
2. **MEDLINE first (library fallback)** — match the bundled NLM catalog by ISSN, then exact normalized journal
   title; use embedded library metadata only when NLM has no exact match.
3. **Full journal titles** — remove short-title hints from render copies so citeproc falls back to the complete
   `container-title`.

The selection is sent through the shared position-aware document render, so applicable live citation text, the
full bibliography, and every section bibliography remain one coherent citeproc result. It is stored in the
Writer file and applies immediately.

## Data and honesty

- `tools/update_medline_journal_abbreviations.py` downloads only NLM's fixed HTTPS `J_Medline.txt`, applies a
  15-MB bound, rejects unexpectedly small parses, drops ambiguous conflicting keys, and writes deterministic
  gzip JSON atomically.
- The committed 2026-07-25 snapshot contains **37,971** parsed records and is **1,142,651 bytes** compressed
  (**3,866,598 bytes** JSON).
- Runtime matching is local and deterministic: ISSN, then exact normalized title—never fuzzy guessing.
- The render response reports whether the CSL style requests short journal titles plus document-unique
  MEDLINE/library/full/unknown counts, at most 20 unknown-title examples, and the NLM snapshot date.
- Transformations use copied CSL items. Embedded Writer payloads and library metadata remain unchanged.
- NLM provenance, currency limits, non-endorsement, and terms are recorded in `THIRD-PARTY-NOTICES.md`.

## Experience pass

A deadline author choosing a journal's submission style should not need to understand citeproc internals.
The menu names all three outcomes and the MEDLINE/library precedence. The post-refresh message acts as a real
preview/validation result: it says when the current style uses full titles, otherwise reports exact source counts
and bounded unknown examples. Unknowns remain readable full titles and do not block the manuscript.

The code/help-grounded pass found no fix-now ambiguity. A persona subagent was not used because delegation was
disabled. Cliff's manual click-through remains useful for the dropdown and long unknown-title message layout.

## Manual QA

1. In Writer, cite one work with a library abbreviation, one exact MEDLINE journal, and one unknown journal.
2. Select Nature or IEEE, open **Journal abbreviations…**, and choose each mode in turn.
3. Confirm library metadata, MEDLINE precedence, and full names respectively; inspect the coverage message.
4. Confirm the full and section bibliographies agree, then save/reopen and refresh.
5. Switch to APA and confirm the message explains why visible full titles do not change.
6. Cancel once and confirm no preference or text change.

## Verification

- Focused citation/adapter/OXT/install/help tests: **222 passed**.
- Installed Writer focused journal-abbreviation spike: **SELFTEST OK**.
- Installed Writer full matrix: **SELFTEST OK**.
- Full project suite: **1589 passed, 1 skipped** in 695.44 seconds.
- Ruff check and format: pass (**519 files already formatted**).
- Line budget: pass (**387** application-source files within the 600-line cap).
- QA surface map: pass (**309/309** API; **1370/1391** frontend, 21 report-only).
- OXT packaging: pass (`0.30.0`, **79,672 bytes**).
- Bundled-index integrity and diff hygiene: pass.

## Remaining LibreOffice scope

The adapter is closed for now. Traveling-library collaboration, comprehensive keyboard/screen-reader
accessibility, cross-editor parity, and P2 manuscript-analysis features remain future projects, not unfinished
work in this active phase.
