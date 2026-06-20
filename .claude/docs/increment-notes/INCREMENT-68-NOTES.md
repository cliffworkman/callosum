# Increment 68 Notes — Canonical `.btn-*` button classes (DESIGN.md §3 #5)

Addressed the standing design-debt item: ~10 near-duplicate button blocks each re-typing the same
border/radius/hover. Introduced a canonical button layer and consolidated the cleanly-identical duplicates —
**CSS-only, zero visual change, no JSX touched.**

## What changed (`app/frontend/styles.css`)
- **Canonical classes** (the single source of truth; new buttons use these): `.btn` (base: cursor +
  font-family), `.btn-primary` (accent fill), `.btn-ghost` (outline, hover accent), `.btn-link` (text link),
  `.btn-icon` (transparent icon), and a `.danger` modifier (red `--danger`, per DESIGN §4).
- **Consolidation by selector grouping** — the historical ad-hoc classes were folded into the canonical
  rules so the recipe is defined once, **without changing any className in the JSX** (`.axis-link` alone has
  dozens of call sites — a className migration would be huge and risky):
  - primary: `.axis-btn` + `.synth-actions button` (the latter keeps its larger-padding/font **delta**).
  - ghost: `.pginate button`.
  - link: `.axis-link` (the legacy `.axis-link.axis-danger` stays amber `--flag`, separate from the canonical
    red `.btn-link.danger` — the §3 #1 leftover, pending migration).
  - icon: `.axis-icon-btn` (keeps its amber danger-hover; its `#e6cdb4` was tidied to `var(--flag-line)`).
- **Not migrated (deferred — value-shifting):** the size-/color-divergent ghost & icon buttons
  (`.axis-sort`, `.axis-new`, `.pdf-zoom button`, `.source-jump`, `.history-delete`, `.hl-editor-actions
  button`, `.axis-x`, `.frame-tab-close`) differ in radius/padding/bg/hover, so folding them in would shift
  their look. Their migration is a JSX-className change per button, deferred like §3 #6.

## Why selector-grouping (not className migration)
The risk in a button-DRY pass is silent visual regression. Grouping the existing class names into the
canonical rules — only where **every grouped property is byte-identical** to the original (hand-verified per
variant) — eliminates the duplication with near-zero blast radius and no JSX churn. The canonical `.btn-*`
classes exist for new buttons; migrating existing components' classNames is the documented incremental step.

## Verification
- **No Python changed → pytest unchanged at 235.** Frontend rebuilt (`callosum-app.html`).
- **Live E2E** (`.local/btn_dry_e2e/`): injected each canonical class and read `getComputedStyle` —
  `.btn-primary` = accent bg / white / radius 7 / weight 600 / pad 5×11; `.btn-ghost` = `--bg` / `--ink-2` /
  `--line-2` border / radius 7; `.btn-link` = borderless / accent / transparent bg; `.btn-icon` = transparent
  solid border / `--ink-3` / radius 5. A real legacy `.synth-actions button` shares the primary recipe + its
  preserved 7×11 sizing delta. **0 console errors.** (Computed-style equality is a stronger proof than a
  screenshot.)
- DESIGN.md updated: §2 Buttons now documents the canonical classes + which legacy classes are grouped vs
  still-divergent; §3 #5 marked **PARTIAL** with the remaining list. No audit gate (styling only); no
  help-corpus change (buttons look identical).

## Deferred (noted)
- Migrate the divergent ghost/icon buttons by changing their JSX className to `.btn-*` (value-shifting — do
  per button). Reconcile `.axis-link.axis-danger` amber → red `--danger` (DESIGN §3 #1) when those buttons
  migrate. The middle radius scale (§3 #6) is the related open item.
