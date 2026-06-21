# Increment 103 — Per-card "copy BibTeX" clipboard button

A small library-card affordance the user requested. inc-98's `user-select: none` on `.paper` cards (which fixed
the double-click word-select) removed the ability to select/copy a card's text — so each card now carries a small
**clipboard icon button** that copies the paper's **BibTeX** citation to the clipboard in one click, placed just
left of the existing checkbox.

## Implemented
- **`app/frontend/js/10_pdf_layer.jsx`**
  - `PaperCopyButton({ paperId })` — mirrors the inc-70 `CiteRow` copy: a raw
    `fetch(API_BASE + "/papers/export", { paper_ids:[paperId], format:"bibtex" })` →
    `navigator.clipboard.writeText(await res.text())` (clipboard works on the 127.0.0.1 secure context). `onClick`
    calls `e.stopPropagation()` so copying never selects/opens the card; a `copied` state flips the icon to a ✓ for
    ~1.5s.
  - Two tiny inline SVG components — `ClipboardIcon` (Feather "copy") + `CheckIcon` (Feather "check"),
    `stroke="currentColor"` so they theme. (The user asked specifically for an SVG; most existing icons are emoji.)
  - Rendered in the card just **before** the checkbox, under the **same `{selecting && …}`** condition
    (`selecting = !focusAxis && !trashView`), so it sits alongside the checkbox in the normal library view. The
    checkbox markup/position is untouched.
- **`app/frontend/styles.css`**
  - `.paper-copy` — an icon button absolutely positioned at `top:10px; right:36px` (left of the `right:14px`
    checkbox, vertically aligned); transparent, `--ink-3` → `--accent` on hover, `--verified` when copied; 14px
    SVG. Tokens only (rule #8).
  - `.paper-title` gained `padding-right: 46px` so a long title's first line clears the two top-right controls.

## Key technical detail
**No backend change** — `POST /papers/export` (inc 70) already validates `paper_ids` + `format` (a `Literal`,
so anything else is a 422), reads live papers only, and renders BibTeX from the stored `csl_json`. The card button
just calls it for a single id and writes the result to the clipboard. Local, read-only, no egress, no migration.
Scoped to the `selecting` view (normal library) to match the user's "alongside the checkbox" placement; not added
to Trash/focus.

## Manual verification script (delegated — needs a real click + clipboard)
1. In the normal library view, each card shows a clipboard icon just left of its checkbox, vertically aligned.
2. Click it → the icon flips to a green ✓ (~1.5s) and the card is **not** selected/opened; paste → the
   `@article{…}` BibTeX record (title + authors + year + venue + DOI).
3. Confirm it does **not** appear in Trash or axis-focus mode, and that long titles clear both controls.

## Pytest
**411 passed, 1 skipped** — unchanged (frontend-only; the BibTeX export path is already covered by the
citation-export / `test_papers` tests). `ruff` clean; the opt-in Playwright smoke passed (0 console errors —
confirms the SVG/JSX compiled under the inc-102 esbuild precompile); `callosum-app.html` rebuilt.
