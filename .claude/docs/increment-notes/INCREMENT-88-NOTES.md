# Increment 88 — Search + Sort on one row

## Implemented
A small library-pane layout tweak (user request): the **Sort** control now sits **inline at the right of the
search box** instead of on its own row below it, reclaiming a row of vertical space.

- `app/frontend/js/10_pdf_layer.jsx` — moved the `Sort` label + `<select>` **into** the existing `.searchbar`
  flex row (after the input) and removed the separate `.lib-sort-row` wrapper `<div>`.
- `app/frontend/styles.css` — deleted the now-unused `.lib-sort-row` rule; gave `.lib-sort-label` + `.lib-sort`
  `flex: none` (+ `white-space: nowrap` on the label) so they keep their size while the search input (`flex: 1`)
  absorbs the width.
- Rebuilt `callosum-app.html`.

## Manual verification script
1. Hard-refresh (Ctrl+Shift+R).
2. The library search box and the **Sort** dropdown are on **one row** (search grows; Sort sits at the right);
   sorting + search still work. _(Visual check delegated to the user.)_

## Pytest
**383 passed, 1 skipped** — unchanged (frontend-only; no Python touched). No migration, no endpoint, no egress.
