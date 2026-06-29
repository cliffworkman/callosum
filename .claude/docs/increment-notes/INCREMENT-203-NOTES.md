# Increment 203 — activate the dormant `contradicted` verification status (backlog A9, close-out)

## Implemented

The first **close-out** from the competitive-benchmark revisions (folded inc 202-grooming): the verification spine
could flag a claim as *not-sufficiently-supported* but **could not surface that a cited source actively disagrees** —
the single most consequential class of citation error a verify-everything tool exists to catch. The schema already
defined `contradicted` (`CITATION_MAPPING_STATUSES`) and the NLI CrossEncoder already produces a contradiction
probability; only the extraction + status + render were missing. Now wired, **scoped narrowly** + **signal, not
verdict**.

- **`app/backend/summarization/verification.py`:**
  - `VerificationConfig` gains **`contradiction_threshold = 0.55`**.
  - `NLISupportScorer.support_and_contradiction(sentence, passage) -> (support, contradiction|None)` reads **both**
    probabilities from the **one** NLI softmax the support path already computes (no extra model call); `.score()` is
    now a thin wrapper returning entailment. The embedding fallback yields contradiction `None` (no signal — silence,
    not a guess). New helpers `_support_and_contradiction` + `_contradiction_index` (standard NLI order
    `[contradiction, entailment, neutral]`; honors the model's `id2label`).
  - `LocalCitationVerifier._support_and_contradiction()` duck-types the scorer (`getattr(..., "support_and_contradiction")`)
    so a plain `SupportScorer` (the embedding fallback or a test double) still works — contradiction simply `None`.
  - `_status()` checks contradiction **first**: returns **`contradicted`** when `contradiction >= threshold` **and**
    `contradiction > support` (conservative — a confident contradiction that genuinely dominates entailment; this
    overrides what would otherwise be `verified`). `VerificationResult.contradiction_confidence` carries it.
- **Frontend (`20_synthesis.jsx` + `styles.css`):** a 3-way `citeStatusClass()` — `contradicted` is its **own**
  state (pill text "⚠ source disagrees", red `.cite-status.contradicted` using the `--danger` family) rather than
  lumped into amber "flagged". DESIGN.md records the narrow exception (red on **one non-interactive status pill**;
  rule #8).
- **No migration:** `contradicted` is a valid status string → it flows through `citation_mappings.status` → the
  response → the frontend automatically. The contradiction *number* isn't persisted/displayed (the status + the
  existing quote/page/support are the evidence); a number display is a noted follow-on.

## Key technical detail

The contradiction probability was already being computed — the support path softmaxed all three NLI classes and then
**discarded** contradiction (`_entailment_confidence` picked only the entailment index). So this is genuinely a
completeness fix, not a new model call: `support_and_contradiction` reads indices for both entailment and
contradiction from the same row. The status precedence puts contradiction **before** verified (a source that
disagrees is `contradicted` even when retrieval + quote are high — the quote matches *because* the passage is on-topic
and disputes the claim), guarded by `contradiction > support` so a merely-ambiguous claim isn't flagged as disputed.

**Principles gate (rule #9) — aligned:** activates an *already-designed* status; **signal not verdict** (#2/#3) — the
contradicted citation shows its verbatim quote + page + confidence and says "this passage contradicts this claim,
your call," never "this claim is false"; strengthens invariant #1 (the most consequential citation error is now
catchable); evidence always shown (#4). The aligned shape was pre-decided with the maintainer (the benchmark-revisions
doc, §A9).

## Manual verification script

`HF_HUB_OFFLINE=1 python -m pytest tests/test_nli_support.py -q` → 10 passed, incl. the 3 new: the scorer reads both
probabilities from one softmax; `_status` returns `contradicted` only when a confident contradiction dominates support
(and never without a contradiction signal); an end-to-end `summarize_scope` with a contradicting fake scorer →
the cited sentence's status is `contradicted`, the sentence is flagged, and `citation_mappings.status` persists
`contradicted`. **UI:** a contradicted citation renders the red "⚠ source disagrees" pill with its quote/page intact
(the live model's real contradiction behavior is the maintainer's eyeball — needs egress + a genuinely-contradicting
source; the pure logic + status flow are proven).

## Gates

- **pytest:** full suite green — **712 passed, 1 skipped** (+3 `tests/test_nli_support.py`).
- **ruff** check + format clean; frontend rebuilt (`callosum-app.html`).
- **QA surface unchanged** — 132/132 API + 661/661 FE, 0 uncovered (a status-class variant, not a new element);
  `route_55_synthesis_verification.md` gained a `contradicted` = signal-not-verdict standing assertion.
- **Audit:** no new endpoint/egress/migration/dependency → no audit-gate trigger; the Principles gate ran (above).
- **DESIGN.md** records the narrow red-on-a-status-pill exception (rule #8). **Help corpus** updated (synthesis
  section + the top-level evidence-workbench line; `HELP-DOCS-SYNCED` → 203).
- Also swept two stray `tests/*.tmp.*` atomic-write orphans (rule #5).

## NEXT (continuing the close-out pass)

The next benchmark-revision close-outs: **A10** (carry "hide uncertain" through to the library-pane axis-contents —
a straight bug; *shown = summarized*), **A8** (verify the synthesis scope label vs the inc-153 coverage readout),
then the low-cost build-now items (**A1** saved searches, **A5** color tags/ratings, **A6** drag-into-axes, **A3**
full-text PDF search). The deferred B-items (MCP server, citation-context classifier) + **A7 Curated Axis** are
larger, their own design passes.
