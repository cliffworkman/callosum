# Design — Citation context: "How this paper is cited" (B4 SP1, the scite analogue)

## Context

Backlog **B4** — a library-level citation-context classifier (a **scite** analogue). When you're deciding whether to
rely on a paper, it matters *how the literature has responded to it*: do later papers **support** it, **contrast**
it, or merely **mention** it? Today callosum can't tell you. This adds a per-paper METHODS panel — **"How this paper
is cited"** — that fetches the actual **citing sentences** from **Semantic Scholar** and classifies each one's stance
**locally** with our own NLI, so you see the real sentence + a labeled stance + confidence, aggregated as honest
counts (never a single "score").

**Maintainer decisions (AskUserQuestion):**
- **Direction:** *incoming first* — "how this paper is cited" (the scite headline). Outgoing ("how this paper cites
  its own sources") is a deferred follow-up (it needs fiddly in-text-citation → reference linking).
- **Classification:** *our local NLI stance* (supports / contrasts / mentions), reusing the inc-156 `NLIStanceScorer`
  — grounded, inspectable, no classification egress; the label is a hint over shown evidence, never a verdict.

## Architecture

A per-paper **async job**, in the shape of `routers/citation_equity.py` (validate → JobStore → worker → poll).

1. **`integrations/semantic_scholar/adapter.py` (NEW)** — a `SemanticScholarClient` mirroring the OpenAlex/Crossref
   adapters: an injectable `fetcher`, a shared `api_cache`, fail-closed. `fetch_citation_contexts(conn, doi) ->
   list[CitingContext]` calls the S2 Graph API
   `GET /graph/v1/paper/DOI:{doi}/citations?fields=contexts,isInfluential,citingPaper.title,citingPaper.year,citingPaper.authors,citingPaper.externalIds`
   (paginated, **capped** at e.g. 500 citations / N pages — rule #4). The DOI is a **validated** path segment (a
   bounded DOI-shape check → no SSRF; constant host). Each `CitingContext` carries the citing paper (title/year/
   authors/DOI) + its **context sentence(s)** + `isInfluential`. Optional `CALLOSUM_S2_API_KEY` (write-only, raises
   rate limits; the API works without one at a lower limit — the Crossref-mailto posture).
2. **`methods/citation_context.py` (NEW, pure)** — `classify_citation_contexts(*, contexts, focal_claim,
   stance_scorer) -> CitationContextReport`: for each citing sentence, `stance_scorer.classify_stance(sentence=<citing
   sentence>, passage=<focal paper's claim>)` (the focal claim = the library paper's abstract, else its title) →
   `support|contrast|mention` + confidence; a context with no sentence or a `None` stance is counted in **coverage**,
   never guessed. Aggregate **counts** (`supporting`/`contrasting`/`mentioning`/`unclassified`) + keep every
   classified item's evidence (the sentence, the citing paper, the stance, the confidence, isInfluential). **No
   composite score.**
3. **`routers/citation_context.py` (NEW)** — `POST /papers/citation-context/run {paper_id}` (202; 404 no paper / 422
   no DOI) + `GET /papers/citation-context/run/{job_id}`; worker: resolve DOI → `fetch_citation_contexts` →
   focal_claim from the library row → `classify_citation_contexts` (local NLI on `app.state`) → report. `app.state.
   citation_context_jobs`; registered **before** `papers.router` (`/papers/citation-context/*`). Fully **local
   classification**; the only egress is the DOI → Semantic Scholar fetch (public metadata, cached), **NOT** the Gemini
   gate.
4. **Frontend `08c_methods_citation_context.jsx` (NEW)** — a METHODS section "How this paper is cited" (a **Fetch
   citations** button, since it's user-initiated egress): the breakdown as **counts** (N supporting · M contrasting ·
   K mentioning · U unclassified) + a list of citing items — each a **stance pill** (support green / contrast amber /
   mention neutral — the inc-203 status colors) + confidence + the citing paper (title · authors · year, a link) +
   the **citing sentence** (the evidence) + an "influential" marker + an honest coverage line + the credit block.

## Honesty — Principles alignment gate (rule #9)

- **Principles touched:** #1 (Semantic Scholar's contexts are *candidates*, never authoritative — we classify
  **locally** and show the sentence), #2 (**signal, not verdict** — the stance is a hint over the shown citing
  sentence), #4 (**evidence always shown** — the real sentence + confidence), #7 (**no opaque composite** — counts +
  evidence, **never** a single "scite score"). Worked example: the statcheck / inc-156-suggest class (a labeled signal
  about the literature, carrying its evidence).
- **The misaligned easy path (declined):** a single "supported/disputed **score**" or a verdict ("this paper is
  contested") shown *without* the sentences; or relaying Semantic Scholar's own intent labels as authoritative. We
  decline all of these — the breakdown is counts, every item shows its sentence + our stance + confidence, and the
  copy frames it as "a labeled signal to read, not a verdict."
- **A-A no-accusation:** a "contrasting" label describes the rhetorical relationship *in a specific, shown sentence*,
  never an accusation about an author. The stance is approximate (an NLI over the citing sentence vs the focal paper's
  claim, which may be only a title when no abstract exists) — stated honestly as a coverage/quality caveat.
- **Egress:** DOI → Semantic Scholar = public bibliographic metadata (the OpenAlex/Crossref posture), user-initiated,
  cached — **NOT** the Gemini library-text gate. The classification runs entirely locally.

## Credit the lineage

This is a **scite** analogue → credit **scite** in the panel + one-click library-add (Nicholson et al. 2021, *"scite:
A smart citations index that displays the context of citations,"* Quantitative Science Studies), and credit
**Semantic Scholar** (Allen Institute for AI) as the data source, in the panel + `THIRD-PARTY-NOTICES.md`.

## Gates & scope

- **Security audit** (`.claude/security-audits/2026-07-01_citation-context.md`) — new integration (#2) + new endpoint
  (#1): SSRF-safe (constant S2 host, DOI validated + path-encoded), bounded/paginated/capped, fail-closed, optional
  key write-only, public-metadata egress (not Gemini). **No new pip dependency** (httpx; reuse the local NLI). **No
  migration** (ephemeral job result, like citation-equity).
- **SP1 scope:** incoming citations, local NLI stance, one per-paper panel. **Deferred:** outgoing ("how this paper
  cites its sources"); Semantic Scholar intents as a supplementary tag; a library-wide "most-contested/most-supported"
  facet; caching the report (v1 recomputes; the S2 fetch is cached).

## Verification

- **pytest** `tests/test_citation_context.py` (hermetic — an injected fake S2 fetcher returning canned
  contexts + a fake stance scorer): the adapter parses/caps/paginates + fails closed + validates the DOI; the pure
  classifier maps stance→counts, keeps evidence, counts unclassified (no guess); the endpoint 202→poll→done, 404/422,
  no-contexts→honest empty. Full suite green.
- **Live spot-check** (the maintainer): run on a real DOI'd paper → real citing sentences classified. Headed: the
  panel renders the breakdown + sentences + stance pills + credit; **0 genai-host requests** (public-metadata egress
  only). `ruff`+`format`; `build_frontend` + assembly; QA `route_53_citation_context.md` 0-uncovered; docs.
