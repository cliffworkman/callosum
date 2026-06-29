# Increment 190 — Feed SP2c-2: the journal-by-ISSN source

Backlog #28 SP2c-2. A third Feed source — **follow a journal by its ISSN** → its recent articles — that drops into the
registry with **no frontend/endpoint/surface change** (the inc-189 data-driven Follow picker rendered the new option
automatically). The clean proof of the registry promise: a new user-facing source in one backend file + a `register()`.

## Implemented

- **`app/backend/discovery/journal_issn_source.py`** (NEW) — `JournalIssnFeedSource` (`kind="journal_issn"`, label
  "Journal (ISSN)"): polls Crossref `/works?filter=issn:<issn>&sort=published&order=desc` (the **already-audited**
  Crossref host); the ISSN is **validated** (`^\d{4}-\d{3}[\dX]$`) before any request, then passed only as a bound
  `filter` param (no SSRF). `record_to_feed_entry` reuses the audited `crossref_provider.message_to_item` (→ Item,
  drops no-title-and-no-DOI) + `_published_date` (date-parts → `YYYY-MM-DD`). Injectable fetcher.
- **`app/backend/discovery/feed.py`** — `build_default_feed_registry` now registers bioRxiv + PubMed-keyword +
  **journal-by-ISSN**.

## Key technical detail

- **Zero frontend/surface change** — the Follow picker is data-driven from `source_meta` (inc 189), so the new source's
  `label`/`placeholder` render automatically; the QA surface map is unchanged (132 API / 655 FE). This is the registry
  promise proven end-to-end (backend → UI).
- **Reuses the audited Crossref mapping** (`message_to_item`) rather than re-deriving it, so a journal article's
  bibliographic fields map identically to a Search result.

## Manual verification script

Hermetic: `pytest tests/test_feed.py` (journal record mapping + posted_date + ISSN validation + injected fetcher).
**Live spot-check:** `JournalIssnFeedSource(mailto=<contact>).fetch("1476-4687", limit=3)` → 3 recent Nature articles.
**Headed, no egress** (`.local/visual/drive_inc190_journal.py` — the REAL `JournalIssnFeedSource` with a fake fetcher +
bioRxiv): the source `<select>` shows "Journal (ISSN)", the placeholder updates, **Follow** `1476-4687` → a
Journal-tagged subscription, **Refresh** → the polled article; 0 console/page/genai. PASS.

## Gates

- **pytest 652** (+1: the journal mapping/validation test; the default-registry test now asserts all three sources).
  `ruff` check + `format --check` clean.
- **Audit:** addendum 2 to `.claude/security-audits/2026-06-28_feed.md` **PASS** (Crossref host already audited; ISSN
  validated + bound filter param → no SSRF; no new dependency/endpoint/migration/surface).
- **QA (rule #10):** **no new surface** — the source is behind `/feed/*` + the data-driven picker → surface **132/132
  API + 655/655 FE, 0 uncovered** (unchanged).
- **help corpus:** the Feed section now lists journal-by-ISSN among the source types (`HELP-DOCS-SYNCED` → 190).
- **No migration, no new dependency, no new endpoint, no frontend change.**

## #28 status

**The discovery track (#28) is feature-complete:** Search (Crossref + PubMed + axis-relevance) + Feed (bioRxiv +
PubMed-keyword + journal-by-ISSN). Remaining is genuinely optional (**SP2c-3**): an auto-refresh cadence; PubMed
abstracts via efetch; medRxiv as a bioRxiv server option.
