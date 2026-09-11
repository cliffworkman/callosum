# Increment 584 — Explain how Ask reads a question (+ a broadening hint) (GitHub issue #30)

## Context

Synthesize → Ask has real query-shape sensitivity that was invisible to users. `query_planner.py`'s
`classify_breadth` escalates a question to broad treatment only when it **names several things**
(enumeration: commas + "and" ≥ 4) or uses framing phrases *and* clears a length floor (≥40 chars). So a
short, semantically-broad question like **"What does my library say about brains?"** (38 chars, no list)
routes to a single focused lookup and can return a narrower answer than intended. Issue #30 asked to
**disclose** this honestly — a "?" explainer near Ask — plus (its open question, which Cliff chose to
include) a **dynamic hint** when a short/open-ended question is detected. Explicitly *not* canonizing
implementation quirks (no "facets/breadth gate/planner" jargon, no char/comma thresholds in user-facing
text) into rules users would later have to unlearn.

This is disclosure about system behavior, not a claim/signal about the literature, so the Principles gate
isn't strongly triggered — but its honesty spirit is the design: a short/quiet answer never implies the
library lacks evidence; describe intent, not quirks; don't over-claim broad detection.

## Implemented

- **`summarization/query_planner.py`** — new pure, no-I/O `broadening_hint_applies(question) -> bool`:
  True for a **short** question (reusing `_MIN_QUESTION_CHARS`, not a new constant) that shows no breadth
  signal — the short/open-ended zone the guidance is about. Colocated with `classify_breadth` so the hint
  and the real routing can never drift, and the length quirk lives **only** here (never in user-facing
  text or the frontend). A longer focused question routes narrow but is deliberately **not** hinted.
- **`api/routers/summaries.py`** — new `POST /summarize/query-shape` → `{routing, show_broadening_hint}`.
  Deterministic and local: runs **only** `classify_breadth`/`broadening_hint_applies` — no LLM, no egress,
  no DB — so the UI can debounce it live. `QueryShapeRequest.query` is length-capped (4000) at the boundary.
- **Help corpus (`help/help_content.md`)** — new section `<!-- section: ask-query-shape -->` "How Ask
  reads your question": naming aspects helps; focused questions work as-is; short open-ended questions are
  **still-improving** (the "brains?" example); a short/quiet answer is **not** proof of no evidence; and a
  "where this is headed" note (Callosum aims to infer scope from natural questions — this describes today).
  Single source of truth: the modal renders this exact section, and the Help center/assistant cover it too.
- **`frontend/js/20_synthesis.jsx`** — a `.btn-link` **"How Ask reads your question"** trigger in the
  actions row opens `AskGuideModal` (reuses the canonical `axis-modal` recipe + `help-body`; fetches
  `/help/corpus`, renders the `ask-query-shape` section; Escape/backdrop/× to close; graceful fallback).
  A debounced (~400ms) `POST /summarize/query-shape` on a query-scope, no-section question drives a muted,
  **dismissible** `.synth-nudge` broadening hint with a "Learn more" that opens the same modal. **Zero new
  CSS** — every class reused.
- **Rule #1 split:** #30 would have pushed `20_synthesis.jsx` over the 600-line cap, so its three
  presentational components (`SummaryHistory`, `SummarySentence`, `CitationCard`) moved verbatim to a new
  `20c_synthesis_results.jsx` (516 + 145 lines; the shared-IIFE function-declaration hoist, same precedent
  as 20b/19c/35b). `20b_summary_groups.jsx`'s `GroupedSummarySentences` still calls `SummarySentence`
  unchanged.

## Key technical detail

The dynamic hint's faithfulness comes from **reusing the live backend classifier via an endpoint** rather
than reimplementing its thresholds in JS. The frontend never learns the 40-char floor; it only asks the
backend "show the hint?" and the backend answers from the same code that does the real routing — so the
hint can never disagree with what actually happens, and no quirk is frozen into user-facing text. The
hint is a strict subset of narrow-routed questions (a test asserts `broadening_hint_applies ⇒
not classify_breadth`), so it never contradicts routing. The irreducible ambiguity — a short *focused*
question ("Smith 2020 sample size?") looks identical to a short *broad* one to the deterministic system —
is handled by wording that reads correctly for both ("Want a broad overview? …") and is dismissible.

## Manual verification script

- `pytest tests/test_query_planner.py` (17) — `broadening_hint_applies` True for "brains?", False for
  empty/broad/long-focused, and the subset-of-narrow invariant.
- `pytest tests/test_summaries.py -k query_shape` — the endpoint returns the right shape for short-open/
  broad/empty and 422s an over-long body (no provider call).
- `python tools/build_frontend.py` → `pytest tests/test_frontend_assembly.py` (87). Line budget OK (599
  files under cap). QA route 55 extended (step 0 + a standing assertion); `build_surface_map.py check` OK.
  Both ruff gates clean. Security audit `2026-09-11_query-shape-endpoint.md` PASS.
- **Live UI — DEFERRED (flagged, not claimed):** open Ask → click "How Ask reads your question" → modal;
  type "What does my library say about brains?" → the broadening hint appears; "Learn more" opens the
  modal; Dismiss hides it; a long enumerated question shows no hint. Needs the app running with AI enabled
  and ideally the ~200-paper testing DB (not on this machine). The endpoint/logic + assembly tests cover
  the mechanism regardless.

## Experience pass (rule #11)

Inhabited the broad-asker: the hint fires exactly for the short/open-ended zone (not on long, deliberately
scoped questions), is muted and dismissible, and its "Learn more" reaches the full corpus guidance — it
serves rather than nags. The residual risk is a short *focused* asker seeing it once; the wording stays
accurate for them and Dismiss suppresses it for the session. Trigger is deliberately conservative and
**tunable** if real use shows noise. Honesty held: the guidance and hint both state a quiet/short answer is
not proof the library lacks evidence, and neither frames phrasing as a requirement.

## Pytest

`tests/test_query_planner.py` 17 passed; `tests/test_summaries.py -k query_shape` 1 passed; frontend
assembly 87 passed. Ruff clean; line budget OK; QA coverage OK.
