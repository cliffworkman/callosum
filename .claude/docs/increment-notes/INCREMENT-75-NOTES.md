# Increment 75 — Literature acquisition: fan out the resolver cascade (B)

## Implemented
Increment A shipped a single OA resolver (OpenAlex) behind the `OaLocation` seam. Increment B **fans the
cascade out** to many authorized open-access sources, tried in gold→green→preprint order, **first authorized
copy wins** — purely additive to the proven seam (no endpoint, no migration, no new dependency, no frontend
change; the Acquire button + OA chips already work). Spec:
`.claude/docs/future-tracks/opus4.8_future-tracks_acquisitionclean.md`.

- **Shared helper** `integrations/api_cache.py` — `get_cached` / `put_cached` (provider+key upsert against
  `external_api_cache`), so each new adapter carries only its mapping logic. (The pre-existing
  openalex/crossref adapters keep their private copies — not refactored, to keep the diff minimal.)
- **Six new source adapters** (each: a `<Source>Fetcher` Protocol for hermetic injection, a `<Source>Client`
  with `lookup_oa(conn, ref) -> OaLocation | None`, a distinct cache `provider`, fail-closed, https-only):
  `integrations/doaj/` (gold; only when a bibjson link is a real PDF), `integrations/europepmc/` (OA full text
  when `isOpenAccess=Y` + a PMCID → the sanctioned `fullTextPDF` endpoint), `integrations/core/` (green;
  Bearer `CALLOSUM_CORE_API_KEY`; **no key → no-op**), `integrations/arxiv/` (preprint; arXiv id from the
  `10.48550/arXiv.*` DOI with **no fetch**, else a title search; the Atom id is read with a **targeted regex,
  not a stdlib XML parser** — avoids the XXE/entity surface, rule #4), `integrations/biorxiv/` (preprint; tries
  the biorxiv then medrxiv server, builds the `.full.pdf` URL), `integrations/osf/` (preprint, covers PsyArXiv;
  `embed=primary_file` → the https download link).
- **Crossref-OA** `integrations/crossref/oa.py` — reuses the existing `CrossrefClient` (and its DOI cache):
  returns an `OaLocation` **only** when the work carries a license (CC → gold, else bronze) AND a direct PDF
  `link` — never guesses OA.
- **Seven thin resolvers** `app/backend/acquisition/resolvers/{doaj,europepmc,crossref,core,arxiv,biorxiv,osf}_resolver.py`
  (delegate to the client; lazy real client) registered in `build_default_registry` after OpenAlex, in
  gold→green→preprint order. The `ResolverRegistry.resolve()` loop is untouched (closed to edits).
- Help corpus: a new **"Acquiring an open-access copy"** section (clears the inc-74 help debt; covers the
  cascade, OA color/version labels, the honest "no authorized copy found", local-first/egress posture, the
  optional CORE key).

## Key technical detail
The bright lines stay enforced **structurally**, not per-source: every adapter can only express an authorized
OA copy as an `OaLocation` (required OA color; https + non-IP host), and the downloader still takes an
`OaLocation`, never a bare URL. So adding six sources adds **zero** new ways to fetch a non-OA/arbitrary URL —
OA-ness is each database's assertion (DOAJ direct-PDF link / Europe PMC `isOpenAccess` / Crossref registered
license / CORE downloadUrl / preprint-server record), and a source with no honest https PDF returns None
rather than a landing page or a guess. The CORE key lives only in `CALLOSUM_CORE_API_KEY`, travels as a Bearer
header (never in a URL → never in the cache), and its absence makes the resolver a silent no-op.

## Manual verification script
1. `CALLOSUM_OPENALEX_MAILTO` (and optionally `CALLOSUM_CORE_API_KEY`) set in the gitignored `.env`.
2. `uvicorn app.backend.api.app:app --host 127.0.0.1 --port 8080`; open `http://127.0.0.1:8080/`.
3. On PDF-less papers, click **Acquire OA copy** for DOIs that exercise different sources — a DOAJ gold
   article, a bioRxiv/medRxiv DOI, a PsyArXiv (OSF) DOI, an arXiv DOI, a Europe PMC OA article, a CORE-only
   green copy. Confirm each imports with the right OA color/version/source chip (bronze rendered distinct), and
   a closed-only paper still shows the honest *"no authorized open-access copy found."*
   _(Hermetic tests cover the mapping per source; a real live pass against each source is still worth doing.)_

## Pytest
**334 passed, 1 skipped** (+31: per-source mapping + OA-flag honored + non-PDF/landing/non-https → None +
fail-closed + cache; CORE no-key no-op + Bearer sent; arXiv DOI-no-fetch + title-parse; bioRxiv server
fall-through; cascade first-hit + new-resolver-registers + default order; structural non-OA-color rejection).
`ruff` clean; no new route (route-surface unchanged), migration head stays **0007**. Security audit
`.claude/security-audits/2026-06-20_oa-acquisition-b.md` — **PASS**. **NEXT:** Increment C (wanted-list table +
an OA-DB-only re-check job + a coverage readout). The legally-ambiguous lane stays deferred/counsel-gated.
