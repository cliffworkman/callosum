# Increment 156 — Highlight-to-suggest / evaluate (Track C, SP1a)

The first build of the highest-value novel capability (#30). Given a draft sentence, **suggest** which library
papers to cite (retrieval in reverse) and **evaluate** whether each candidate *supports / contrasts / mentions*
the claim — with the evidence shown. SP1a = the engine + the `POST /citations/suggest` contract + a thin in-app
**Cite** pane; SP1b (next) = the LibreOffice "Suggest citations" macro that calls the contract (the inc-107→108
pattern). Fully local — local embeddings + local NLI; **no egress**. No migration (read-only over chunks).

## Implemented

- **`app/backend/summarization/verification.py`** — an NLI **stance** scorer beside `NLISupportScorer`:
  `Stance{label, confidence, probs}`, `StanceScorer` Protocol, `NLIStanceScorer` (reuses the
  `cross-encoder/nli-MiniLM2-L6-H768` 3-way softmax: entailment→support, contradiction→contrast,
  neutral→mention; **any failure → None**, never a guessed verdict), `default_stance_scorer()`. Generalized
  `_entailment_index` → `_label_index(..., label, default)` + added `_stance_from_scores`.
- **`app/backend/citations/suggest.py`** (NEW) — `suggest_citations(conn, *, text, model, vector_store, top_k,
  evaluate, stance_scorer)`: `search_similar(target_types=("chunk",))` → best chunk per paper → rank by score →
  for each, load chunk text + paper meta, attach the matched quote (region precision) + (if evaluate) the stance.
  Caps: `MAX_TEXT_LEN=4000`, `CHUNK_TOP_K=30`, `MAX_SUGGESTIONS=20`, `QUOTE_MAX=400`.
- **`app/backend/api/routers/citations.py`** — `POST /citations/suggest` (`SuggestRequest`/`SuggestResponse`/
  `StanceResponse`/`SuggestionResponse`); whitespace text → 422; the embedding model + stance scorer are cached
  on `app.state` (a sync endpoint must not reload heavy models per request; injected ones win).
- **`app/backend/api/app.py`** — `create_app(..., stance_scorer=None)` → `api.state.stance_scorer` (overridable
  in tests, mirrors `support_scorer`).
- **`app/frontend/js/37_cite.jsx`** (NEW) + `styles.css` — a THEORY accordion **Cite** section (order 25): a
  paste box → suggestion cards (title · author/year · **stance pill** support/contrast/mention or "stance n/a" ·
  **match** pill · verbatim **quote** · **Open source region** + **Copy BibTeX**). Tokens-only CSS; stance pills
  reuse the `.cite-status` pill geometry (support=verified-green, contrast=flag-amber, mention/unknown=muted).

## Key technical detail

- **Stance from the existing NLI model.** No new model — the support scorer already loads the 3-class NLI
  cross-encoder; the stance scorer reads all three labels via `id2label` (`_label_index`) and maps them. So
  "evaluate" was ~free over "suggest" (it shares the retrieval pass; the marginal cost is surfacing the
  contradiction/neutral labels).
- **Best-chunk-per-paper ranking via dict insertion order.** `search_similar` returns hits best-first; the first
  time a paper appears is at its best chunk, so `dict` insertion order ranks papers by that best chunk's score.
- **Coordinate honesty:** the matched evidence is a whole chunk → `coordinate_precision="region"`, stamped into
  every bbox item (`_stamp_region`); the viewer page-opens + shows a region note, never a fabricated exact rect.
- **Synchronous + model caching:** `/citations/suggest` is sync (the pane is interactive); the heavy embed + NLI
  models load **once** and are cached on `app.state` so subsequent Suggest clicks are fast. First click pays the
  load (the pane shows "Finding suggestions…").

## Principles / security

- **Principles gate run** (rule #9): suggestions carry their reason (quote+page+score), are candidates not
  verdicts, never auto-insert; stance is local-NLI-only, leads with the quote+confidence; region-honest; no
  opaque composite; ranked by sentence-match not citation count; accuses no one. See the design spec.
- **Audit `.claude/security-audits/2026-06-27_citation-suggest.md` PASS** — local (no egress / no new fetch),
  bounded inputs + work, bound-param SQL, region-honest, **no new dependency**, graceful NLI degradation.

## Experience pass (rule #11) — deadline-writer persona

A persona agent (a researcher hand-citing in LibreOffice, vetting before citing) found the **vet** half strong
(stance-with-quote is exactly what saves her from citing the opposite) but a pane named "Cite" that couldn't
**extract** anything dead-ended. **Fixed in-increment (cheap):** a **Copy BibTeX** button per card (the in-app
bridge for hand-citing; reuses the tested inc-70 export), a **visible** "stance unavailable" note (not just a
tooltip), and de-duplicated the per-card region/confidence boilerplate (one results-level note). **Deferred
(SP1b / backlog):** a formatted "Cite as… (style)" copy via the inc-106 engine; the live LibreOffice **Insert**;
an accordion entry signpost; (the `match 1.00` "looks fake" reaction is a seed-data artifact — real cosine
varies).

## Manual verification

**Headed, no egress** (`.local/visual/drive_inc156_cite.py` — fake-embedding app + injected fake stance scorer
over the seeded library incl. the real seed.pdf paper): open THEORY → **Cite**, paste a sentence → **2 cards**
render with a **SUPPORT** stance pill + **MATCH 1.00** + verbatim quote + the **Copy BibTeX** button + the
results-level ranking/region note; **Open source region** on the renderable paper opens the real PDF at region
precision; **0 console / 0 page / 0 genai**.

## Pytest

**568** (+11 `test_citations_suggest.py`: ranking/one-per-paper, region-not-exact, evaluate attaches/omits
stance, trashed excluded, empty→[], the NLI label-mapping + graceful-when-unavailable + loader path, endpoint
shape + stance + evaluate=false + empty/whitespace/oversized→422; route-surface +1). `ruff` clean; build +
assembly green; QA surface **110/110 API + 569/569 FE, 0 uncovered** (`route_42_cite.md`). No migration.

## Next (SP1b)

The LibreOffice "Suggest citations" UNO macro (`adapters/libreoffice/callosum_cite.py`): grab the current
sentence → `POST /citations/suggest` → present suggestions (stance + quote + confidence) → Insert the chosen
cite via the existing inc-108 Insert→ReferenceMark flow. Verified by a headless UNO round-trip (like inc-108).
No server change (the contract is SP1a's). Then SP2 (beyond-library discovery) + Stage-4 (section-scoping).
