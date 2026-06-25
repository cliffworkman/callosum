# Increment 126 — p-curve (collection-level evidential-value check)

The first of the GRIM/p-curve "data-detective" METHODS family the user asked for (surfaced via Daniël Lakens'
automated-review catalog). **p-curve first** (lower risk — it reuses the proven statcheck p-value extractor; GRIM's
hard, low-coverage extraction is a deliberate follow-up). Given a SET of significant focal NHST results across a
user-selected set of papers, p-curve (Simonsohn, Nelson & Simmons, 2014) tests whether their p-value distribution
is **right-skewed** (→ evidential value) vs flat. **Collection-level only, never per-paper, never "p-hacked"**; the
interpretation is the user's.

## Implemented

- **`app/backend/methods/pcurve.py`** (new) — pure, no-DB, no-LLM, no-egress: `compute_pcurve(p_values)` (the
  right-skew **Stouffer** test `Z = Σ Φ⁻¹(p/.05)/√k`, a **binomial** check on the share of p < .025, and the 5
  observed bins {.01–.05} as percentages) + `run_pcurve(per_paper)` building a `PcurveResult` (with
  `IncludedTest` provenance). Edge cases: k=0 → honest empty; p≤0 or ≥.05 excluded; k<5 → `low_power`.
- **`app/backend/api/routers/methods.py`** — async `POST /methods/pcurve/run {paper_ids}` + `GET …/run/{job_id}`
  (new `api.state.pcurve_jobs` JobStore in `app.py`); `_run_pcurve_job` reuses `run_statcheck` +
  `get_chunks_for_paper` per **live** selected paper, then `run_pcurve`. **Ephemeral — no persistence, no
  migration.** Selection de-duped + capped (`MAX_PCURVE_PAPERS=1000`); empty → 422.
- **Frontend** — a **p-curve** action in the library bulk bar (`10_pdf_layer.jsx`) + minimal `40_app.jsx` wiring
  (`pcurvePapers` state + `bulkPcurvePapers`) opening a new **`29_pcurve.jsx`** modal: the framing ("collection-
  level … not a verdict … never any single paper or author"), the coverage note, a hand-rolled **SVG curve**
  (bars .01–.05 + dashed 20% null), the right-skew + binomial statistics (descriptive), the **included-tests**
  list (each opens its page at region precision), the coverage caveat, and a **credit** block (Simonsohn et al.
  2014 + a one-click **add to library** via the inc-93 `/library/import` with bundled CSL-JSON). Tokens-only CSS.

## Key technical detail

- **Reuses statcheck's exact p-values** (`StatResult.computed_p`) — no new extraction. Because statcheck rounds
  `computed_p` to 4dp, results so significant their p rounds to ≈0 are **conservatively dropped** (`0 < p < .05`),
  which biases p-curve *against* over-claiming evidential value (the safe direction). Stated in the coverage note.
- **Credit-the-lineage:** the modal credits the method paper in-context + offers a one-click library-add (bundled
  CSL-JSON → the existing import path; idempotent). THIRD-PARTY-NOTICES gained a methods-lineage section (p-curve +
  scrutiny + the Lakens catalog; statcheck's credit backfilled too).
- **Principles gate (#9): aligned** — collection-level, present-the-curve-not-a-verdict, never per-paper, never
  "p-hacked" (the A-A no-accusation veto), coverage stated, included tests inspectable, no composite score/rank.
  Declined easy path: a per-paper "evidential value / p-hacking" badge or rank. Audit `2026-06-25_pcurve.md` PASS.
- **Rule #1 watch:** `40_app.jsx` is now **590/600** — a split is overdue; keep further wiring out of it.

## Manual verification

- Hermetic (`tests/test_pcurve.py`, no egress): the math (right-skewed→significant, flat→not, left→not, k=0 empty,
  exclusion, low-power, bins) + `run_pcurve` provenance + the async endpoint (202→done, k_significant, right_skew_p
  < .05, included_tests, 422 on empty, 404 on bad job). Route-surface test updated (`test_health.py`).
- **Headed (real psych papers, no egress)** `.local/visual/drive_inc126_pcurve.py`: selected 12 papers → p-curve
  → **76 significant tests (of 219) across 12 papers, strongly right-skewed (Z = −10.98, p < .0001)**; the SVG
  curve, stats, included-tests (open page), coverage, and credit (add-to-library → "✓ added") all render;
  **0 console/page errors, 0 genai requests** (p-curve is local).

## Pytest

459 passed, 1 skipped (+10 `test_pcurve.py`). `ruff` clean; QA surface check 0 uncovered (90 API / 472 FE).
