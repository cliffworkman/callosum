# Increment 228 — citation-equity SP2: topical overlooked-work remediation (backlog #25)

## Implemented

The distinctive half of citation equity (#25): given a paper's reference list, surface **topically-relevant work
the list OMITS** — candidates the author may have missed — ranked by callosum's **own local scientific-paper
embedding cosine**, with an inspectable "why this is a real topical match" + a one-click **metadata-only add**.
**Add-only, identity-agnostic, no quota** — the spec's veto lines + the A-A no-accusation boundary, honored
*structurally*: there is **no "drop this citation" path**, the reason is topical relevance (never an author's
identity), and it's "relevant work you may have missed," never "add N to hit a target." A "Find overlooked work"
action in the inc-227 Citation-equity panel (separate from the structural audit — the heavier embedding pass is
opt-in).

- **`integrations/openalex/adapter.py`** — `_meta_from_work` extended additively with `related_works` (bare ids,
  capped) + `concepts` (top names) — the candidate pool + the shared-topic "why". New `_meta_with_abstract`
  (`_meta_from_work` + the reconstructed abstract, candidate-only). New `fetch_works_by_ids` (one batch
  `?filter=openalex_id:W1|W2|…`, each id validated `^W\d+$` **before** the request → no SSRF, ≤50/call, cached) +
  `fetch_topic_candidates` (the topic sample WITH abstract, sharing the inc-227 `field:<id>` cache via a new
  private `_field_sample_body`).
- **`app/backend/methods/overlooked_work.py`** (NEW, pure) — `rank_overlooked(*, focal_text, candidates,
  focal_concepts, embedding_model, threshold=0.55, top_k=12)` → `OverlookedCandidate`s (numpy unit-cosine, the
  inc-185 `score_axis_relevance` pattern): each carries the labeled `match`, the focal ∩ candidate
  `shared_concepts` ("why"), and `in_library`. Below-threshold candidates are not shown (no fabricated relevance);
  **no identity, no verdict, no drop, no quota**; ranked by topical match, never citation count.
- **`app/backend/api/routers/citation_equity.py`** (extended) — `POST`/`GET /methods/citation-equity/overlooked`
  (a 2nd JobStore `app.state.overlooked_jobs`; the inc-227 worker pattern). Worker: focal title+abstract
  (`fetch_work_csl`) + focal `related_works`/`primary_topic`/`concepts` (`fetch_work_meta_for`) → **candidate pool
  = related ∪ topic sample**, **minus the already-cited** (`fetch_referenced_works`) + the focal itself → fetch
  candidate metas+abstracts → mark `in_library` (`find_existing_paper_by_identity` by W-id/DOI) → `rank_overlooked`.
  A lazy-cached `_overlooked_model(app)` (injected wins; else SPECTER v1).
- **Frontend `08b_methods_citation_equity.jsx`** (extended, 255) — an **Overlooked work** sub-section: a **Find
  overlooked work** button → poll → candidate cards (title·authors·year·venue, a **topical match** chip, a
  **shared topics** "why", and either **✓ in library** or a one-click **＋ Add** via `POST /discovery/save` —
  metadata-only, no PDF). A framing line ("candidates to consider, never a 'you must cite this'; nothing is dropped
  or auto-added, and an author's identity is never the reason"), an honest coverage line + empty state. Tokens-only
  `.cite-equity-cand*` CSS.

## Key technical detail

**The embedding is SPECTER v1 (`sentence-transformers/allenai-specter`) — scientific-paper embeddings purpose-built
for paper-paper relatedness — loaded through the EXISTING sentence-transformers stack, so NO new dependency** (the
maintainer chose "SPECTER-class"; the aligned implementation delivers that quality at a model-download cost, not a
package; SPECTER2 [needs `adapters`] / SciNCL are documented swaps in `OVERLOOKED_EMBED_MODEL`). The "topical
match 0.NN" is callosum's **own** inspectable cosine, not OpenAlex's black box. **The real model only loads for the
user** (first run → ~440 MB HF download); CI/tests inject a **fake deterministic keyword model** (the inc-185
pattern), so the suite never downloads SPECTER. Only DOIs / W-ids / the topic id leave the machine (the OpenAlex
metadata fetches, cached); the title+abstract are embedded **locally** — public-metadata egress, NOT the Gemini
gate. The candidate pool reuses the cached focal blob (`related_works`) + shares the inc-227 `field:<id>` cache, so
a run adds at most one batch fetch beyond the audit's.

## Manual verification script

- **Unit/integration** (`tests/test_overlooked_work.py`, hermetic, 10 tests): the additive `_meta_from_work` keys +
  `_meta_with_abstract` + `fetch_works_by_ids` (batched, W-id-validated, fail-closed); the ranker (order, threshold
  cut, shared-concept "why", `in_library` passthrough, **no-identity proven** by injecting `gender`/`sex`/`race` →
  output unchanged); the async endpoint (run→candidates, **excludes already-cited**, marks in-library, empty state,
  404/422, unknown-job 404) — via an injected fake `openalex_client` + a fake embedding model.
- **Headed, no egress** (`.local/visual/drive_inc228_overlooked.py`, fake OpenAlex + fake keyword model): Citation
  equity → **Find overlooked work** → 3 candidates with match chips, the in-library one marked, the off-topic one
  excluded, **＋ Add** lands a candidate in the library; 0 console/page/genai.

## Gates

- **Security audit** — **addendum** to `.claude/security-audits/2026-06-30_citation-equity.md` **PASS**: the new
  OpenAlex egress shape (validated/bound `related_works` + batch ids + topic-candidate abstracts → no SSRF); the
  **add path is metadata-only `save_item` — NO PDF fetch** (no paywall circumvention, A-A veto); **no new
  dependency** (SPECTER v1 via the existing stack — a model download, not a package); bounded; **no identity
  inference** (proven by test); public metadata, NOT the Gemini gate.
- **Principles / A-A — aligned**: the inc-156-suggest / inc-185-relevance class — signal-not-verdict (#2), no
  opaque composite (#7 — one labeled cosine), inspectability (#8), candidates the human picks (#3/#5). The veto
  lines are **structural** (no drop path; identity never the reason; no quota; only-add). Declined: a "fix your
  biased citations" framing, auto-insertion, ranking by citation count.
- **QA (rule #10):** `route_51_methods_citation_equity.md` extended (the overlooked flow + the veto assertions);
  surface **165/165 API + 727/727 FE, 0 uncovered** (the new endpoint matches the `/methods/citation-equity*`
  glob; the buttons ride the chunk claim).
- **Rule #1:** new `overlooked_work.py` (~120); `routers/citation_equity.py` + `js/08b_methods_citation_equity.jsx`
  (255) under cap.

## Pytest

**(see footer — full suite green; +10 `test_overlooked_work.py`).** `ruff` + `format` clean; frontend rebuilt
(`test_frontend_assembly` 5/5). No migration / new dependency. **This completes citation equity (#25): SP1 audit
(inc 227) + SP2 remediation (inc 228).**
