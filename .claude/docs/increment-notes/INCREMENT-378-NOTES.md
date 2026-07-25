# Increment 378 - Writer batch bibliography categories

## Context

Increment 377 made categorized bibliographies correct but still required one dialog and one bibliography refresh
per work. A medium manuscript needed a reusable category vocabulary and a safe multi-work operation before the
larger custom-ordering or chapter/section work.

## Implemented

- **Citations in this document…** enables bounded Ctrl/Shift multi-selection and advertises it above the list.
- **Set category…** offers existing document categories alphabetically, plus explicit **Create new category…**
  and **Remove category** choices. Mixed-category batches default to a no-op placeholder.
- One batch deduplicates and validates numeric paper ids, caps the request at 1,000 works, writes the document
  property once, and refreshes the bibliography once.
- A refresh failure restores the complete prior category map. Invalid input and blank create-new input mutate
  nothing. The existing single-work setter remains a backward-compatible wrapper.
- Go to and bibliography exclusion now explain ambiguous or uncited selections without closing the panel.
- The extension version is `0.23.0`.

## Gates

- **Principles / governance:** non-triggering. This is explicit author organization, not inference, scoring, or
  recommendation.
- **Security:** `2026-07-25_writer-batch-bibliography-categories.md` - **PASS**.
- **QA:** route 34 covers multi-selection, mixed defaults, label reuse/create/remove, guarded navigation and
  exclusion, one-refresh transactionality, rollback, real Writer conversion/links, reopen, and bounds.
- **Experience:** a deadline-author found the batch path discoverable and materially faster. Its fix-now blank,
  navigation, and uncited-exclusion dead ends were closed. Select-all-visible and selection preservation remain
  polish.

## Manual verification

1. Open **Citations in this document…** with several cited/uncited works and Ctrl/Shift-select a mixed batch.
2. Choose **Set category…**; confirm the placeholder is selected and OK changes nothing.
3. Reopen the picker, reuse an existing category, and confirm every selected row changes after one refresh.
4. Create a new category, then remove it with **Remove category**. Blank create input must be a no-op.
5. Confirm multi/uncited Go to and exclusion show an explanation while the panel remains open.
6. Save/reopen, convert citation placement, and confirm category layout and DOI links remain coherent.

## Verification

- Focused LibreOffice adapter/OXT/install/help tests: **149 passed**.
- Installed Writer focused category spike: **SELFTEST OK**.
- Installed Writer full matrix: **SELFTEST OK**.
- Full project suite: **1578 passed, 1 skipped**.
- Ruff check/format, line budget, QA surface map, OXT packaging, and diff hygiene: **PASS**.

## Remaining item #11 scope

Custom category ordering, chapter/section bibliographies (optionally alongside a full-document bibliography),
bibliography-title links, and per-source navigation for grouped citations remain.
