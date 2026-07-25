# Increment 379 - Writer custom bibliography category order

## Context

Increments 377/378 made categorized bibliographies correct and efficient, but always alphabetized the category
headings. Authors may need manuscript logic such as Background, Methods, Evidence, and Further discussion rather
than lexical order.

## Implemented

- **Category order…** in the document-citations panel lists active categories and provides **Move ↑ / ↓**,
  **Reset alphabetical**, Save, and Cancel.
- A separate bounded Writer property stores explicit category precedence. Configured active categories lead;
  newly created or otherwise unranked categories follow alphabetically.
- Citeproc order inside every category remains stable. **Other references** is generated, not user-orderable,
  and always remains last.
- Save performs one bibliography-only refresh. Failure restores the exact prior property. Reset plus Save
  removes the property and restores the Increment 377 alphabetical behavior.
- Custom order survives refresh, save/reopen, bibliography links, and citation placement conversion.
- The extension version is `0.24.0`.

## Gates

- **Principles / governance:** non-triggering. Order is explicit author organization, not inferred importance,
  quality, or recommendation.
- **Security:** `2026-07-25_writer-custom-bibliography-category-order.md` - **PASS**.
- **QA:** route 34 covers reorder/reset/cancel, new-category fallback, Other-last, per-group stability, links,
  refresh, movement, conversion, reopen, invalid metadata, bounds, and exact failure rollback.
- **Experience:** a deadline-author completed reorder/reset safely. Selection follows moved items, Save/Cancel
  staging is clear, new categories appear for later placement, and omitting **Other references** from the list
  matches expectations. Boundary-button feedback, a stronger reset/save hint, and clearing stale order with
  fewer than two active categories remain polish.

## Manual verification

1. Create three named bibliography groups and open **Category order…**.
2. Move the last category to the top and Save; confirm headings move but entry formatting/order does not.
3. Save/reopen, refresh, and convert citation placement; confirm order and links persist.
4. Add a new category; confirm it follows configured groups alphabetically until positioned.
5. Reopen, choose **Reset alphabetical**, Save, and confirm the custom property disappears.
6. Cancel a changed draft and confirm the document remains untouched.

## Verification

- Focused LibreOffice adapter/OXT tests: **132 passed**.
- Installed Writer focused category spike: **SELFTEST OK**.
- Installed Writer full matrix: **SELFTEST OK**.
- Full project suite: **1579 passed, 1 skipped**.
- Ruff check/format: **pass** (517 files).
- Line budget: **pass** (386 app-source files).
- QA surface map: **pass** (309/309 gated API, 1370/1391 frontend with 21 existing report-only findings).
- OXT packaging: **pass** (68,156 bytes).
- Diff hygiene: **pass**.

## Remaining item #11 scope

Chapter/section bibliographies (optionally alongside a full-document bibliography), bibliography-title links,
and per-source navigation for grouped citations remain.
