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

### DOI recovery — wrong-DOI + duplicate guards

- A missing DOI is recovered from the PDF (`find_doi_in_pdf`, existing) or a Crossref title-search, and adopted
  **only** on a conservative title match (`_titles_match`: normalized-equal or token-Jaccard ≥ 0.7) **and** a
  compatible year (`_years_compatible`). A weak or year-mismatched candidate is rejected — the paper stays without
  a DOI (honest) rather than acquiring a wrong one (`test_doi_recovery_strong_match_adopts_weak_and_mismatch_reject`).
- A recovered DOI that already belongs to a **different** library paper is **not** written
  (`find_existing_paper_by_identity` guard → left for dedup), which both avoids a mis-merge and honors the
  `papers.doi` UNIQUE constraint (`test_recovered_doi_colliding_with_another_paper_is_skipped`). A fragment's own
  DOI never sets the column — only the guarded effective DOI does (`merged["DOI"] = doi`).

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
- DOI recovery: strong match adopts; weak match + year mismatch reject; duplicate DOI skipped. ✓
- Cascade fills `abstract` from a later source when the first lacks it. ✓
- Scaffold with no DOI + no recovery → `crossref-unresolved` (honest), `still_missing_doi=True`. ✓
- `_csl_from_work` maps venue/abstract/type/DOI/PMID; `None` → `None`. ✓
- Per-paper + batch endpoints behave; unknown job → 404; offline OpenAlex (404) + no-op search keep it hermetic
  (no genai host contacted). ✓

---

**Security Audit: PASS.**

SP2 (Europe PMC + PubMed sources) extends the same cascade under the **same posture** (public-metadata egress,
constant audited hosts, fail-closed, gap-fill-only) — each is one `register()` + a response mapper; covered by an
addendum to this audit when it lands.
