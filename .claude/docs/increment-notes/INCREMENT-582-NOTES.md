# Increment 582 — verified-claim responsiveness band (findings vs study-context)

## Context: what this is, and what it deliberately is NOT

Broad (faceted, inc 581) Ask verifies claims correctly, but the *verified* set mixes substantive findings
with thin "study-context" framing — sentences that restate a paper title, a table caption, or a
"topic was studied" statement. These pass the unchanged verifier (exact quote + NLI support) yet answer the
question poorly. Inc 582 labels each already-verified broad-Ask claim `finding` / `descriptive` / `unknown`
so the UI leads with findings and groups descriptive material under a **Study context** heading. It is a
**presentation layer only** — it changes no verification status, no score, no threshold, hides nothing,
promotes nothing, and adds no provider call, schema, or migration. `descriptive` means *verified but lower
answer-value*, never *lower confidence*.

**It is a separate quality fix, not a workaround for a verifier problem** (see below).

## The rejected verifier experiment that preceded this (record, do not re-attempt without new evidence)

A different candidate for this slot was to **remove `retrieval_confidence` as a necessary condition for
VERIFIED** (since VERIFIED already requires `quote_confidence==1.0`, that is literally removal of the retrieval
gate from the verified decision). It was put through a pre-registered evidence gate on the **complete 12-row
flip universe** (every persisted citation with `quote=1.0 ∧ support≥0.55 ∧ retrieval<0.70`, across the demo DB +
the frozen baseline copy). Blind support adjudication: **10 SUPPORTED / 1 UNSUPPORTED / 1 UNRESOLVED** →
**gate FAILED**. The two counterexamples (both on chunk 32651) reassign the subject/scope of the source ("MCI
is associated with LLD…" from a source that only says *depressive symptoms → cognitive decline in MCI
populations*), and the whole-chunk retrieval score (0.64/0.68) is currently the **only** gate blocking them —
the NLI support gate false-positived (0.95/0.76). So whole-chunk retrieval demonstrably still prevents a real
NLI-support-false-positive class; wholesale removal is unsafe. Full analysis:
`.claude/docs/research/2026-09-07_ask-verification-next-increment.md` (PHASE-GATE ADDENDUM). That research
stands; inc 582 addresses the orthogonal *answer-value* problem instead.

## Implemented

- **`app/backend/summarization/responsiveness.py`** (new, pure — no I/O/model/score):
  `classify_responsiveness(claim_text, cited_chunk_types=None, cited_evidence_roles=None) ->
  "finding"|"descriptive"|"unknown"`. Classifies the **main assertion**: a research-activity frame
  ("Research investigated the relationship between X and Y", "This study examined Z") is `descriptive` even
  though result vocabulary appears as the *object* of the activity verb; a reporting/result verb ("found",
  "showed", "observed" …) overrides the frame ("This study **found** greater X" → `finding`); a stated result
  (direction/comparison/association-as-predicate/prediction/significance) with no descriptive frame →
  `finding`; else `unknown` (fail open, treated as a finding for grouping). Evidence-metadata params are
  **reserved** (claim semantics are primary; evidence may never *manufacture* a finding) and unused in v1.
- **`app/backend/summarization/faceted_pipeline.py`**: `_assemble` now also returns a `responsiveness` list
  built **after** final ordering (so index == persisted ordinal); `summarize_faceted` rides it into
  `extra_scope_ref["responsiveness"]` (same extensible `scope_ref_json` blob as `coverage` — no migration). No
  reorder of ordinals, no change to verified/flagged/caps/coverage.
- **`app/backend/api/routers/summaries_response.py`**: `_responsiveness_from_ref` (mirrors
  `_coverage_from_ref`) + a `responsiveness: str|None` field on `SummarySentenceResponse`, mapped by ordinal.
  Narrow/paper/cluster/imported summaries have no key → `None` → response byte-identical to before.
