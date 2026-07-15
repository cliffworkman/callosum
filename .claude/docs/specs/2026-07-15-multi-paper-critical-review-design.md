# Multi-paper (set) critical review — design spec (backlog #12, "stronger" mode)

**Date:** 2026-07-15 · **Status:** design approved, pending spec review · **Track:** backlog #12 (gated; un-gated by the ratified #13 bar)

## Context

The **single-paper** critical read shipped in inc 266: a METHODS-pane surface where Tier-1 (local, deterministic)
composes a paper's stored method signals + the cross-corpus contradiction detector (`find_contested_claims` — the
paper's claims that *another corpus paper* contests, via local NLI), and Tier-2 (opt-in, egress-gated) has the LLM
*propose* critique candidates admitted only through the **#13 verbatim bar** (`verify_candidates`:
`canonical_text_contains` + local NLI stance + confidence + signature; human accept/reject).

Backlog #12's remaining half is a **stronger, set-based mode**: critically review a *chosen set of papers together*
— the papers you're synthesizing or citing side-by-side — surfacing where they **disagree with each other**, a
per-paper **fact scan** across the set, and **cross-paper** AI critiques. The primitives already exist; this spec
**scopes and aggregates** them across a set and adds one cross-paper Tier-2 generator + a modal. It must meet the
ratified **#13 auditability bar** and pass the **rule-#9 Principles + APPROACH-AVOIDANCE gate**.

## Goal & scope

