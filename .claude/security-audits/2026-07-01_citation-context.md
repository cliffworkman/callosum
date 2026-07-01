# Security Audit — Citation context "how this paper is cited" (B4 SP1, inc 232)

**Date:** 2026-07-01
**Feature:** `POST/GET /papers/citation-context/run` — fetch a paper's **citing sentences** from Semantic Scholar,
classify each stance **locally** (support / contrast / mention). Files: `integrations/semantic_scholar/adapter.py`
(new client), `app/backend/methods/citation_context.py` (pure classifier), `app/backend/api/routers/citation_context.py`
(async endpoints), `app/backend/api/app.py` (wiring), `app/frontend/js/08c_methods_citation_context.jsx` (panel).

**Audit-gate triggers:** a new API endpoint (#1) + a new external fetch/integration (#2 — Semantic Scholar). **NOT
triggered:** a new file-ingestion path (#3) or a new pip dependency (#6 — httpx already pinned; the local NLI reused).

## Threat review

- **SSRF / injection (the new fetch).** `fetch_citation_contexts` accepts only a paper's DOI (from the trusted
  `papers.doi` column, never client-typed path input). The DOI is (a) shape-validated (`^10\.\d+/\S+$`) and (b)
  **fully url-encoded** with `quote(doi, safe='')` before it enters the path `/paper/DOI:{doi}/citations`, so every
  reserved character (`/ : ? #` …) is percent-encoded — the host is always the constant `S2_BASE_URL` and no value can
  break out of the path segment. Query params (`fields`/`offset`/`limit`) are constants / bounded ints. The optional
  `CALLOSUM_S2_API_KEY` goes in an `x-api-key` header (never a URL/log), env-only, write-only.
- **Resource caps (rule #4).** `MAX_CITATIONS = 500` bounds the pages pulled per paper; `S2_PAGE_SIZE`-bounded pages;
  a `timeout` on each request; the classifier caps at `MAX_ITEMS = 500` and truncates each context to `CONTEXT_MAX`
  before the NLI. The job is async + ephemeral (in-memory `JobStore`).
- **Fail-closed + honest caching.** A network/parse error or non-200 → the fetch stops and returns whatever it has;
  a **transient first-page failure is NOT cached** (`got_ok` guard) so a "0 citations" answer is never poisoned by a
  blip — only a real 200 is cached. Any worker failure → `mark_error`, never a crash. Defensive parsing (`_parse`
  tolerates missing/oddly-typed fields).
- **Egress.** The only thing that leaves is the paper's **DOI** → Semantic Scholar (public bibliographic metadata) —
  the OpenAlex/Crossref posture. The **stance classification runs entirely locally** (our NLI). This is **NOT** the
  Gemini library-text gate; no draft/library text is sent anywhere. Stated in the router + client docstrings.
- **Output encoding.** Citing titles/sentences are external strings rendered by React as text (auto-escaped — no
  `dangerouslySetInnerHTML`); the citing-paper link is `https://doi.org/{doi}` from the parsed DOI.
- **Honesty (Principles gate, run in the design).** The aggregate is **counts, never a composite score** (#7); every
  classified citation carries its **real citing sentence** as evidence (#4); the stance is a **labeled signal, not a
  verdict** (#2 — a local NLI over the citing sentence vs the focal claim, shown with confidence); an unclassifiable
  citation is **counted, never guessed** (#6); a "contrast" describes the shown sentence's rhetorical relationship,
  never an accusation of an author (A-A).
- **Supply chain.** No new pip dependency (httpx + the existing local NLI). Semantic Scholar (Allen Institute for AI)
  is credited as the data source in-panel + `THIRD-PARTY-NOTICES.md`; scite (the tool this echoes) is credited +
  library-addable (credit-the-lineage).

## Negative-path checks (all in `tests/test_citation_context.py`, hermetic — a fake S2 fetcher + a fake NLI)

- Non-DOI id → **no request made** (returns []). ✔
- Transient failure → [] and **not cached** (a retry succeeds). ✔
- The DOI is path-encoded in the request (`/paper/DOI:10.1%2Ffocal/citations`). ✔
- Unclassifiable citation (no sentence) is counted, never guessed; no `score` key in the report. ✔
- Endpoint 404 (no paper) / 422 (no DOI) / 404 (unknown job) / no-citations → honest empty. ✔

**Security Audit: PASS.** Public-metadata egress (DOI → Semantic Scholar, not the Gemini gate); SSRF-safe
(shape-validated + fully url-encoded DOI, constant host); bounded/paginated/capped; fail-closed with honest,
non-poisoning caching; local classification; no new dependency. Re-audit if a library-wide batch or a non-DOI lookup
path is added.
