# Increment 232 — Citation context: "how this paper is cited" (B4 SP1, the scite analogue)

The second B-item. When you're deciding whether to rely on a paper, it matters *how the later literature responded
to it*: do subsequent papers **support** it, **contrast** it, or merely **mention** it? A new METHODS panel answers
that — the incoming, "smart citations" (scite) half of B4.

Maintainer decisions (AskUserQuestion): **incoming direction first** (outgoing — "how a paper cites its own sources"
— is deferred; it needs fiddly in-text-citation → reference linking) + **our local NLI stance** (reusing inc-156's
`NLIStanceScorer`, not Semantic Scholar's black-box intents).

## The honesty stance (the load-bearing part — a Principles-gate feature)

scite-style tools drift toward verdicts; the whole design resists that:
- **Counts, never a composite score** (#7) — no single "smart-citation number", no ranking.
- **Evidence always shown** (#4) — every classified citation carries its **real citing sentence** + a confidence.
- **A labeled signal, not a verdict** (#2) — the stance is an NLI reading of the citing sentence against the focal
  paper's own claim, framed as "a signal to read", not a judgment.
- **Unclassifiable ≠ guessed** (#6) — a citation with no citing sentence is counted but not classified.
- **No accusation** (A-A) — a "contrast" describes the shown sentence's rhetorical relationship, never an author.

## Implemented

- **`integrations/semantic_scholar/adapter.py`** (NEW) — `SemanticScholarClient.fetch_citation_contexts(conn, doi)`
  hits the S2 Graph API `GET /paper/DOI:{doi}/citations?fields=contexts,isInfluential,citingPaper.{title,year,authors,externalIds}`.
  Mirrors the OpenAlex/Crossref adapters: an injectable `fetcher`, `external_api_cache` via the shared
  `integrations/api_cache`. The DOI is **shape-validated** (`^10\.\d+/\S+$`) and **fully url-encoded**
  (`quote(doi, safe='')`) before it enters the path → the host is always constant, no value can break out (no SSRF).
  Paginated + **capped** (`MAX_CITATIONS = 500`). **Fail-closed with non-poisoning caching:** a transient first-page
  failure returns `[]` and is **not** cached (only a real 200 is), so a blip never becomes a cached "0 citations".
  Optional `CALLOSUM_S2_API_KEY` (write-only header, raises rate limits; the API works without one).
- **`app/backend/methods/citation_context.py`** (NEW, pure) — `classify_citation_contexts(*, contexts, focal_claim,
  stance_scorer)`: for each citing sentence, `stance_scorer.classify_stance(sentence=focal_claim, passage=<citing
  sentence>)` (the citing sentence is the premise/evidence; the focal claim the hypothesis) → support/contrast/mention
  + confidence; aggregate **counts** + keep every citation's evidence. `focal_claim` = the library paper's abstract
  (`abstract_plain_text`), else its title. No sentence / no scorer / no claim → the citation is counted, never
  classified. `to_dict()` has **no `score` key** — counts only.
- **`app/backend/api/routers/citation_context.py`** (NEW) — `POST /papers/citation-context/run {paper_id}` (202; 404
  no paper / 422 no DOI) + `GET …/run/{job_id}` + the worker (resolve DOI + focal claim → `fetch_citation_contexts` →
  `classify_citation_contexts` with `_stance_scorer(app)` [injected wins, else a lazily-cached local NLI — the
  citations.py pattern]). `app.state.citation_context_jobs`; registered **before** `papers.router`. Any failure →
  `mark_error`, never a crash.
- **`app/backend/api/app.py`** — `citation_context_jobs` JobStore + an injectable `semantic_scholar_client`
  `create_app` param + `app.state` + `include_router(citation_context.router)` before papers.
- **`app/frontend/js/08c_methods_citation_context.jsx`** (NEW) — a METHODS section "How this paper is cited" (order
  36): **Fetch citations** → the counts breakdown (reusing the `.citec-count` colors: support green / contrast amber /
  mention neutral) + a list of citing sentences, each with a `.cite-stance` pill + confidence + the citing paper
  (link) + an "influential" marker + a coverage line + the credit block. Reuses `.cite-equity-*` intro/report +
  `.cite-stance` + `.method-credit`; a small `.citec-*` recipe (tokens only, rule #8).

## Credit the lineage

scite (Nicholson et al. 2021, *Quantitative Science Studies*) — the tool this echoes — is credited in the panel + one-
click added to the library (the inc-93 import path). Semantic Scholar (Allen Institute for AI) is credited as the
data source in-panel + in `THIRD-PARTY-NOTICES.md`.

## Verification

`HF_HUB_OFFLINE=1 python -m pytest tests/test_citation_context.py -q` → **6 passed** (hermetic — a fake S2 fetcher + a
fake NLI, no network/model): the client parses/paginates/caps + validates the DOI [no request on a non-DOI] +
fails-closed without poisoning the cache + path-encodes the DOI; the classifier counts + keeps evidence + never
guesses [no `score` key]; the endpoint 202→poll→done, 404/422, no-citations→honest empty. Full suite **831 passed, 1
skipped**. QA surface **169/169 API + 733/733 FE, 0 uncovered** (`route_53_citation_context.md`). No migration, no new
dependency; **public-metadata egress (DOI → Semantic Scholar), NOT the Gemini gate**; classification local. Audit
`.claude/security-audits/2026-07-01_citation-context.md` PASS.

**The live Semantic Scholar round-trip on a real DOI is the maintainer's spot-check** (needs network; the
classification + the contracts are pytest-proven).

## Deferred

**SP2 — the outgoing direction** ("how this paper cites its own sources"): detect each in-text citation, link it to a
reference, classify the stance. Fiddlier (our extraction doesn't parse structured citation markers) → its own
increment. Also possible later: Semantic Scholar intents as a supplementary tag; a library-wide "most-contested /
most-supported" facet; caching the report.
