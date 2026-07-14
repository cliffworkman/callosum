# Security audit — multi-pass, gap-filling metadata enrichment (inc 217, SP1)

**Date:** 2026-06-30
**Feature:** a multi-source, gap-filling enricher (`enrich_paper_metadata_multi`) + a pluggable source registry
(`enrich_sources.py`: Crossref-by-DOI → OpenAlex; SP2 adds Europe PMC + PubMed) + a library-wide async batch
(`POST/GET /library/enrich/refresh`) + a per-paper `POST /papers/{paper_id}/fill-metadata`. Plan:
`.claude/backups/plans/2026-06-30_metadata-multi-enrich.md`.

**Audit gate triggers:** (1) new API endpoints (3); (2) external metadata fetches newly in the enrichment path
(OpenAlex `fetch_work_csl`; the Crossref title-search `CrossrefSearchProvider`); (5) a net-new feature spanning
3+ files. No new external *host* (Crossref + OpenAlex are already-audited adapters). No new dependency. No migration.

---

## Threat review

### Data egress / consent posture

- The cascade sends **DOIs / PMIDs / titles** to **public bibliographic registries** (Crossref `/works/{doi}`,
  Crossref `/works?query=` for title-search, OpenAlex `/works`). This is **public-metadata egress** — the same
  posture as DOI re-resolve (inc 49), library scan (inc 87), discovery search (inc 183), and citation counts
  (inc 210). It is **NOT** the Gemini **library-text** egress gate (invariant #3): no abstract/body/note text is
  sent *out* — only identifiers and the paper's own title (for DOI recovery), exactly as discovery/acquisition
  already do. The route_48 standing assertion + the hermetic tests confirm **no `generativelanguage`/genai host**
  is ever contacted by enrichment. The Gemini gate is a separate channel, untouched.
- Polite-pool `mailto` comes from `app_settings.resolved_mailto(...)` (Settings → Metadata access, overlaying the
  env var), the established pattern. No secret is introduced.

### Non-destructiveness (the core safety property)

- **Gap-fill only.** `gap_merge` fills a CSL key **only** when the existing value is absent/empty (`_is_empty`),
  and `_gap_fill_columns` emits a scalar-column update **only** when the paper's current column is empty. A value
  the user typed is therefore **never overwritten** — proven by `test_gap_fill_never_overwrites_populated_fields`.
  This is a *strict improvement* over the existing wholesale `enrich_paper_metadata_from_crossref` (which the new
  path does not touch — that stays the explicit force-overwrite re-resolve).
- **Provenance never downgraded.** A `user-edited` / `merged` / `ai-agent` paper keeps its `imported_source` (only
  its blanks are filled), so it stays protected from the wholesale path and its origin stays honest
  (`test_user_edited_provenance_preserved_blanks_filled`). Running the batch over *all* live papers is therefore
  safe by construction — there is no "clobber a curated record" path.

### DOI recovery — wrong-DOI guard and duplicate-merge signal

- A missing DOI is recovered from the PDF (`find_doi_in_pdf`, existing) or a Crossref title-search, and adopted
  **only** on a conservative title match (`_titles_match`: normalized-equal or token-Jaccard ≥ 0.7) **and** a
  compatible year (`_years_compatible`). A weak or year-mismatched candidate is rejected — the paper stays without
  a DOI (honest) rather than acquiring a wrong one (`test_doi_recovery_strong_match_adopts_weak_and_mismatch_reject`).
- A recovered DOI that already belongs to a **different** library paper is now written after the conservative match.
  This creates an explicit duplicate signal so a raw-PDF record can be merged with a metadata-only record. A
  fragment's own DOI never sets the column — only the guarded effective DOI does (`merged["DOI"] = doi`).

### SSRF / external calls

- Every fetch goes to a **constant host** (the Crossref / OpenAlex adapters' hardcoded base URLs); the only
  request-controlled inputs are the DOI / PMID / title, passed as **query params / path segments**, never as a
  user-supplied URL. No SSRF surface is introduced. Each client is **fail-closed** (any non-200 / exception →
  `None`), and the registry's `fetch_all` skips a source that raises — one bad source never breaks the cascade or
  500s an endpoint.

### Input validation / injection

- The endpoints take only a `paper_id` (path int) — a missing paper → 404 (`get_paper`/`NoResultFound`). No request
  body carries free text into the enricher. All DB writes are SQLAlchemy Core bound parameters (`update_paper_metadata`,
  `find_existing_paper_by_identity`); table/column names are constants. `csl_json` is written as a JSON column
  (bound), never concatenated.

### Output encoding

- Filled abstracts may be raw JATS (Crossref) or plain text (OpenAlex) — stored verbatim in the `abstract` column
  exactly as the existing enrich path does; the Detail pane renders them through the existing allowlisted
  `abstract_plain_text` / `clean_abstract_for_display` (inc 33/55), so no new XSS surface.

### Resource caps / abuse

- The batch iterates a **bounded** set (`list_live_paper_ids` — live papers only) in one transaction, one pass.
  Each source is **cache-first** (`external_api_cache`), so a re-run is cheap and bounded. The frontend poll loop is
  capped (~12 min) and the job continues server-side regardless. Under Remote access (inc 168) the bearer-token gate
  + rate limiter already throttle `/library/*` + `/papers/*`. (Like the scan/edit routes, `/library/enrich/*` carries
  a server-side fetch + mutation, so it stays off any cloudflared cite-only ingress allowlist — recorded for the
  pre-hosted-deploy pass.)

### File-path safety / supply chain

- No new file path is built from request data (DOI recovery reads existing attachment paths via the existing
  `_doi_for_paper`). No new dependency — Crossref/OpenAlex/discovery clients all pre-exist.

---

## Negative-path checks run (hermetic, `tests/test_metadata_multi_enrich.py`)

- Populated field never overwritten; provenance preserved on a `user-edited` paper. ✓
- DOI recovery: strong match adopts; weak match + year mismatch reject; duplicate DOI is written for merge cleanup. ✓
- Cascade fills `abstract` from a later source when the first lacks it. ✓
- Scaffold with no DOI + no recovery → `crossref-unresolved` (honest), `still_missing_doi=True`. ✓
- `_csl_from_work` maps venue/abstract/type/DOI/PMID; `None` → `None`. ✓
- Per-paper + batch endpoints behave; unknown job → 404; offline OpenAlex (404) + no-op search keep it hermetic
  (no genai host contacted). ✓

---

**Security Audit: PASS.**

SP2 (Europe PMC + PubMed sources) extends the same cascade under the **same posture** (public-metadata egress,
constant audited hosts, fail-closed, gap-fill-only) — each is one `register()` + a response mapper; covered by the
addendum below.

---

## Addendum — SP2: Europe PMC + PubMed sources (inc 218)

Two sources added to the cascade, each behind the existing `EnrichmentSource`/registry contract — **no new
endpoint, no new external host, no new dependency, no migration** (both reuse already-audited adapters/hosts).

- **`EuropePmcEnrichSource`** (DOI/PMID-keyed): a new `EuropePmcClient.lookup_metadata(conn, ref)` reads the **same
  cached `resultType=core` record** the OA resolver (`lookup_oa`) already fetches from the constant
  `www.ebi.ac.uk/europepmc/...` host (cache-first via the shared `external_api_cache`), and maps title/authors/
  journal/year/abstract/DOI/PMID → a CSL fragment. No new fetch path; SSRF-safe (DOI/PMID as a bound query param).
- **`PubMedEnrichSource`** (PMID → efetch abstract; else title-search → matched record's metadata + abstract): reuses
  the audited `pubmed_provider` helpers (`_eutils_search` esearch→esummary, `fetch_abstracts` efetch, `summary_to_item`)
  against the constant NCBI E-utilities host, query/ids as bound params (the inc-186/191 SSRF posture). The
  **title-search path adopts a record only on a conservative title match** (`_title_overlap`: normalized-equal or
  token-Jaccard ≥ 0.7) — no wrong-paper enrichment; the efetch abstract parse is the regex (not an XML parser) →
  no XXE. Both fetchers are fail-closed (any error → no fragment).

These only **add fragments** to the gap-fill cascade — the merge is still fill-empty-only and the provenance/
DOI/duplicate guards (above) are unchanged, so the non-destructiveness + honesty properties hold identically.
Egress remains **public bibliographic metadata** (a DOI/PMID/title to Crossref/OpenAlex/Europe PMC/NCBI), **not**
the Gemini library-text gate. Negative paths re-checked: the Europe PMC `core`→CSL mapper; the PubMed PMID-abstract
+ title-match-adopt + title-mismatch-reject paths; the default registry is exactly `[crossref, openalex, europepmc,
pubmed]` (`tests/test_metadata_multi_enrich.py`).

**Security Audit (SP2 addendum): PASS.**

---

## Increment 226 addendum — per-identifier re-fetch (PMID / arXiv → OpenAlex)

The Details → Identifiers 🔎 (DOI → Crossref re-resolve, inc 49) is generalized to **PMID** and **arXiv**:
each calls `POST /papers/{id}/re-resolve {source}` (`routers/paper_enrich.py`, split out of `papers.py` to keep
both under the 600-line cap). The new `source` is an allowlisted `Literal["crossref","pmid","arxiv"]` (default
`crossref` → byte-for-byte the prior DOI behavior + back-compat with the no-body POST).

- **No new external host / fetch path / dependency.** `pmid`/`arxiv` reuse the **already-audited**
  `OpenAlexClient.fetch_work_csl(conn, ref)` (the inc-217 enrich client): `pmid` → `PaperRef(pmid=<csl PMID>)`;
  `arxiv` → `PaperRef(doi="10.48550/arXiv.<csl arxiv>")` (the synthesized arXiv DOI, the `_ARXIV_DOI_RE` form).
  Egress is the same **public bibliographic metadata** posture (a PMID/DOI to OpenAlex's constant host as a bound
  path segment → no SSRF), **not** the Gemini library-text gate.
- **Overwrite is the force path** (`enrich_paper_metadata_from_identifier`, `force=True` from the endpoint, the
  user's explicit "re-fetch from *that* source" intent — mirrors the DOI 🔎): the resolved CSL projects through
  `_paper_values_from_csl(record, imported_source="openalex")` + `update_paper_metadata` (full wholesale
  overwrite, the inc-49 primitive). `OPENALEX_SOURCE` is added to the `_can_update_from_crossref` allowlist so a
  re-fetched record is treated as resolved+updatable (like `crossref`), never protected like `user-edited`. The
  **inc-174 confirm guard** in the frontend still gates overwriting a `user-edited` record.
- **Provenance honesty / identifier preservation:** `_csl_from_work` echoes PMID but **not** the arXiv id, and the
  projector replaces `csl_json` wholesale — so the orchestrator `setdefault`s the clicked identifier back onto the
  record before overwrite (the source id is never silently dropped). The tradeoff (re-fetching from PMID/arXiv may
  yield an OpenAlex record thinner than a prior Crossref one) is the user's explicit intent.
- **Negative paths:** identifier absent from `csl_json` → **422** (no fetch, no overwrite); a fetch miss → **no
  overwrite**, the row keeps its data, the UI warns (graceful 200, never 500). Covered by
  `tests/test_papers.py` (`test_reresolve_from_pmid_overwrites_via_openalex`,
  `test_reresolve_from_arxiv_uses_synthesized_doi`, `test_reresolve_from_identifier_miss_is_graceful`,
  `test_reresolve_from_identifier_422_when_absent`) via an injected fake OpenAlex client (hermetic, no network).
- **No migration, no new QA route** (paths unchanged → surface map still 161/161 API + 719/719 FE, 0 uncovered;
  the optional `source` param is noted on `route_30_detail_pane.md`). The router split is behavior-preserving.

**Security Audit (inc 226 addendum): PASS.**
