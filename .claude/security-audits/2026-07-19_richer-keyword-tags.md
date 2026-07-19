# Security Audit — Richer keyword tags (OpenAlex topics + PubMed MeSH)

**Date:** 2026-07-19
**Increment:** 306
**Trigger:** audit gate #3 (a new external-response parse path — PubMed MeSH XML) + #5 (net-new feature spanning
3+ files: `work_keywords.py`, `adapter.py`, `pubmed_provider.py`, `enrich_sources.py`, `enrichment.py`).

## Change under review
Import two more imported-keyword tag sources during the multi-pass metadata enrich, joining the existing
`keyword:crossref` (inc 73): **`keyword:openalex`** (curated OpenAlex topics) and **`keyword:pubmed`** (PubMed
MeSH descriptors). Driven off the enrich **registry** — a source that advertises `keyword_source` + `keywords()`
has its terms imported as additive, deletable, inc-143-suppressible tags. Backend-only (the frontend
`tagSourceLabel` already renders both provenances).

## Threat review
- **New external parse (untrusted input, rule #4) — PubMed MeSH XML.** `pubmed_provider._parse_mesh` uses a
  **targeted regex over the response text**, NOT an XML parser (`_MESHLIST_RE` → `_DESCRIPTOR_RE`, mirroring the
  existing `_parse_abstracts`, the inc-75 arXiv pattern). **No `xml.etree`/`lxml`, so no XXE / entity-expansion /
  external-DTD surface.** Descriptor names are read only from inside the `<MeshHeadingList>` block, `html.unescape`
  + tag-stripped, deduped. Malformed / partial / non-XML input → `{}` (never raises).
- **SSRF / request forgery.** `fetch_mesh_terms` hits a **constant host** (`EUTILS` efetch); PMIDs are
  **digit-validated** (`p.isdigit()`) before they enter the `id=` param — no attacker-controlled URL. Non-200 or
  empty body → `{}` (fail-closed). Same shape as the audited `fetch_abstracts`.
- **Egress posture (invariant #3).** All fetches are **public bibliographic metadata** (OpenAlex works, PubMed
  efetch) — the inc-87/183/210 posture, **NOT** the Gemini library-text gate. No library text leaves the machine.
  - **OpenAlex topics = zero extra egress:** `fetch_work_keywords` reads the **cached** work the enrich cascade
    already fetched (same client + ref → cache hit); the `keywords_from_work` extraction is a pure function.
  - **PubMed MeSH = one extra efetch** per biomedical paper *with a PMID*, during a user-initiated enrich only.
    Bounded, cached-host, fail-closed. Folding it into the existing abstract efetch is a noted future optimization.
- **Injection / SQL (rule #3).** Tags are written through `tags_repo.add_tags_to_paper` (bound-param Core, the
  same path as `keyword:crossref`); names are display strings, capped at `TAG_NAME_MAX`, never interpolated.
- **Facts vs candidates / no opaque score (principles 3, 7).** Imported keywords are facts from a **named index**,
  source-labeled (`keyword:openalex`/`keyword:pubmed`), deletable + suppressible — never presented as user tags or
  AI candidates. OpenAlex confidence scores are used **only to filter noise server-side** (topics ≥ 0.3; concepts
  fallback additionally drops level-0) and are **never surfaced** — the tag is just a name with a visible source.
- **Resource caps.** OpenAlex keywords capped at `max_terms=5`/work; MeSH prefers the *major* headings (a handful
  of primary subjects, not the full ~10-15 including generic check-tags), one batched efetch; no unbounded growth.
- **Secret handling / new deps.** None — no secrets, no new third-party dependency (httpx already present).

## Negative-path checks (run)
- `_parse_mesh` on no-`MeshHeadingList`, no-PMID, and non-XML input → `{}` (test_pubmed_provider).
- `fetch_mesh_terms` with non-digit/empty PMIDs → **no HTTP call** made; non-200 → `{}` (monkeypatched transport).
- `keywords_from_work` on `None`/`{}`/malformed topics → `[]` (test_openalex_work_keywords).
- **Hermeticity / no-surprise-egress:** an empty or stub registry (no keyword-capable source) imports **no**
  keyword tags and makes **no** network call — verified by `test_enrich_without_keyword_capable_source…` and by the
  unchanged, green `test_retraction` (which drives the enrich route with an empty `EnrichmentRegistry()`).
- **Suppression (inc 143):** a deleted `keyword:*` tag is not re-added on re-enrich (integration test).

## Verdict
**Security Audit: PASS.** New parse is XXE-safe (targeted regex, no XML parser); requests are constant-host +
digit-validated (no SSRF); egress is public metadata (not the library-text gate), OpenAlex adds zero and PubMed one
bounded fail-closed call; no opaque score surfaced; tagging is hermetic-by-construction (registry-gated). Full
suite green recorded in `INCREMENT-306-NOTES.md`.
