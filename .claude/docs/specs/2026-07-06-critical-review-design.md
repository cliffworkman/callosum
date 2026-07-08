# Design — Critical-review supplement (backlog #12): the "scrutiny surface"

**Status:** design, awaiting maintainer review → implementation plan.
**Date:** 2026-07-06. **Backlog:** #12 (un-gated today by the #13 auditability-standard ratification).

## Context — why, and what prompted it

Callosum can *synthesize* a corpus (grounded, verified). It cannot yet help a reader **critically appraise** a
paper or a set of papers — surface what a skeptical reader should scrutinize before relying on the work. That is
backlog #12, and it was **gated on #13** ("how auditable is auditable enough?"), ratified this morning. So the
constraint is fixed: this is a **stronger, more opinionated AI action than a grounded summary**, and it is the
single highest Principles risk in the tool — PRINCIPLES **Example 4** territory ("*synthesis prose is the artifact
that most resembles authority; the model smooths genuine disagreement into false consensus, invisibly*").

**The load-bearing decision (maintainer, brainstorm 2026-07-06):** critical review is **NOT** a model-written
critique. The maintainer explicitly **declined the "draft critical prose" job** — the verdict-shaped path — and
chose the three *grounded-signal* jobs: **(1) vet a paper before citing it, (2) stress-test a set of papers, (4)
find weak claims mechanically.** These are one capability at two scopes, not three features.

## What it is — the "scrutiny surface" (signal, never verdict)

A critical review is **the inspectable things a skeptical reader should check, assembled — not narrated as a
judgment.** It is a *composition of grounded signals + a weak-claim detector*, presented as "what to scrutinize,"
where the human does the appraising. There is **no composite score, no "this paper is good/bad" verdict, no
model-authored critique prose.** Two clearly-separated tiers:

### Tier 1 — deterministic backbone (always shown, fully local, no egress)

Mostly *composition of signals that already exist*, gathered into one "what to scrutinize" view:
- **Methods signals** — statcheck (p-values that don't recompute), GRIM/GRIMMER, p-curve, retraction,
  open-science disclosures, the LMM / Bayes / meta-analysis reporting-completeness flags (precondition-scoped:
  only the auditors that apply to this paper). These already exist; critical review *surfaces them together*.
- **Citation signals** — the citation-concentration / overlooked-work lens (inc-229/230).
- **Cross-corpus contradiction detector (the one genuinely new deterministic piece — the heart of "weak
  claim"):** take the paper's candidate claim sentences (abstract + conclusion-section sentences, bounded),
  retrieve semantically-related passages from the *rest of the selection/library* via the vector store, run the
  **existing NLI stance classifier** (`cross-encoder/nli-MiniLM2-L6-H768`, already in `verification.py`) with the
  paper's claim as hypothesis, and surface **claims other papers in the corpus contradict**, each with its
  contradicting passage (paper, page), stance, and confidence. This is the THEORY contract's "*surface
  disagreement, do not smooth it*" turned into a signal — grounded by construction.

### Tier 2 — LLM candidate critiques (opt-in, egress-gated, marked as candidates — the AI funnel / human filter)

The model proposes **additional** critique points the deterministic detectors can't see (an overstated
conclusion, an unsupported causal leap, a missing control). Each candidate is `{concern, anchor_quote,
paper_span}` and must **pass the #13 bar to appear**: it carries a **verbatim quote from the paper** (the quote
must be literally present — the `canonical_text_contains` check), the passage it concerns (retrievable span), an
NLI stance, and a visible confidence. A candidate that can't be grounded to a verbatim span is **dropped**
(honest shortfall — silence ≠ certificate). Surfaced candidates are **never auto-trusted**: the human
**accepts** (→ persists as a finding) or **rejects** (→ remembered, never re-proposed) — the inc-259 loop exactly.

## MVP + sequencing

- **MVP = single-paper "vet" (jobs 1 + 4).** The engine + both tiers, for one paper, in a METHODS-pane section.
- **Increment 2 = multi-paper "stress-test" (job 2).** Same engine, in the multi-paper/synthesis surface, adding
  the **cross-paper conflict map** (where the selected papers disagree, grounded). Out of scope for the MVP spec.

## Where it lives / invocation / persistence

- **A new METHODS-pane section** (`registerPaneSection`, the statcheck/GRIM/LMM pattern) — it belongs beside the
  auditors it composes. Label: **"Critical read"** (not "critical review" — the label itself should say *signal,
  not judgment*; final call at build).
- **Tiered invocation:** a button computes **Tier 1 locally, always.** **Tier 2** is a *separate* opt-in action
  inside the panel, visible only when AI is enabled — the egress gate is a deliberate second click, never
  automatic.
- **Persistence:** Tier 1 recomputes on demand (like statcheck — never stale). Tier-2 **accepted** candidates
  persist to a review store (a dedicated `critical_review_candidates` table mirroring inc-259's `ma_proposals`,
  or the inc-130 `paper_findings` with a new kind — the plan decides); **rejected** ones are remembered so they
  are never re-proposed. Accepted candidates feed the existing library-wide review queue.

## Architecture (reuse-heavy)

- **NEW `app/backend/methods/critical_review.py`** — deterministic Tier 1: gather the per-paper method-signal
  producers + the cross-corpus contradiction detector. Pure/local; reuses the vector store (retrieval), the NLI
  stance classifier + `canonical_text_contains` (`verification.py`), and the existing producers.
- **NEW `integrations/gemini/critical_review.py`** — Tier 2 candidate generator, wrapped in the existing
  `EgressGated*` seam (the `summaries.py` pattern: cache inside the gate, egress consent checked outermost);
  proposes candidates → each routed through the verification bar → only passers returned.
- **NEW `app/backend/api/routers/critical_review.py`** — sibling router (`methods.py` is near the 600-cap),
  async-job pattern (mirrors acquire-oa / statcheck jobs): `POST` starts, `GET /{job_id}` polls; Tier 2 gated on
  egress; accept/reject endpoints for candidates. Mounted in `app.py`.
- **NEW `app/frontend/js/08x_methods_critical.jsx`** — the two-tier panel + candidate accept/reject; reuses the
  auditor-section + credit-block recipes.
- **Migration** only if a dedicated candidates table is chosen.

## Principles / A-A gate (rule #9 — the heavy pass; this IS the feature's justification)

- **Worked example it resembles:** PRINCIPLES **Example 4** (answering "what does the literature say about X") and
  **Example 3** (the "is it real" verdict). The misaligned path is *the easy one*: let the model write a fluent
  critical review and ship the prose.
- **The misaligned path — explicitly declined:** model-authored critique prose (the "draft prose" job the
  maintainer rejected). It manufactures authority, smooths disagreement invisibly, and gives the reader nothing
  to check.
- **The aligned design (this spec):** (a) the deterministic backbone is the source of truth (PRINCIPLES #4 —
  the model only proposes *additional* candidates, never the backbone); (b) every point — deterministic or
  candidate — carries its evidence and meets the #13 bar (#1, #8); (c) it **surfaces disagreement, does not
  resolve it** (the THEORY contract); (d) facts (deterministic signals) and candidates (LLM proposals) are
  visually + epistemically distinct (#3); (e) no composite "quality" score (#7); (f) the human accepts/rejects
  every candidate (#5, the funnel/filter); (g) egress is a deliberate opt-in second click (#10, invariant #3).
- **A-A veto check:** **no accusation of individuals** — the scrutiny surface critiques *claims and methods*, never
  authors; copy is "what to scrutinize about this work," never "this researcher." This is a hard boundary the
  copy + the candidate prompt must enforce.

## Security audit (fires: new endpoint + Tier-2 egress of library text + candidate storage)

`.claude/security-audits/2026-07-06_critical-review.md`. Threat review: Tier-2 sends the paper's text to the
provider — **gated** on the same `EgressGatedSummaryGenerator` consent path (default off; loopback = zero egress);
Tier 1 makes no external call. Input validation (paper id, bounded claim extraction, candidate caps); candidate
storage is local; no new secret; output encoding (candidate text rendered by React). Negative paths: egress-off →
Tier 1 only, Tier 2 refuses; oversized/malformed → 422. End PASS.

## Testing

- **Cross-corpus contradiction detector:** a seeded paper whose claim another seeded paper contradicts → surfaced
  with the contradicting passage + stance; a claim nothing contradicts → not surfaced; grounding present.
- **Tier-1 composition:** the applicable method signals for a paper appear; non-applicable auditors don't render.
- **Tier-2 candidate bar:** a candidate with a verbatim anchor passes; one whose quote isn't in the paper is
  dropped (the `canonical_text_contains` gate); accept → persists; reject → not re-proposed.
- **Endpoint:** egress-off → Tier 1 only + Tier 2 refuses with the honest message; egress-on (fake generator) →
  candidates returned + verified.
- **Principles guard:** a structural/copy test that no composite score is emitted and no author-directed language
  appears (the no-accusation boundary).

## Gates checklist (rule #9/#10/#11 + audit + credit)

Principles/A-A (above); **security audit** (above); **QA route** (new `/critical-review/*` API + the panel);
**experience pass** (the deadline citer vetting a paper before citing); **credit-the-lineage** (the NLI
stance-detection lineage is already credited; the contradiction-as-signal idea is native — no new paper to
credit, note in the audit); **help corpus** ("Critically reading a paper"); DESIGN (reuse recipes).

## Out of scope (MVP)

The multi-paper stress-test + cross-paper conflict map (increment 2); model-authored critique prose (declined,
permanently — the verdict path); any composite quality score or ranking; author-directed judgments (veto).