**Goal:** a shared, set-based critical-review engine keyed on a list of `paper_ids`, run as one async job, launched
from **two entry points** (a synthesis's source papers; an explicit library multi-selection) and rendered in **one
dedicated modal**.

**In scope:** intra-set contradiction detection; a per-paper aggregate fact-matrix; egress-gated cross-paper Tier-2
candidates through an extended #13 bar; the modal + two entry points; a small additive migration; security audit +
QA route + experience pass.

**Out of scope (follow-ons):** persisting a "set" as a first-class entity; ranking/scoring papers; resolving
disagreements; a non-modal pane; the citation-concentration lens (network-based, not in Tier-1).

## Architecture

One engine, keyed on `set_ids: list[int]`, two thin entry points, one modal.

```
synthesis "Critically review these sources"  ─┐
library bulk-bar "Critical read across selection" ─┴─▶ POST /critical-read/set {paper_ids, llm} ─▶ async job
                                                                                                    │
                                          Tier-1 (local): intra-set contradictions + aggregate matrix
                                          Tier-2 (opt-in, egress-gated): cross-paper candidates → #13 verify
                                                                                                    │
                                                          GET /critical-read/set/{job_id} ─▶ modal
```

## Components

### 1 · Deterministic backbone — Tier-1, local, always-on
New module `app/backend/methods/critical_review_set.py`, reusing inc-266 primitives.

- **Intra-set contested claims.** For each `paper_id` in the set, run the existing `find_contested_claims` but with
  `other_chunk_ids` scoped to the *other papers in the set* — a new helper `set_chunk_embedding_ids(conn, set_ids,
  exclude_id)` mirroring `other_paper_chunk_embedding_ids` (same `embeddings→chunks→papers` join, `chunks.paper_id IN
  set_ids AND != exclude_id`, `deleted_at IS NULL`). Result: only contradictions where **both** papers are in the set
  ("your chosen papers disagree here"). Each carries claim, verbatim contradicting passage, both paper ids/titles,
  page, stance="contrast", confidence. Reuses `embed_model` / `vector_store` / `stance_scorer` / `make_chunk_resolver`
  (all injected; test seam `critical_review_deps`).
- **Aggregate fact-matrix.** For each set paper, gather its **stored** signals via `_stored_method_signals` (statcheck
  / retraction / transparency / findings FACTs) + its intra-set contested-count → one row per paper:
  `{paper_id, title, method_signals: [{kind,label,detail}], contested_count}`. **Strictly a fact matrix** — per-paper
  check *statuses*, **never summed into a score or a ranking** (PRINCIPLES: no opaque composite scores). An empty row
  = "these checks surfaced nothing on this paper," **never** "clean" (silence ≠ certificate).

### 2 · Cross-paper critique — Tier-2, egress-gated LLM, opt-in, #13 bar
New module `integrations/gemini/critical_review_set.py` (or extend the existing), reusing `verify_candidates`.

- **Prompt** the configured LLM (`complete()` seam) with the set's **bounded** text: per paper `title + abstract +
  top chunks`, each block labeled with its paper id/title, **total-capped** (`_MAX_SET_PROMPT_CHARS ≈ 20000`,
  budgeted evenly across papers). Instruction: "concerns that **span these papers** — a shared limitation, a claim in
  one contradicted by another — about the CLAIMS and METHODS ONLY, never the authors as people. For each, quote the
  EXACT sentence (verbatim) and name which paper it is from. JSON only."
- **Verify (#13, extended to the set).** For each draft `{concern, anchor_quote}`, keep it only if `anchor_quote` is
  verbatim in **some** set paper's full text (`canonical_text_contains` against each paper's `paper_full_text`) →
  record the **anchoring `paper_id`** + local NLI stance + confidence + signature; drop ungrounded (honest shortfall),
  previously-rejected, or duplicate. This is `verify_candidates` extended to *locate* the anchoring paper across the
  set (returns each candidate's `paper_id`).
- **Honesty on "cross-paper".** Only the **anchor quote in one paper is #13-verified.** The concern's cross-paper
  framing (it "relates to paper Y") is the **model's narrative** — admitted only because its anchor is grounded, the
  same way the single-paper concern text is unverified narrative around a grounded quote. `related_paper_ids` is
  populated **conservatively** (only the other set papers the model explicitly named, intersected with the set) and
  is surfaced as *"the model relates this to: [titles]"* — **the model's framing, never a verified link.** If the
  model names no valid set paper, the candidate is still shown (a single-anchor concern surfaced in a set context).
- **Egress:** the set text leaving the machine → the existing **Gemini egress gate** (invariant #3) enforced at the
  endpoint exactly as single-paper generate (`requires_egress(config) && !data_egress_enabled → 422`; key check; the
  `critical_review_generator`/`_set_generator` test seam bypasses egress with a fake). Tier-1 is fully local.

### 3 · API
Extend `app/backend/api/routers/critical_review.py` (~255 lines → ~330 with the two set endpoints + the set job
runner — well under the 600-line cap; no split needed). The set engine + gemini modules are separate new files.
- `POST /critical-read/set` — body `{paper_ids: list[int], llm: bool = false}`. Validates: 2 ≤ len ≤ `MAX_SET_PAPERS`
  (~12), all live + existing, de-duplicated. Returns `{job_id, status}` (async, mirrors the single-paper job).
- `GET /critical-read/set/{job_id}` — poll → `{status, report}` where report =
  `{aggregate: [...], contested_claims: [...], candidates: [...], llm_status}`. Runs Tier-1 always; runs Tier-2 only
  when `llm` and consent+key present, else `llm_status` carries the honest "AI critique needs consent/key" note.
- **Reuse** the existing per-candidate `POST /critical-read/candidates/{id}/accept|reject`.

### 4 · Persistence
- **Backbone** (contested claims + aggregate) is **computed per run**, not persisted (like the single-paper backbone job).
- **Tier-2 candidates** reuse the existing **`critical_review_candidates`** table, keyed on each candidate's anchoring
  `paper_id` (grouped and inserted via `repo.insert_candidates(conn, anchor_paper_id, [...])`). **Migration (additive,
  guarded, no down-migration):** add a nullable `related_paper_ids_json` (JSON) column holding the model's
  conservatively-validated related set papers (see Tier-2 honesty note — the model's framing, not a verified link);
  it also marks set-provenance so the single-paper view can, if wanted, distinguish set-origin candidates.
  `rejected_signatures` reuse keeps a rejected cross-paper concern from returning. `repo.insert_candidates` /
  `list_candidates` gain an optional `related_paper_ids` passthrough (backward-compatible; single-paper stays `NULL`).

### 5 · Frontend
New modal chunk `app/frontend/js/08y_critical_set.jsx` (a `<div className="axis-modal…">`-family modal, callosum's
existing pattern), three sections:
1. **Aggregate** — the fact-matrix (papers × check statuses); honest, no score/rank; a paper row links to open it.
2. **Where these papers disagree** — the intra-set contested claims (claim + contradicting passage + both titles +
   page + stance + confidence; each opens the source PDF, reusing the evidence-open path).
3. **AI cross-paper critiques (opt-in)** — the Tier-2 candidates in **amber** (`.cr-candidate`), each with its
   verbatim quote + which paper + stance + confidence + Accept/Reject; the section gated behind a "Suggest cross-paper
   critiques (AI)" button + the `/settings` `data_egress_enabled` check (mirrors `08x_methods_critical.jsx`).
Entry points: a **"Critically review these sources"** button on a rendered synthesis (`20_synthesis.jsx`, passing the
synthesis scope's `paper_ids`); a **"Critical read"** action in the library bulk-select bar (passing the selection).

## Honesty — rule-#9 Principles + APPROACH-AVOIDANCE gate

Resembles **PRINCIPLES Example 3** (statcheck: signal not verdict) + the inc-266 single-paper critical read. Pass:
- **Signal, not verdict.** Contradictions + candidates are signals the human appraises; nothing is resolved or scored.
- **Facts vs candidates.** Tier-1 backbone = FACTS (contradictions the corpus already contains + stored signals), no
  amber. Tier-2 = CANDIDATES (amber, human-filtered). Visually + structurally distinct.
- **No opaque composite score / no ranking.** The aggregate is a **fact matrix**, never a summed quality number or a
  "worst paper" ordering. *(Misaligned easy path: a "critique score" per paper or a ranked "most-flawed" list — declined.)*
- **#13 auditability.** Every AI judgment carries its retrieved span (the anchor quote's location) + local NLI stance
  + verbatim quote + visible confidence, evidence one low-friction click away; ungrounded drafts are dropped and the
  shortfall stated (`llm_status`, empty sections).
- **No accusation of individuals** (A-A veto). The prompt forbids "about the authors as people"; concerns are about the
  WORK; a banned-phrase test guards it (reuse the inc-266 `test_no_composite_score_field_and_no_author_directed_copy`).
- **Silence ≠ certificate.** Empty results read "nothing surfaced," never "these papers are sound."
- **Local-first / egress-gated.** Tier-1 no egress; Tier-2 rides the invariant-#3 consent gate; loopback providers run
  with zero egress.

## Security audit (gate: new endpoint + egress over a set of library text)
Open `.claude/security-audits/2026-07-15_multi-paper-critical-review.md` at build start: input validation on
`paper_ids` (ints, live, capped), egress consent enforcement + negative path (422 without consent), the #13 grounding
(no ungrounded candidate persists), prompt-injection posture (untrusted model output → defensive parse, JSON-only,
zero-drafts-on-failure), no author-directed output, resource caps (set size + prompt budget), SQL bound params.

## QA & experience
- **QA route** `route_71_critical_review_set.md`: the new API surfaces + honesty-invariant assertions (egress gate,
  facts-vs-candidates, no score field, no author accusation), per QA-POLICY.
- **Experience pass** (rule #11): dispatch the **skeptical synthesizer** persona against a real synthesis's sources —
  does the modal help decide whether to trust the synthesis, without moralizing or scoring?

## Caps & constraints
`MAX_SET_PAPERS ≈ 12`; `_MAX_SET_PROMPT_CHARS ≈ 20000` (even per-paper budget); `max_claims`/`top_k` reuse the inc-266
detector defaults; async job (embeds + NLI over a set are slow). 600-line cap respected (split routers/gemini modules
if needed — the `library_enrich.py` precedent).

## Testing
- **Engine** (`tests/test_critical_review_set.py`, injected fakes, no model load): intra-set scoping (a contradiction
  from a *non-set* paper does NOT surface; an intra-set one does); aggregate composition (per-paper stored signals +
  contested count; empty = honest null); `set_chunk_embedding_ids` correctness.
- **Tier-2 verify**: multi-paper #13 (a quote in set-paper B anchors to B with `related_paper_ids`; ungrounded
  dropped; rejected-signature skipped); banned-phrase/author-accusation scan; no score/quality field in the payload.
- **Endpoint**: egress gate (422 without consent, fake generator honors it), caps (set size), accept/reject reuse,
  the two entry-point request shapes.

## Verification (post-build)
`pytest` green incl. the new suites; manual: run over a real 3-paper synthesis source set — confirm intra-set
contradictions open the right PDFs, the aggregate is a fact-matrix (no score), Tier-2 is egress-gated + candidates
carry verbatim quote + stance + confidence + accept/reject; a rotated/garbled quote honestly falls to no-anchor.
