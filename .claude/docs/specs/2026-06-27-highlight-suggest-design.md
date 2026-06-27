# Highlight-to-suggest / evaluate — Track C, SP1a (inc 156)

**Status:** built (inc 156). Design spec for the engine + contract + in-app Cite pane. The plan lives at
`.claude/backups/plans/2026-06-27_inc156-highlight-suggest-sp1a.md`.

## Why

Track C ("highlight-to-suggest / highlight-to-evaluate", `future-tracks/opus4.8_future-tracks.md`) is the
highest-value novel capability: given a draft sentence, **suggest** which library papers to cite (retrieval in
reverse) and **evaluate** whether each candidate *supports / contrasts / mentions* the claim, with the evidence
shown. It is "largely a recombination of machinery the core already builds."

**User decisions:** SP1 = suggest **and** evaluate together; the real input is the sentence being written in the
**LibreOffice document** (inc-108 cite-while-you-write); sequence like **inc-107→108** — build the engine +
endpoint contract first (SP1a) with a thin in-app surface to verify it, then the LibreOffice macro (SP1b).

## Scope

**SP1a (inc 156):** the local suggest+evaluate engine, the `POST /citations/suggest` contract, and an in-app
**Cite** pane (THEORY accordion) to review + extract. **Deferred:** SP1b (LibreOffice "Suggest citations" macro
→ insert), SP2/Stage-3 beyond-library discovery (OpenAlex/Semantic-Scholar), Stage-4 plugin section-scoping.

## Architecture

- **Suggest** = `embeddings.retrieval.search_similar(query=<span>, target_types=("chunk",))` — guided clustering
  run against the span — aggregated to the best chunk per paper, ranked by that chunk's score. Trashed papers
  excluded (inc-66). `app/backend/citations/suggest.py::suggest_citations`.
- **Evaluate** = a new local **NLI stance scorer** (`summarization/verification.py`): the existing
  `cross-encoder/nli-MiniLM2-L6-H768` already emits a 3-way softmax, so entailment→**support**,
  contradiction→**contrast**, neutral→**mention** (`NLIStanceScorer.classify_stance` → `Stance{label, confidence,
  probs}`; `_label_index` generalizes the old `_entailment_index`). On any model failure → `None` (no guessed
  verdict).
- **Contract** = `POST /citations/suggest {text, top_k≤20, evaluate}` → `{suggestions: [{paper_id, title, year,
  author, match_score, chunk_id, quote, page_start, page_end, coordinate_precision:"region", bbox_json, stance}]}`.
  The model + stance scorer are cached on `app.state` (a synchronous endpoint must not reload them per request);
  injected ones win (tests). **Fully local — no egress.**
- **In-app Cite pane** (`app/frontend/js/37_cite.jsx`): a paste box → suggestion cards (title · author/year ·
  stance pill · match pill · verbatim quote · "Open source region" + "Copy BibTeX"). Region precision → the
  viewer page-opens with a region note, never an exact rect.

## Honesty (Principles gate — run)

Most like synthesis-verification (every claim carries its evidence) + the gapfinder (candidates, not a verdict).
- **Declined (misaligned-easy):** opaque similarity/citation-count rank with no reason; a stance verdict without
  the quote; auto-insert; chunk-region evidence shown as exact.
- **Built (aligned):** each suggestion carries its matched quote + page + match-score as the **reason** (#8);
  **candidates the author picks**, nothing auto-inserts (#3/#5); stance leads with the verbatim quote +
  confidence, a labeled signal not a bare verdict (#1/#4); stance is **local NLI only**; evidence is **region**
  precision (#2); match_score is one labeled similarity, **no opaque composite** (#7); ranked by sentence-match
  not citation count (bias-amplification is an SP3 concern); suggesting a paper accuses no one (A-A veto).

## Verification

- pytest **568** (+11 `test_citations_suggest.py`); `ruff` clean; build + assembly green; QA surface
  **110/110 API + 569/569 FE, 0 uncovered** (`route_42_cite.md`).
- Audit `.claude/security-audits/2026-06-27_citation-suggest.md` **PASS** (local, bounded, bound-param,
  region-honest, no new dependency).
- Headed, no egress (`.local/visual/drive_inc156_cite.py`): paste → 2 cards (stance pill, match, quote), Copy
  BibTeX, "Open source region" → real PDF at region; 0 console/page/genai.

## Experience pass (rule #11) — deadline-writer persona

Found the **vet** half genuinely strong (stance-with-quote is what saves a writer from citing the opposite), but
a pane named "Cite" that couldn't extract anything dead-ended. **Fixed in-increment (cheap):** a "Copy BibTeX"
extract button per card (the in-app bridge for a writer hand-citing in LibreOffice; reuses inc-70 export); a
**visible** "stance unavailable" note (not just a tooltip); de-duplicated the per-card region/confidence
boilerplate. **Deferred (backlog/SP1b):** a formatted "Cite as… (style)" copy via the inc-106 engine; the live
LibreOffice **Insert** (SP1b); an accordion entry signpost.
