# Increment 397 — Three small UI cleanups: "More checks", METHODS text-wrap, unthemed CSL buttons

**Date:** 2026-07-27
**Status:** All three implemented and verified live via Playwright (light + dark theme).

## Context

Three independent, purely-frontend cosmetic/cleanup requests in one sitting:

1. Remove the "More checks" subsection from Statistics (paper Detail pane's METHODS accordion) —
   redundant: p-curve already lives in its own modal, and future statcheck extensions will just be
   bundled into the existing statcheck results rather than needing a separate list.
2. Fix a long-standing text-wrapping bug across all 4 Checklists sections, Statistics, and Data (same
   METHODS panel): descriptive intro paragraphs (e.g. the statcheck "WHOLE LIBRARY" blurb) wrapped
   noticeably narrower than the panel's actual width.
3. Unthemed buttons in Settings' citation-style panel: "Install .csl" and "Import URL" rendered as
   native unstyled browser buttons instead of the app's themed recipe — and the same bug was found on
   4 more buttons in the same panel while investigating ("Edit source", "Duplicate"/"Duplicate to
   edit", "Check for updates", "Download .csl").

## Implemented

**"More checks" removal.** `app/frontend/js/09_placeholders.jsx` registered a second tab on the real
Statistics section (`registerPaneTab`, id `statcheck-more`) rendering a pure `<ComingSoon>` stub — no
live logic, no button, no API call. It was the *last* remaining "coming soon" placeholder in the
codebase (five earlier ones — Discover, Mixed-model, Bayesian, Meta-analysis, Citation-equity — had
already been removed in prior increments as their real features shipped), so once removed the
`ComingSoon` component had zero callers left. Per rule #5, deleted the whole file outright (not just
the tab registration) rather than leave a comment-only husk, and removed the now-dead `.coming-soon*`
CSS block (`styles.css`) — nothing else referenced either. `05_panes.jsx`'s tab-strip render logic
(`tabs.length > 1 ? (strip) : tabs[0].render(...)`) already collapses cleanly to no-strip with one tab,
confirmed by direct read before relying on it. p-curve's real entry point (Library toolbar bulk action
→ `PcurveModal`) is untouched and independent — it never depended on this stub.
`.claude/DESIGN.md`'s "Coming soon" recipe entry updated to note the pattern is currently dormant (no
active file) but stays the convention to follow if a future stub is ever needed.

**METHODS text-wrap fix.** All 4 Checklists + Statistics + Data intro paragraphs share
`<div className="settings-sub">`. Its base rule (`styles.css`) carries a hardcoded `max-width: 300px`
— correct in `.settings-sub`'s original narrow Settings-sidebar home, but several other reuse contexts
already override it back to `max-width: none` per-container (`.settings-section`, `.settings-ai-controls`,
`.provider-card`, and `.ws-pad`/`.wb-pane`). The comment directly above that last override *already
named* the METHODS accordion (`.acc-body`) as a context needing the same treatment — but the selector
list never actually included it. A documented-but-never-added selector, not a flex/min-width bug. Fix:
added `.acc-body .settings-sub` to that selector list. The base `.settings-sub` rule itself is
untouched (still 300px in its genuinely narrow Settings-sidebar home).

**Unthemed Settings buttons.** `app/frontend/js/35d_citation_styles.jsx`'s "Install .csl" and
"Import URL" buttons (plus "Edit source", "Duplicate"/"Duplicate to edit", "Check for updates",
"Download .csl" found in the same file/panel) used bare `className="btn"` with no variant class. The
base `.btn` rule (`styles.css`) only sets `cursor`/`font-family` — all actual button theming lives in
the variant rules (`.btn-primary`, `.btn-ghost`, `.btn-link`, `.btn-icon`, each referencing theme
tokens), per DESIGN.md's "`.btn` + a variant" recipe. Without a variant the browser's native unstyled
button chrome renders through regardless of `data-theme`. Fixed by adding `btn-ghost` to all 6
buttons, matching the file's own precedent for secondary actions (the "Remove" button already
correctly uses `btn-ghost danger`).

## Key technical detail

Two of the three bugs (text-wrap and unthemed buttons) share the same shape: a correctly-designed
**shared base class** (`.settings-sub`, `.btn`) whose narrow/undecorated default is right in its
*original* context, reused elsewhere by a component that forgot to apply the established
per-context override (`.acc-body .settings-sub`) or variant (`.btn-ghost`) the convention already
calls for. Neither was a novel CSS problem — both were catchable by checking new/reused UI against
the already-documented recipe (DESIGN.md rule #8) rather than assuming a shared class "just works."

## Manual verification script

1. Start the dev server (`uvicorn app.backend.api.app:app --host 127.0.0.1 --port 8888`); open a
   paper's Detail pane, expand METHODS → Statistics — confirm no `[Statistics | More checks]` tab
   strip, just the statcheck content directly.
2. Same panel: confirm the "WHOLE LIBRARY" statcheck intro paragraph now wraps at the panel's full
   width (not a cramped ~300px column). Spot-check Checklists/Data similarly.
3. Settings → Citation styles: confirm "Install .csl", "Import URL", "Edit source", "Duplicate"/
   "Duplicate to edit", "Check for updates", "Download .csl" all render with the app's themed
   ghost-button styling in both light and dark theme (toggled via `data-theme` for this check), not
   native browser chrome. (All three verified live via Playwright this increment.)

## Pytest

`pytest tests/test_frontend_assembly.py -q` — 53 passed (2 pre-existing tests needed updating to
match the intentional changes: `test_stale_discover_placeholder_is_removed_from_theory_accordion`
checked for a comment that lived inside the now-deleted `09_placeholders.jsx`;
`test_padding_sweep_ws_pad_on_six_workspace_tabs_only` asserted the exact old `.settings-sub` override
selector list, missing the new `.acc-body` entry). Full suite before merge:
`pytest -n auto -q` — see final run count in `changes.md`.

## Files changed

- `app/frontend/js/09_placeholders.jsx` (deleted — last remaining stub cleared)
- `app/frontend/js/35d_citation_styles.jsx` (6 buttons: `btn` → `btn btn-ghost`)
- `app/frontend/styles.css` (`.acc-body .settings-sub` override added; `.coming-soon*` block removed)
- `.claude/DESIGN.md` ("Coming soon" recipe entry updated)
- `tests/test_frontend_assembly.py` (2 tests updated to match)
- `callosum-app.html` (rebuilt)
