# Increment 101 — Reading mode (one-click distraction-free reader)

The carrot of the inc 100–101 patter. A toggle that hides **both** side panels and their dividers to maximize
the center pane (the open PDF), with **Esc** to return — for focused reading. Frontend-only; builds directly on
the inc-42 collapsible-panel model.

## Implemented
- **`40_app.jsx`**
  - `readingMode` state + a `_panelSnapshot` ref. `toggleReading()`: on enter, snapshots `leftOpen`/`rightOpen`,
    collapses both, sets the flag; on exit, restores the snapshot. **Not persisted** — a reload returns to normal
    (never leaves the user stuck with hidden chrome).
  - An **Esc-to-exit** keydown effect, active only while `readingMode`, **skipped when a modal owns Escape**
    (`anyModalOpen` = settings/help/duplicates/wanted/scan/import) so Esc closes the modal first.
  - `cols` gains a reading branch: `0px 0px minmax(340px,1fr) 0px 0px` — the panel tracks are already 0 (via
    `leftOpen`/`rightOpen=false`), and this also zeroes the two **divider** tracks. `.app` gets a `reading` class.
  - `readingMode` + `onToggleReading` threaded to `LibraryFrame`.
- **`30_viewer.jsx`** — `LibraryFrame` renders a **`.frame-reading`** toggle at the right of the tab bar
  (`⛶ Read` / `⤢ Exit`), the one control that stays reachable in reading mode (the sidebar — with the ⚙/❓
  buttons — is hidden, so the toggle + Esc are the way back).
- **`styles.css`** — `.frame-reading` (a tab-bar control, `margin-left:auto`; **accent = active**, matching the
  `.frame-tab.active` pattern; tokens only — `--ink-2`/`--line-2`/`--accent`/`--accent-soft`/`--accent-line`/
  `--radius-sm`, no raw hex, rule #8) + `.app.reading .divider { display:none }` (so the collapsed dividers'
  expand chevrons don't overflow the 0px tracks).

## Key technical detail
The mode is a **pure view state** — it sets `leftOpen`/`rightOpen=false` (so the panels unmount exactly as the
existing chevron-collapse does) and additionally zeroes the divider tracks + hides the dividers, so nothing but
the center pane shows. Restoring the snapshot returns the user to whatever asymmetric layout they had (e.g. left
open / right closed), not a hardcoded default. Hiding the dividers removes the only other re-open affordance, so
the mode is unambiguous: the **⤢ Exit** button or **Esc** is the single way out. No backend, no migration, no
egress, no new token.

## Manual verification script (delegated — no Playwright MCP this session)
1. Open a PDF. Click **⛶ Read** at the right of the tab bar → both side panels and their dividers vanish; the PDF
   fills the width; the button reads **⤢ Exit** (accent-highlighted).
2. Press **Esc** (or click **⤢ Exit**) → the panels return to **exactly** their prior state (try it with the left
   panel open and the right collapsed first — that asymmetry should be restored).
3. With a side panel collapsed via its chevron beforehand, enter then exit reading mode → the collapsed/open mix
   is preserved.
4. Reload the page while in reading mode → it returns to the normal layout (reading mode is transient).
5. Open the Scan/Import modal from the library header while reading, press Esc → the modal closes (reading mode is
   not exited under it).

## Pytest
**411 passed, 1 skipped** — unchanged (frontend-only; no Python touched). `ruff` clean; `callosum-app.html`
rebuilt; no help-corpus change needed (Reading mode is self-evident from its labeled toggle + tooltip — a
candidate for a one-line note in the "Getting around" help section if the user wants it).
