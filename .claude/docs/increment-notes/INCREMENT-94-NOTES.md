# Increment 94 — Library-header polish: "+ Add ▾" menu + persistent / descending Sort

The two **chores** of the patter (the carrot, statcheck, follows in its own plan-mode increment). Both are small,
frontend-leaning library-header UX wins.

## Implemented

### Chore 1 — declutter the header into a "+ Add ▾" menu
The library header had grown to six actions (Scan folder · Import · Unsorted · Wanted · Duplicates · Trash). The
two "bring papers in" actions are folded into one **"+ Add ▾"** dropdown:
- New `AddMenu` component (`app/frontend/js/10_pdf_layer.jsx`) — a `.trash-toggle`-styled trigger (so it blends
  with the row) + a small popup with **Scan folder…** / **Import file…**, closing on outside-click (a
  `document` mousedown listener in a `useEffect`, cleaned up). Replaced the two standalone buttons with
  `<AddMenu onScan={onOpenScan} onImport={onOpenImport} />`.
- CSS (`styles.css`): `.add-menu` (positioning context) + `.add-menu-pop` (the dropdown panel) + its item
  buttons — all token-based (`--panel`/`--line-2`/`--radius`/`--sans`/`--ink-2`/`--hover`/`--accent`; a modest
  one-off box-shadow like the modal's). Header: 6 actions → 5.

### Chore 2 — persistent + descending Sort
- The **Sort** choice now **persists** across reloads: `librarySort` initializes from
  `localStorage["callosum.librarySort"]` and `changeSort` writes it (mirrors the theme + hide-uncertain prefs).
- Added **Title (Z–A)** and **Author (Z–A)** options: new `title_desc` / `author_desc` keys in the
  `_paper_sort_order` allowlist (`repository.py`; NULL author still sorts last; `papers.id` stays the stable
  tiebreak) + the two `<option>`s in the Sort `<select>`.

Rebuilt `callosum-app.html`.

## Key technical detail
The "+ Add ▾" menu reuses the borderless `.trash-toggle` text-button style for its trigger so it's visually
identical to the other header actions; only the popup is new chrome. Sort descending is the same allowlist/param
pattern as every other sort key (rule #3 — the key indexes a constant ORDER BY, never interpolated); persistence
is pure frontend `localStorage` (no backend/migration). Both chores: **no migration, no egress, no new endpoint.**

## Manual verification script
1. Hard-refresh. The header shows **+ Add ▾** (not separate Scan/Import); click it → Scan folder… / Import
   file… open the right modals; clicking elsewhere closes the menu.
2. Change **Sort** to e.g. Title (Z–A) → the list reverses; **reload** → the sort choice is retained.
   _(Visual check delegated to the user.)_

## Pytest
**395 passed, 1 skipped** — unchanged count (Chore 1 frontend-only; Chore 2 added two assertions to the existing
`test_library_sort_orders` for `title_desc`/`author_desc`). `ruff` clean. No migration, no egress.
