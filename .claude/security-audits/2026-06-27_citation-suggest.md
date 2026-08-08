# Security Audit — Highlight-to-suggest / evaluate (inc 156, `POST /citations/suggest`)

**Date:** 2026-06-27
**Feature:** A fully-local suggest+evaluate engine (`app/backend/citations/suggest.py`) + a new endpoint
`POST /citations/suggest` (`routers/citations.py`) + an in-app Cite pane (`app/frontend/js/37_cite.jsx`) + an
NLI stance scorer (`summarization/verification.py`). Given a draft sentence, it returns ranked library papers to
cite (retrieval in reverse) with an optional NLI stance (support/contrast/mention).
**Gate triggers:** #1 new API endpoint; #5 net-new feature spanning 3+ files.

## Threat review

- **Input validation.** The draft `text` is untrusted (it will come from the user's LibreOffice document in SP1b).
  `SuggestRequest` enforces `min_length=1, max_length=4000` and `top_k ∈ [1,20]` via Pydantic → malformed/oversized
  → **422** before any work. The handler additionally rejects whitespace-only text (`422`). The engine re-clamps
  (`[:MAX_TEXT_LEN]`, `top_k` → `min(top_k, MAX_SUGGESTIONS)`) defense-in-depth.
- **Resource exhaustion (the local-app threat model).** Bounded at every step: `text` ≤ 4000 chars; retrieval
  scans ≤ `CHUNK_TOP_K = 30` chunk hits; output ≤ `MAX_SUGGESTIONS = 20` papers; **≤ top_k (≤20) NLI passes** per
  request (one per suggested paper's best chunk). The embedding + NLI models are loaded **once** and cached on
  `app.state` (a fresh instance per request would reload the model each call) — no unbounded model loads.
- **Injection / SQL.** All DB access is SQLAlchemy Core bound parameters: `search_similar` (bound subqueries,
  rule #3, inc-66), `_chunk_text` / `_paper_meta` (`select(...).where(col == :id)`). No string interpolation; no
  table/column name comes from request data.
- **Data egress / SSRF.** **None.** The whole path is local — local embeddings (`encode_texts`) + the local NLI
  cross-encoder + sqlite-vec retrieval. No external host is contacted; this is **not** the Gemini egress gate and
  introduces no new outbound call. (Verified in the headed driver: 0 `generativelanguage` requests.)
- **Output encoding.** The response carries paper `title`/`author`/`quote` (library-derived text) as JSON; the
  frontend renders them as React text nodes (no `dangerouslySetInnerHTML`) → no injection surface. `bbox_json` is
  echoed from the stored chunk bbox, stamped `coordinate_precision="region"`.
- **Coordinate honesty (invariant #2).** A suggestion's evidence is a whole **chunk** → `region` precision,
  never an exact rect. `_stamp_region` writes `coordinate_precision="region"` into every bbox item and the
  top-level field; the Cite card opens "source region" (page-open + region note), never a fabricated exact
  highlight. Test-pinned (`test_suggest_evidence_is_region_precision_never_exact`).
- **Secret handling.** No secrets touched (no API key, no egress flag).
- **File-path safety.** No filesystem path is built from request data.
- **Supply-chain.** **No new dependency** (reuses the existing sentence-transformers embed + NLI models,
  sqlite-vec, retrieval, FastAPI/Pydantic).

## Negative-path checks (recorded)

- Empty `""` → **422** (Pydantic `min_length`); whitespace `"   "` → **422** (handler strip);
  `len > 4000` → **422** (Pydantic `max_length`). (`test_suggest_endpoint_rejects_empty_and_oversized_text`)
- NLI model unavailable → `NLIStanceScorer.classify_stance` returns **None** (no stance, never a guessed verdict
  / never a 500). (`test_nli_stance_scorer_is_graceful_when_model_unavailable`)
- Empty library / no semantic match → `suggestions: []` (**200**), the Cite pane shows the honest empty state.
- Trashed (soft-deleted) papers are excluded from candidates (inherits inc-66 retrieval filtering;
  `test_suggest_excludes_trashed_papers`).
- Egress unset + using the Cite pane → 0 genai-host requests (headed driver `drive_inc156_cite.py`).

## Principles posture (rule #9, recorded)

Suggestions carry their matched quote + page + match-score as the **reason** (inspectable, #8); they are
**candidates the author picks**, never auto-inserted (#3/#5); the stance leads with the verbatim quote +
confidence, a labeled signal not a bare verdict (#1/#4); the match score is one labeled similarity, **no opaque
composite** (#7); ranking is by sentence-match, **not citation count** (bias-amplification is deferred to the SP3
beyond-library lane); suggesting a paper accuses no one (A-A veto). The misaligned-easy paths (opaque rank, bare
verdict, auto-insert, exact-coordinate claim) are declined by design.

## Result

**Security Audit: PASS.** Local-only (no egress, no new external fetch), bounded inputs + work, bound-param SQL,
region-honest coordinates, no new dependency, graceful degradation. Tests + the headed driver pin the
negative paths and the no-egress + region-precision invariants.

## Addendum — `POST /citations/classify-stance` (inc 461, roadmap #20, backlog #33/#34)

Triggered by gate criterion #1 (a new API endpoint). New sibling router `app/backend/api/routers/citation_stance.py`
— a **pairwise** stance classification given a caller-supplied `(sentence, passage)` pair, built for the
LibreOffice "Insert evidence" command's claim-check (roadmap #20). Every existing stance call site in this
codebase (`/citations/suggest` above, `beyond_library.py`, `critical_review.py`, `citation_context.py`,
`reference_integrity.py`) bundles classification with a retrieval/search step first; this is the first place a
caller supplies both texts directly.

- **Input validation.** `ClassifyStanceRequest` enforces `min_length=1, max_length=MAX_TEXT_LEN` (the SAME 4000-
  char cap `/citations/suggest` already uses, reused not reinvented) on both `sentence` and `passage` via
  Pydantic → empty/oversized → **422** before any work. No other fields accepted.
- **No new model, no new egress class.** `classify_stance_endpoint` reuses `_suggest_stance_scorer(request)` —
  the exact cached `NLIStanceScorer` singleton `/citations/suggest` already lazily loads and caches on
  `app.state`. No retrieval, no embedding call, no chunk/paper lookup, no DB access at all — this endpoint
  touches no persistence. Same local-only posture as the base audit above; no new outbound host.
- **Resource exhaustion.** Bounded to exactly one NLI classification per request (no loop, no batch, no
  per-request model reload — the cached-singleton pattern already covers this).
- **Output.** `StanceResponse | None` — the same label/confidence/probs shape `/citations/suggest` already
  returns for its own stance field; nothing new is echoed back that wasn't already part of an audited response
  shape.
- **Injection / SQL.** None — no SQL at all on this path.
- **Secret handling.** No secrets touched.
- **Supply-chain.** No new dependency.

**Negative-path checks (recorded, `tests/test_citation_stance.py`):** empty `sentence`/`passage`/missing
`passage` → **422**; oversized text (`MAX_TEXT_LEN + 1`) → **422**; an injected scorer that returns `None`
(model unavailable/inference failed) → the endpoint returns `None`, **not a 500** — mirrors
`classify_stance`'s own "never a guessed verdict" contract exactly, the same graceful-degradation posture the
base audit already established for `/citations/suggest`.

## Principles posture addendum (rule #9)

The claim+stance check is signal-not-verdict, identical framing to `/citations/suggest`'s existing stance
display (a labeled 3-way support/contrast/mention breakdown with confidence, never a bare "supports/
contradicts" verdict) — no new pattern, the same honest framing applied to a caller-supplied claim instead of a
retrieved chunk. It is purely a decision aid inside the LibreOffice "Insert evidence" dialog (the caller decides
what, if anything, to insert); nothing about this endpoint auto-composes or auto-inserts document text.

**Security Audit (inc 461 addendum): PASS.** No new egress class, no new dependency, no persistence touched;
input bounded identically to the already-audited sibling endpoint; graceful `None` degradation confirmed by test.
