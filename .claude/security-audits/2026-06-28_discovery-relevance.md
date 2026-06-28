# Security + Principles review — discovery axis-relevance highlight (SP1b), inc 185

**Date:** 2026-06-28
**Feature:** `app/backend/discovery/relevance.py::score_axis_relevance` + `POST /discovery/relevance`
(`routers/discovery.py`) + the `.discover-relevance` badge in `30d_discover.jsx`. For each search result, score its
title+abstract against the user's AXIS embeddings and return the best-matching axis + similarity for items that clear
that axis's cutoff — the frontend **highlights** those rows **within the complete list**. Backlog #28 SP1b.

**Audit gate triggers:** a new API endpoint. (No new external fetch, no new ingestion path, no new dependency — numpy
is already a dep.)

## Principles alignment gate (rule #9) — this is a SIGNAL feature

It produces a relevance judgment relating an external paper to the user's axes. Principles touched + how honored:

- **#2 signal not verdict / #6 silence is not a certificate.** The badge is "likely: <axis> · match 0.NN" — a labeled
  hint, not "this IS about X." A below-cutoff item carries **no badge**, and that means *no strong axis match*, **not
  "irrelevant"** — the row is still shown in full and savable. (Encoded structurally: `score_axis_relevance` only
  *adds* entries for clearing items; it never marks anything "rejected.")
- **#3/#5 the human is the filter; the AI is the funnel.** The highlight never hides, filters, or reorders — the
  complete `/discovery/search` list is rendered in its original order; relevance is overlaid best-effort (if the call
  fails or there are no axes, the list shows with no badges). The user still decides what to Save.
- **#7 no opaque composite score.** The "match" is **one cosine similarity**, rounded to the same 2 decimals an axis
  card shows (so a result's match number is directly comparable to a paper's axis confidence) — not a black-box
  "relevance score" blending multiple signals.
- **The deliberately declined misaligned path** (named in the design spec): a filtered/AI-curated "here's what
  matters" list that hides or reorders-away the rest. Declined — **the complete list is the product; relevance is a
  non-destructive highlight.**

Resembles the axis scoring/tiering (inspectable confidences, the same cutoff semantics) + inc-156 citation-suggest
(the match is the reason; candidates the user picks). **A-A vetoes:** no accusation (it's the user's *own* axes; the
score is shown), no paywall, no opaque score — none in play. **Aligned.**

## Security threat review

- **Input validation (rule #4):** `RelevanceRequest` (pydantic) bounds `items` to **1..50**; each `RelevanceItem`
  bounds `dedup_key` 1..400, `title` ≤2000, `abstract` ≤20000. Empty/oversized → **422**. The handler builds
  `text = f"{title} {abstract}".strip()` (no interpolation into SQL or any command).
- **Injection (rule #3):** the only DB access is `select(axes).where(axes.c.kind != MY_PUBLICATIONS_KIND)` — a
  bound-param read; no request data reaches SQL text. **No DB write** (a pure read — axis vectors are embedded fresh
  in-process, matching the scorer's text prep so the numbers agree with the axis cards).
- **SSRF / external calls / egress (invariant #3):** **none.** Scoring is entirely local — `embedding_model.encode_texts`
  over the user's own axis text + the items the client already holds. No host is contacted; the QA route asserts **0
  genai-host requests**. This is not the Gemini gate.
- **Secret handling / supply-chain:** none introduced; numpy already a dependency.
- **Resource caps:** items ≤50; axes are the user's own (small); cosine is one matmul over short vectors. The heavy
  embedding model is loaded once + cached on `app.state` (`_discovery_model`; an injected model wins for tests),
  mirroring the inc-156 suggest endpoint.
- **Graceful degradation:** no axes / axis-less library → `{}` (no badges); the frontend treats relevance as
  best-effort, so a failure or empty map never breaks the (already-rendered) complete list.

## Negative-path checks
- Empty `items` → 422 (`test_relevance_endpoint`); below-cutoff item omitted (`test_relevance_respects_per_axis_cutoff`);
  My-Publications axis excluded (`test_relevance_excludes_my_publications_axis`); no axes / no items → `{}`
  (`test_relevance_no_axes_or_no_items`); the match equals the displayed-precision cosine
  (`test_relevance_returns_best_axis_above_cutoff` → 1.0). Headed: exactly 1 badge on the matching row, the complete
  list of 3 still shown, 0 genai (`drive_inc185_relevance.py`).

## Decision

**Security Audit: PASS.** A local, read-only, bounded signal endpoint; no egress, no DB write, bound-param read.
**Principles: aligned** — a non-destructive highlight (augment, never filter), a labeled single-similarity signal,
silence-≠-certificate, the human still decides; the misaligned "curated list" path is declined.
