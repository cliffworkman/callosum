# Increment 380 - Writer heading-scoped bibliographies

## Context

Bibliography item #11 still needed chapter/section bibliographies. The existing Writer adapter had one bounded
full-document bookmark pair, while section refresh already had a semantic outline definition: nearest preceding
heading plus nested lower-ranked headings until the next peer/ancestor heading.

## Implemented

- **Insert current-section bibliography here** creates a live bibliography at the main-text caret for that
  semantic heading subtree. **Remove bibliography for current section** removes only its block.
- Each block owns a random 128-bit lowercase-hex identity and strict scope/start/end bookmark triple. The scope
  marker stays at the heading boundary; the start/end pair bounds only generated bibliography text.
- Up to 50 complete blocks may coexist with the ordinary full-document bibliography.
- Citeproc still receives the complete ordered manuscript, uncited/excluded settings, and active style. A pure
  projection keeps entries whose citeproc ids intersect live citation items anchored in the block's subtree.
  Ordering, categories, and validated DOI/URL spans therefore reuse the full render.
- Passive and explicit bibliography refresh compare and rebuild only stale blocks in the same UndoManager group
  as any full bibliography/citation changes. Rollback verifies both the full and every section signature.
- Document observation includes section managed text; diagnostics reports count/damaged identities; damaged
  triples block refresh/new insertion; flatten removes all section wrappers while retaining rendered text.
- Section blocks never create full-bibliography entry targets, avoiding duplicate Writer bookmark names.
- Placement conversion fails before style lookup or mutation while section blocks exist. Multi-range conversion
  Undo/Redo is the next hardening increment rather than an unverified extension of the single-range recovery path.
- OXT version: `0.25.0`.

## Gates

- **Principles / governance:** non-triggering. Section membership is deterministic Writer structure plus explicit
  author insertion, never inferred importance or recommendation.
- **Security:** `2026-07-25_writer-heading-scoped-bibliographies.md` - **PASS**.
- **QA:** route 34 step 20 covers outline membership, multiple/full coexistence, refresh/reopen/removal,
  categories/links, malformed bounds, cap, rollback, flatten, and conversion refusal.
- **Experience:** a deadline-author found the behavior safe and non-destructive. The review caused three in-
  increment copy fixes: **here** now makes placement explicit, docs define the exact outline-subtree mental
  model, and conversion refusal explains safe Undo in user terms. List/jump-to, remove-all, and heading/count
  success feedback remain polish.

## Verification

- Focused LibreOffice adapter/OXT tests: **135 passed**.
- Focused adapter/OXT/install/help tests: **153 passed**.
- Installed Writer focused section-bibliography spike: **SELFTEST OK**.
- Installed Writer full matrix: **SELFTEST OK** (exit 0; 614.9 seconds).
- Full project suite: **1582 passed, 1 skipped** (765.68 seconds).
- Ruff check/format: **pass** (517 files).
- Line budget: **pass** (386 app-source files).
- QA surface map: **pass** (309/309 gated API, 1370/1391 frontend with 21 existing report-only findings).
- OXT packaging: **pass** (71,741 bytes).
- Diff hygiene: **pass**.

## Remaining item #11 scope

Verified multi-range placement-conversion Undo/Redo, bibliography-title links, and per-source navigation for
grouped citations remain.
