# Increment 191 — Feed SP2c-3 (part 1): medRxiv source + PubMed abstracts (efetch)

Backlog #28 SP2c-3, the backend half. Two enrichments that round out the Feed's sources/content; **no frontend
change** (medRxiv rides the data-driven Follow picker; PubMed abstracts fill the existing Abstract toggle).

## Implemented

- **medRxiv source** (`biorxiv_source.py`): `BioRxivFeedSource` is now **server-configurable** (`server="biorxiv"|
  "medrxiv"`) — one class, instantiated per server → kinds `biorxiv_category` + `medrxiv_category`. `kind`/`label`/
  `suggestions` moved to instance attributes; the default fetcher bakes in the server (so injected fakes keep the
  `CollectionFetcher` signature); `_biorxiv_fetch` gained a `server` param (the server is a **fixed literal** in the
  URL path → no SSRF). `record_to_entry` derives the journal label + content-URL host from the record's own `server`
  field. New `MEDRXIV_CATEGORIES` (clinical subjects). `build_default_feed_registry` registers both servers.
- **PubMed abstracts via efetch** (`pubmed_provider.py`): `fetch_abstracts(pmids)` calls NCBI **efetch**
  (`rettype=abstract&retmode=xml`); `_parse_abstracts` extracts per-PMID abstracts with a **targeted regex** (split on
  `<PubmedArticle>`, PMID + `<AbstractText>` regex, strip inline tags, `html.unescape`) — **not an XML parser** → no
  XXE (rule #4, the inc-75 pattern). `PubMedKeywordFeedSource` gained an injectable `abstract_fetcher` (default
  `fetch_abstracts`) and enriches each entry's `abstract` after esummary; a failed efetch is swallowed (abstracts are
  a nicety, never load-bearing).

## Key technical detail

- **One preprint class, two servers:** making `kind`/`label`/`suggestions` instance attributes (set from `server`)
  lets a single `BioRxivFeedSource` serve both bioRxiv and medRxiv; the data-driven picker (inc 189) renders both from
  `source_meta` with no frontend edit. The `server` field on each API record drives the per-item journal label + URL,
  so a medRxiv item is labeled/linked correctly.
- **efetch is enrichment, not load-bearing:** wrapped in `try/except`; a non-200 or a parse miss → no abstract, the
  poll still returns its entries. Digit-validated PMIDs as a bound param → no SSRF; regex parse → no XXE.

## Manual verification script

Hermetic: `pytest tests/test_feed.py` (medRxiv server config + server-aware label/URL; efetch parse + enrichment +
fail-closed). **Live spot-checks:** `BioRxivFeedSource(server="medrxiv", …).fetch("epidemiology", limit=3)` → 3 real
medRxiv preprints; `PubMedKeywordFeedSource(email=<contact>).fetch("crispr gene therapy", limit=4)` → 3/4 entries
enriched with real abstracts (the 4th has none in PubMed → correctly empty).

**No headed run** — backend-only: medRxiv appears in the Follow picker via `source_meta` (the data-driven mechanism
proven headed in inc 189/190; the default-registry test asserts `medrxiv_category` is exposed), and efetch abstracts
populate the existing FeedPane Abstract toggle (no UI change).

## Gates

- **pytest 654** (+2: medRxiv server config; efetch parse/enrich/fail-closed; the default-registry test now asserts
  4 kinds). `ruff` check + `format --check` clean.
- **Audit:** addendum 3 to `.claude/security-audits/2026-06-28_feed.md` **PASS** (medRxiv = audited host + fixed-literal
  server segment; efetch = audited host, digit-validated ids, regex parse without an XML parser, fail-closed).
- **QA (rule #10):** no new API/FE surface → surface **132/132 API + 655/655 FE, 0 uncovered** (unchanged).
- **help corpus:** the Feed section lists medRxiv among the source types + notes PubMed items now carry abstracts
  (`HELP-DOCS-SYNCED` → 191).
- **No migration, no new dependency, no new endpoint, no frontend change.**

## NEXT — SP2c-3 (part 2), inc 192: the auto-refresh cadence

A frontend "auto-refresh on open" toggle (staleness-gated refresh when the Feed tab is opened + a subscription is
stale), mirroring the watched-folders on-launch rescan — pull-first, opt-in. That closes #28 entirely.
