# Increment 271 — Set (multi-paper) critical review (backlog #12)

Extends the single-paper "Critical read" (inc 266) to a **chosen set of papers reviewed together** — the sources
behind a synthesis, or a library selection. Same soul as the single-paper read: a **signal, never a verdict**;
facts (Tier 1, local) and candidates (Tier 2, egress-gated AI) kept visually + epistemically distinct; no composite
score; the critique is of claims + methods, never the authors. Reuses the inc-266 primitives throughout.

## Implemented

**Migration + persistence (Task 1)**
- `alembic/versions/0045_cr_candidate_related_papers.py` — additive, guarded `related_paper_ids_json` JSON column on
  `critical_review_candidates` (down_revision `0044`). `schema_critical_review.py` gains the `Column(..., JSON)`;
  `critical_review_repo.insert_candidates` passes it through (`None` for single-paper candidates — no behavior change).

**Tier-1 engine (Tasks 2–3) — `app/backend/methods/critical_review_set.py` (local, no LLM)**
- `set_chunk_embedding_ids(conn, set_ids, exclude_id)` — the inc-266 `other_paper_chunk_embedding_ids` **scoped to
  the set** (chunks whose `paper_id ∈ set_ids`, ≠ the paper under review, non-deleted). This is the set-scoping: a
  contradicter is retrieved only when it belongs to *another paper in the chosen set*.
- `set_contested_claims(...)` — loops the set, runs `find_contested_claims` with `other_chunk_ids` scoped to the set;
  rows carry `{claim, passage, claim_paper_id, other_paper_id, page, stance, confidence}`.
- `set_aggregate(conn, set_ids, contested)` — one row per paper: its **already-stored** method signals
  (`_stored_method_signals`) + its intra-set contested count. A **fact-matrix**, never a summed score / ranking
  (guard test asserts no `score/quality/grade/rank/rating` key); empty `method_signals` is honest silence, not "clean".

**Tier-2 generator (Task 4) — `integrations/gemini/critical_review_set.py` (egress-gated)**
- `GeminiSetCriticalReviewGenerator.propose(set_papers)` → `parse_set_drafts` (defensive; `[]` on any parse failure)
  → `SetCandidateDraft{concern, anchor_quote, related_indices}`.
- `verify_set_candidates(...)` — the extended **#13 bar**: keep a draft only if its `anchor_quote` is verbatim in
  **some** set paper (`canonical_text_contains`) → that paper becomes the anchor (chosen **deterministically**, never
  by the model); annotate with a local NLI stance + confidence + signature; drop ungrounded / previously-rejected /
  duplicate. `related_paper_ids` = the model's named indices mapped to set ids, validated to the set, minus the anchor
  — **the model's framing, not a verified link.** Prompt bounded to `_MAX_SET_PROMPT_CHARS=20000` **divided across
  the set**; `_MAX_DRAFTS=8`, concern/quote capped at 400.

**API (Task 5) — `routers/critical_review.py`**
- `POST /critical-read/set` (202) — de-dup ids, require **2 ≤ len ≤ 12** (`MAX_SET_PAPERS`) else 422, existence-check
  each else 404, spawn an async job. `GET /critical-read/set/{job_id}` polls it.
- `_run_set_critical_read_job` always runs Tier-1 (`set_contested_claims` + `set_aggregate`); on `llm:true`,
  `_run_set_tier2` runs behind the egress gate — mirrors the single-paper generate: `requires_egress(config) and not
  data_egress_enabled` → `llm_status.status == "unavailable"` (Tier-1 still completes), else generate → verify →
  group by anchor paper → `insert_candidates`. Two `app.state` seams: `critical_review_set_jobs` + a
  `critical_review_set_generator` test seam.

**Frontend (Task 6) — `app/frontend/js/08y_critical_set.jsx` + two entry points**
- `CriticalSetModal`: the fact-matrix (`CriticalSetMatrix`, neutral bordered table, "not a score" caption, scrolls
  in-container), the "where these papers disagree" list (opens the contradicting PDF at region precision), and the
  amber Tier-2 candidate cards (reuse `.cr-candidate`/`.cr-quote`/`.cr-actions`) with which-paper + stance/confidence +
  the "model's framing, not a verified link" note + Accept/Reject.
- Entry points (both gated on `!readOnly`): a **"Critically review these sources (N)"** button on a shown synthesis
  (over its cited papers, 2..12) via `paneCtx.onCriticalReviewSources`; a **"critical read"** action in the library
  bulk bar (≥2 selected) via `useLibrary` `critSetIds` state + `onBulkCriticalRead`.

**Gates (Task 7)**
- Security audit `.claude/security-audits/2026-07-15_multi-paper-critical-review.md` — **PASS**.
- QA route `.claude/qa-routes/route_71_critical_review_set.md` — `build_surface_map.py check` → **0 uncovered API,
  0 uncovered FE**.
- Help corpus: new "Critically reviewing a set of papers together" section. `changes.md` + this note + CLAUDE bump.

## Key technical detail
The whole feature is the inc-266 single-paper engine with the contradiction detector's candidate corpus **narrowed
to the set**. `find_contested_claims` already takes an `other_chunk_ids` set; passing the set-scoped embedding ids
makes "the rest of your corpus contests this" become "another paper *in this set* contests this" — no new retrieval
math. The only genuinely new judgment surface is the Tier-2 cross-paper prompt, and it is admitted through the same
verbatim #13 bar as single-paper, with the anchor paper chosen by *which set paper contains the quote* (deterministic),
so the model never asserts a cross-paper edge as fact — `related_paper_ids` is stored + shown as framing only.

## Manual verification script
1. `uvicorn app.backend.api.app:app --port 8888`; open a DB with ≥3 processed papers.
2. Select 3 papers → **critical read** in the bulk bar. Confirm: the fact-matrix renders (rows = papers, method-check
   columns + contested count, "not a score" caption); the disagreement list opens the *contradicting* paper at its page.
3. Run a synthesis, then click **Critically review these sources (N)** → the modal opens over the cited papers.
4. Egress **off** (default): the "Suggest cross-paper critiques (AI)" control is hidden; forcing `POST /critical-read/set
   {llm:true}` → job done with `llm_status.status == "unavailable"`, no candidates, no genai host hit.
5. Egress **on** (fake/loopback): **Suggest…** → each candidate quotes a set paper verbatim, names its anchor paper,
   carries stance + confidence; a garbled quote yields no anchor (dropped). Accept persists; Reject never returns.

## Experience pass (rule #11 — skeptical synthesizer, inline)
Inhabited **Dr. Nadia**, deciding whether to trust a 6-paper synthesis before citing it. Reception: the
"Critically review these sources (N)" button sits in the summary-meta header beside the verified/flagged counts —
where she already reads trust signals; discoverable + legible. The disagreement list (click → opens the
contradicting PDF at its page) and the egress-gated, verbatim-quoted amber candidates serve her verify-it-yourself
instinct well. **Finding (fixed in-session):** the fact-matrix composes *already-stored* method signals, so a set
whose papers were never run through statcheck/transparency showed **no method columns** — reading as "clean on
methods" when it actually means "no checks were run" (silence-is-not-a-certificate). Aligned fix: when the
aggregate has zero method-signal columns, the caption now says the checks haven't been *run* + points to each
paper's METHODS pane, and clarifies the `contested` column needs no prior check. No UX follow-up backlogged.

## Pytest
Full suite green — `tests/test_critical_review_set.py` 11 passed (8 engine/Tier-2 + 3 endpoint). Total: **1201 passed, 1 skipped** (18m20s).
