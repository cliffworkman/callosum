# Increment 86 — Axis re-score line-wrap fix + button-cleanup resolution

Two UI-polish chores (frontend-only: `styles.css` + `.claude/DESIGN.md`; no Python).

## Implemented
- **Fix the axis re-score line wrap.** The re-score control row (`Re-score:` · Cutoff slider · button · 👁)
  wrapped badly in narrow/expanded axis cards. Changed `.axis-rescore-row` to `flex-wrap: nowrap` and made the
  **cutoff slider the flex item that shrinks** (`.axis-cutoff { min-width: 0 }` + `.axis-cutoff-range { flex: 1;
  min-width: 36px }`, replacing its fixed `width: 84px`); the label, button, and value are `flex: none` so they
  keep their size while the slider absorbs the squeeze — everything stays on one line at any sidebar width
  (180–600px).
- **Button cleanup (DESIGN §3 #5) — resolved, deliberately.** On review, the "remaining divergent buttons"
  (`.axis-sort`, `.axis-new`, `.pdf-zoom button`, `.source-jump`, `.history-delete`, `.hl-editor-actions
  button`, `.axis-x`, `.frame-tab-close`) are **not near-duplicates** — each is an intentional distinct variant
  (a tiny inline `<select>`, compact toolbar controls, a green "+", borderless symbol-× closes with flag hovers,
  small special-hover deletes/jumps). Folding them into the full-size `.btn-ghost`/`.btn-icon` recipe would
  **enlarge them + change their hovers** (a value-shift, contra "consolidate, don't redesign") for ~no DRY gain.
  So they're **kept as documented intentional exceptions** (DESIGN §2 + §3 #5 marked RESOLVED). The one safe,
  zero-change unification applied: **every hardcoded `border-radius: 5px` → `var(--radius-sm)`** across
  `styles.css` (the dominant "messy middle" radius; `--radius-sm` *is* 5px → no visual change), advancing
  DESIGN §3 #6.
- Rebuilt `callosum-app.html`.

## Key technical detail
The radius replace is provably zero-visual-change (`--radius-sm: 5px`, theme-invariant), so it's a pure token
consolidation, not a restyle. The button "migration" was reframed from a blind className swap (which would have
value-shifted intentional compact controls — unverifiable without a browser this session) into the correct
engineering outcome: **decide + document** that these are distinct-by-design variants, and unify only what's
safe (the radius vocabulary). New buttons still use the canonical `.btn-*` classes.

## Manual verification script
1. Hard-refresh (Ctrl+Shift+R).
2. Expand an axis card and narrow the sidebar — the re-score row stays on **one line**, the slider shrinking
   rather than the controls wrapping.
3. Eyeball the small controls (axis sort select, PDF zoom, the green "+", × closes, history delete, source
   jump) — they should look **unchanged** (only their corner radius is now token-driven, identical 5px).
   _(Visual check delegated to the user — no in-repo browser automation this session.)_

## Pytest
**380 passed, 1 skipped** — unchanged (frontend-only; no Python touched). No migration, no endpoint, no egress.
DESIGN.md §3 #5 → RESOLVED; §6 advanced (5px tokenized).
