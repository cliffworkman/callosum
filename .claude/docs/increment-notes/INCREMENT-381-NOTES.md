# Increment 381 - Writer section-bibliography placement conversion

## Context

Increment 380 deliberately refused citation-placement conversion while heading-scoped bibliographies existed.
Writer restores replaced bibliography text during Undo but collapses removed/recreated zero-width boundary
bookmarks, and repairing several pairs inside an Undo listener can terminate the native process.

## Implemented

- Placement conversion accepts complete, non-empty heading-scoped bibliography blocks and includes their target
  render in the same Writer Undo transaction as citation relocation and the full bibliography.
- Conversion keeps every section scope/start/end bookmark object attached. It preserves the unchanged first
  heading character and final newline and replaces only the interior, so native Undo/Redo retain exact bounds.
- The ordinary full-bibliography repair listener remains limited to its previously verified single pair.
- The hidden conversion-state ReferenceMark selects a bounded collision-free main-text point instead of assuming
  document start, where it could displace a section scope marker.
- Conversion verifies every section render after commit and includes full plus section signatures in exact
  rollback/copy-isolation snapshots.
- Damaged triples, more than 50 blocks, and empty/degenerate section blocks refuse before mutation.
- OXT version: `0.26.0`.

## Gates

- **Principles / governance:** non-triggering. The change is deterministic document formatting and does not rank,
  recommend, or infer research importance.
- **Security:** `2026-07-25_writer-section-bibliography-conversion.md` - **PASS**.
- **QA:** route 34 step 20 now covers APA-inline to Chicago-footnote conversion with two section blocks, exact
  Undo/Redo, injected rollback, converted-copy isolation, save/reopen, and damaged/empty refusal.
- **Experience:** local deadline-author review found the existing preview and one-step Undo mental model clear;
  retaining chapter bibliographies removes a destructive prerequisite. No persona subagent was used because
  delegation was disabled for this run.

## Verification

- Focused LibreOffice adapter/OXT tests: **135 passed**.
- Focused adapter/OXT/install/help tests: **153 passed**.
- Installed Writer focused section-bibliography spike: **SELFTEST OK** (exit 0; 112.9 seconds).
- Installed Writer full matrix: **SELFTEST OK** (exit 0; 572.2 seconds).
- Full project suite: **1582 passed, 1 skipped** (748.45 seconds).
- Ruff check/format: **pass**.
- Line budget: **pass** (386 app-source files).
- QA surface map: **pass** (309/309 gated API; 1370/1391 frontend with 21 existing report-only findings).
- OXT packaging: **pass** (72,983 bytes).
- Diff hygiene: **pass**.

## Remaining item #11 scope

Bibliography-title links, per-source navigation for grouped citations, and long-manuscript section-bibliography
list/jump/remove-all polish remain.
