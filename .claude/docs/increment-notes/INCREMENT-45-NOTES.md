# Increment 45 Notes — Adjustable assignment cutoff ("gain") + axis-card redesign

Replaces inc-39's relative natural-break badge (systematically too exclusive) with an **absolute,
per-axis, user-adjustable cutoff** (default 0.35), and redesigns the axis card around it: icon buttons +
a circular count badge on the card, and the Re-score row reduced to a cutoff flipper + button.

## Implemented

**Backend**
- **Migration `0003_axis_scoring_gain`** — nullable `axes.scoring_gain` FLOAT (idempotent, additive;
  NULL = "use `DEFAULT_AXIS_CUTOFF`"). `schema.py` axes table updated. Auto-applies on startup.
- **`axis_scoring.py`** — the badge is now absolute: ASSIGNED = `similarity >= cutoff`, UNCERTAIN =
  `[AXIS_FLOOR(0.20), cutoff)`, below floor not stored. Unified the scoring paths and factored a shared
  `_never_empty_uncertain` fallback (now also serves the absolute/supervised path); never-empty is gated
  to the absolute mode so `largest_gap`/`top_n` keep recording nothing when nothing qualifies. The
  `natural_break` mode + its utility/test remain as a supported alternative.
- **`routers/axes.py`** — `DEFAULT_AXIS_CUTOFF=0.35`, `AXIS_FLOOR=0.20`, `CUTOFF_MIN/MAX=0.20/0.60`;
  `_axis_config(cutoff)` builds an absolute config; `SUPERVISED_AXIS_CONFIG` is now the default absolute
  config. `POST /axes/{id}/score` accepts optional `AxisScoreStartRequest{gain}` (validated + clamped),
  threads it into the job, and **persists** `axes.scoring_gain`. `axis_clusters` re-tiers on read using
  the axis's cutoff (assigned = stored confidence ≥ cutoff). `AxisResponse.scoring_gain` exposes it.

**Frontend** (`15_axes.jsx` + `styles.css`; rebuilt `callosum-app.html`)
- Axis **card**: ✎ edit (opens the modal, does NOT expand), ＋ add (auto-expands + opens the add-paper
  picker), 🗑 delete (confirm) — small icon buttons with `stopPropagation`; the paper count is a
  **circular red badge** (white text). The quickname wraps only for long titles.
- Expanded body: the lone **Re-score row** — `Re-score:` · a **cutoff flipper** (`AxisCutoffFlipper`,
  range 0.20–0.60, preset to the axis's `scoring_gain`, labelled "Cutoff") · the Re-score button (POSTs
  the chosen gain). Removed the inline edit/add/delete actions and the relative-tiers tip.
- The **relative-tiers tip** moved to **`.claude/HELP.md`** (in-app help viewer is deferred).

## Key technical detail — why absolute now, and the systematic bias it fixes

Inc-39 chose relative natural-break because absolute 0.5/0.7 assigned nothing (then-max ~0.37). But the
largest-gap heuristic cuts at the biggest gap, which on real axes' **smooth similarity declines** sits
near the top — so it assigned only the top 2–6 (resting-state: 2 of 39). Inc-44's term curation also
raised similarities to 0.49–0.57. Empirically (replaying the live DB), an absolute **0.35** cutoff assigns
the relevant ~half consistently across all three axes. The cutoff is **per-axis, persisted, and
user-adjustable** (default 0.35, recalibratable; eventual home = a Settings increment). Existing axes
re-tier at 0.35 on the next read — no re-score needed (confidences ≥0.20 are already stored).

## Manual verification script
1. Restart uvicorn (backend + migration) and open `/` (hard-reload).
2. Existing axes should now show **more** ASSIGNED papers (re-tiered at 0.35) without re-scoring.
3. On an axis card: ✎ opens the edit modal (no expand); ＋ expands + opens the add-paper picker; 🗑
   deletes (confirm); the count is a red circular badge.
4. Expand an axis → the Re-score row shows a **Cutoff** slider (default 0.35). Drag it lower → Re-score →
   more papers become ASSIGNED; the value persists (reopen shows it; survives reload).

## Verification
- **pytest: 149** (recalibrated the fake model's "borderline" → cosine 0.30 (uncertain band); added
  `test_axis_cutoff_is_adjustable_and_persists`; decoupled the natural-break unit test from SUPERVISED;
  bumped head-revision assertions to 0003).
- **Live E2E** (`.local/axis_gain_e2e/`): card icons + red badge; ✎ no-expand; ＋ expands + picker; flipper
  default 0.35; set 0.25 + Re-score → `scoring_gain` persists 0.25 and presets after reload; tip gone;
  **0 console errors**. Migration 0003 auto-applied.
- **Security audit:** `.claude/security-audits/2026-06-19_axis-gain.md` — **PASS**.
- Line caps: `axis_scoring.py` 588, `axes.py` 466, `15_axes.jsx` 378 — all < 600.

## Backlog
Queued: in-app **HELP viewer**, **Settings UI** (the cutoff default + light/dark), **terms-as-first-class**
field, **B′ eyeball toggle** (hide/show UNCERTAIN), and the rest (tier-tag ✓-confirm, library focus-mode,
multi-select/dedup/merge, synthesis split + editable Details + DOI re-search).
