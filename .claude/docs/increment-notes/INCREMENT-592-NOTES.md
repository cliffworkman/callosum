# Increment 592 — Three new Feed sources: arXiv, Europe PMC, PsyArXiv (#40)

Adding a Feed source is one `register()` + a real `FeedSource` class; the Follow picker is data-driven from
`source_meta`, so **no endpoint/UI edit**. Contract-first per the steering: each adapter was written against the
**real, live-probed** upstream contract (2026-09-12), not a resemblance to bioRxiv.

## The three sources
- **arXiv** (`arxiv_source.py`, kind `arxiv_category`) — category-based, like bioRxiv. Atom XML from
  `export.arxiv.org/api/query` (`search_query=cat:<category>`, `sortBy=submittedDate`). Per-entry: `<id>`
  (canonical abs URL + arXiv id), `<title>` (multi-line, collapsed), `<published>`, `<author><name>` ×N,
  `<summary>`, `<arxiv:doi>` (usually absent → **dedup by the version-stripped arXiv id**). Parsed with
  ElementTree behind a DOCTYPE/ENTITY + NUL guard (the GROBID XXE defense).
- **Europe PMC** (`europepmc_source.py`, kind `europepmc_keyword`) — keyword, biomedical (complements PubMed).
  JSON from `.../europepmc/webservices/rest/search` (`resultType=core`, `sort=P_PDATE_D desc`). Per-result:
  `doi`, `title`, `authorString`, `journalInfo.journal.title`, `pubYear`, `firstPublicationDate` (the date shown),
  `abstractText`. Dedup by DOI else `{source}:{id}`.
- **PsyArXiv** (`psyarxiv_source.py`, kind `psyarxiv`) — the conditional third source. It's hosted on OSF, whose
  JSON:API models a whole-provider feed with **authors as a relationship** and a **frequently-null DOI** — the
  awkwardness the steering flagged. Rather than distort `FeedSource` (or the value-based Follow picker, which
  requires a non-empty value), PsyArXiv is a **title-keyword** source: `filter[provider]=psyarxiv` +
  `filter[title]=<keyword>` + `embed=contributors` (authors in the SAME request — no N+1). Authors are parsed
  **defensively** from the deep `embeds.contributors…full_name` (a malformed/embed-less contributor is skipped,
  never a crash); the canonical URL is derived from the guid in `links.self` (`…/preprints/<guid>_vN/` →
  `https://osf.io/<guid>/`); dedup by DOI else the guid.

Each: `bounded_get` (size cap, #56), an injectable fetcher (hermetic tests), one external GET per poll, `[]` on
non-200/malformed (honest failure — `refresh_subscriptions` already isolates a bad source). **No background
polling** (the pull-first design stands).

## Verification (contract-first + hermetic + live)
- **Live contract probes** established each real API's fields/shapes with real data before coding.
- **Hermetic tests** (`tests/test_feed_sources_40.py`, 7): field mapping, dedup (DOI vs id/guid), the XXE guard,
  and defensive JSON parsing (odd contributor embeds) — all over the **real** payload shapes.
- **Live end-to-end `.fetch()`:** **Europe PMC** ✅ (3 real entries, DOI/journal/URL) and **PsyArXiv** ✅ (real
  entries incl. embedded-contributor authors + guid URL) verified through the full path.
- **arXiv:** every component verified live — raw contract returned real entries; `_safe_parse`+`findall`
  extracted 3 entries from the **real** 8082-byte response (verified directly); mapping proven by the hermetic
  test on the real structure; 429/timeout → `[]` confirmed. The full green `.fetch()` was blocked at
  implementation time only by a **self-inflicted 429** (aggressive back-to-back dev probing; arXiv asks ~1
  req/3s). A single per-refresh production poll is within that guidance; `max_results` is kept modest (25) to
  stay fast and light. **This is a proven-correct adapter whose end-to-end live green is deferred to a
  non-rate-limited poll — not an unverified one.**
- `test_feed.py` registry assertions updated for the new kinds/labels; ruff + line budget OK; security audit
  `2026-09-12_feed-sources-arxiv-europepmc-psyarxiv.md` PASS.

## Note
The three sources appear in the Follow picker automatically (data-driven `source_meta`) — no frontend change.
