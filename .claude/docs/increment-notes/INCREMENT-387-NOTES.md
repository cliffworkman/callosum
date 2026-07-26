# Increment 387 — conservative table-aware statcheck

**Date:** 2026-07-25
**Status:** implemented; local gates complete

## Outcome

Backlog #27 is closed. Per-paper and whole-library statcheck now supplement the existing extracted-prose scan
with a bounded, local pass over clearly headed result tables in PDF, JATS/XML, HTML, DOCX, and ODT attachments.
Rows retain their original header and cell text plus attachment, page, table, row, caption/section, and—where
PDF supplies it—the table-row bounding region.

The parser is deliberately narrow. It reconstructs a candidate only when a row has one unambiguous p-value
column and complete test/type, degrees-of-freedom, and statistic fields, or when a single table cell already
contains a complete APA result. Ambiguous, unlabeled, multi-p-value, or incomplete rows remain silent. The
existing consistency math and signal-not-verdict language are unchanged.

## Architecture and boundaries

- `app/backend/document_tables.py` is a small, cached, format-dispatched table-evidence provider. It does not
  modify `DocumentTextProvider`, chunks, embeddings, or document persistence.
- `app/backend/methods/statcheck_tables.py` is a pure conservative header/row interpreter. It returns structured
  candidates to the existing statcheck recomputation path rather than duplicating statistical logic.
- `run_statcheck(..., table_rows=...)` accepts ephemeral table evidence, deduplicates by provenance/raw result,
  and marks results as `prose` or `table`.
- API coverage names scanned/skipped attachments, pages, tables, rows, table results, and truncation. A malformed
  attachment fails independently, preserving prose findings.
- Library batch extraction occurs outside write transactions. Existing statcheck summaries/findings persist in
  the established short per-paper write.
- P-curve remains inline-prose-only because choosing focal results from tables is a distinct, judgment-laden
  problem. WIP statcheck remains snapshot-chunk-only.
- `STATCHECK_VERSION` advances from `1` to `2` because serialized results now carry source/table provenance;
  existing WIP statcheck snapshots are therefore honestly invalidated even though WIP remains prose-only.
- There is no migration, dependency, egress, LLM use, or new executable path.

## Safety caps

- Eight supported attachments per paper.
- 256 MiB source file and 64 MiB ZIP member.
- 200 PDF pages, 100 tables, 1,000 rows, 50 columns, and 2,000 characters per cell.
- 64-entry extraction cache keyed by resolved path, content type, size, and modification time.

## User experience

The Statistics panel distinguishes reconstructed evidence with a neutral **TABLE N · ROW N** badge, keeps the
source header and row visible, and reports scan coverage and safety truncation. PDF table evidence opens at
region precision; non-page formats remain visibly unlocated. The table badge is provenance—not verified green—
while the separate consistency state continues to describe the arithmetic result.

A skeptical synthesizer's goal-in-the-moment pass asked: “Can I tell exactly what Callosum reconstructed, and
can I inspect the source before treating the flag as meaningful?” The real-browser fixture made the table
origin, row, coverage, and caveat legible, with the source jump as the intended next action. The phone-width
check had no overflow. Persona-agent dispatch was unavailable under the session's no-delegation constraint, so
the pass was driven directly.

## Manual verification

1. Attach a supported document containing a clearly labeled `Test`, `df`, statistic, and `p` result table.
2. Open **METHODS → Statistics → This paper** and run the check.
3. Confirm the result has a **TABLE N · ROW N** badge, displays the original header and row, and reports the
   attachment/table/row coverage.
4. For a PDF, click the page locator and confirm it opens the table region without claiming an exact quote.
5. Repeat with an ambiguous multi-p-value or incomplete table; confirm no row is reconstructed.
6. Add a malformed supported attachment beside valid prose; confirm the prose result remains and skipped
   coverage increases.
7. Run **Whole library** and confirm a table-only inconsistency enters the existing review signal.
8. Resize to 375×812 and confirm badge, row, coverage, and caveat remain within the panel.

## Verification

- Focused document/statcheck/p-curve/frontend suite: **100 passed**; focused statcheck/WIP regression slice:
  **47 passed**.
- Chromium smoke: **5 passed** with zero console/page errors, including the table-provenance path at 375×812.
- Alembic upgrade/model-drift tests: **3 passed**.
- Ruff check/format, 393-file source line budget, frontend build/assembly, help sync, and diff hygiene: pass.
- QA surface map: **312/312 API** and **1378/1399 frontend**; the 21 frontend items remain explicitly
  report-only and every gated surface is claimed.
- Full project suite: **1607 passed, 1 skipped** in 1555.85 seconds.