- **Frontend**: `GroupedSummarySentences` extracted to new `app/frontend/js/20b_summary_groups.jsx` (rule #1 —
  the added lines pushed `20_synthesis.jsx` to 611; shared-IIFE hoist keeps it callable from `SynthesisPane`).
  When `responsiveness` is present (broad only), the **unchanged verified set** splits into **Findings** and
  **Study context** — both use the same `summary-section verified` chrome (study-context is verified material,
  never amber), no new CSS/color. Narrow Ask (no `responsiveness`) renders exactly as before ("Verified").

## Key technical detail

The retrieval gate uses the *whole chunk* while support uses the *precise quote* — that asymmetry is the root of
both the false-negatives (rejected experiment) and the thin-verified problem this increment groups. Here the
label is claim-semantics-only and **fail-open**: the ship priority is *false descriptive demotions ≈ 0* (never
demote a genuine finding), accepting false negatives. A leading-adjective research frame ("Longitudinal studies
have investigated…") currently falls to `unknown`→Findings rather than `descriptive` — a deliberate acceptable
false negative, not expanded pre-release to avoid re-freezing a validated rule.

## Validation (frozen, read-only — no provider reruns for the gate)

Classifier run against **80 real persisted verified claims across 3 disjoint artifacts** (demo DB 21 +
frozen baseline copy 49 + frozen closeout new-answer 10; closeout 0-overlap with baseline): **51 finding /
19 unknown / 10 descriptive, 0 false descriptive demotions** (every descriptive row adjudicated genuine
topic-was-studied/methods-employed framing). The "4 known-thin" claims live in the closeout artifact, disjoint
from the demo+baseline universe — validated against the real rows, not retyped probes. Frozen accounting SHA-256
`339d11fc9b8ce94dbce484b505186d7fcf9b54eeb80f4c0566a2e34dccee7d75`.

## Manual verification script

1. Isolated ephemeral backend on a **copy** of the demo DB (`:8899`, Gemini), demo `:8888` untouched.
2. Real broad Ask ("Synthesize the neurobiological systems implicated in late-life depression, covering
   serotonergic function, amyloid pathology, glucose metabolism, gray matter structure, and other …") →
   `status=done`, 5 facets, **every sentence carried a responsiveness label**; verified band = 3 findings +
   1 study-context, flagged unchanged; **0 backend errors/exceptions in the log**. Confirmed no verified
   sentence was missing a label, and the clearest thin claim ("Comparisons … have been made") → `descriptive`.
3. Bundle rebuilt (`build_frontend.py`); grouping code present in `callosum-app.html`. A full browser
   screenshot was **not** run (to conserve the session); the render path is a simple deterministic split over
   the live-verified response contract + `test_frontend_assembly` — flag if a pixel check is wanted.

## Pytest

`tests/test_responsiveness.py` (new — the 12-case matrix incl. the 5 real regression fixtures from today's Ask:
"Research investigated the relationship…"→descriptive, "This study found…"→finding vs "This study examined…"
→descriptive, "…influences…"→finding) + extended `tests/test_faceted_synthesis.py` (responsiveness alignment,
flagged-never-promoted, `_responsiveness_from_ref` reader). Green: `test_responsiveness` + `test_faceted_synthesis`
(37), `test_summaries` (with the two, 54), `test_summarization`+`test_reverify` (17, verifier/narrow-path
unchanged), `test_frontend_assembly` (87). Ruff format+check, line-budget, tach all pass.

## Next-arc pointer (documentation only — NOT in scope here; do not broaden inc 582)

Today's broad Ask exposed that **topic-facet decomposition is lossy for relational, multi-part questions**
(a "relationship between X and Y" facet retrieves X- and Y-ish chunks but does not preserve the *requested
relationship* or measurement detail). Next architectural research should investigate **answer obligations /
answer contracts** rather than topic facets: preserving requested relationships + measurement details;
carrying **question provenance** alongside evidence provenance; multiple retrieval formulations per obligation;
evidence-to-obligation triage; a bounded gap-directed second retrieval; synthesizing verified findings into
**question-aligned sections**; and local Qwen as a possible semantic control plane for both local and cloud
generation. This is a pointer, not a commitment.
