# Increment 189 — Feed SP2c-1: the PubMed-keyword source + a data-driven Follow picker

Backlog #28 SP2c. Makes the Feed **multi-source**: a saved **PubMed query** joins bioRxiv-by-category, and the Follow
UI becomes a **data-driven source picker** (rendered from backend metadata), so the next source needs no frontend edit.

## Implemented

- **`app/backend/discovery/pubmed_provider.py`** — `PubMedKeywordFeedSource` (`kind="pubmed_query"`, label "PubMed
  search"): polls `esearch` **sorted by date** (`_eutils_search` gained a `sort` param, default "relevance" for
  Search) → esummary → `record_to_feed_entry` (maps a record → `FeedEntry`, posted_date from `sortpubdate`,
  dedup_key DOI→PMID→title; drops no-title-and-no-DOI). Reuses the already-audited NCBI E-utilities plumbing
  (constant host, query as a bound param → no SSRF).
- **`app/backend/discovery/feed.py`** — `FeedSource` gains optional display metadata (`label`/`placeholder`/
  `suggestions`); `FeedRegistry.source_meta` exposes it (defensive `getattr` defaults). `build_default_feed_registry`
  now registers **bioRxiv + PubMed-keyword**.
- **`app/backend/discovery/biorxiv_source.py`** — `BIORXIV_CATEGORIES` moved here (the backend owns the suggestions);
  `BioRxivFeedSource` gains `label`/`placeholder`/`suggestions`.
- **`app/backend/api/routers/feed.py`** — `GET /feed/subscriptions` returns `source_meta` (no new endpoint).
- **`app/frontend/js/30e_feed.jsx`** — the Follow row is **data-driven**: a source `<select>` (shown when >1 kind),
  the value input with the selected kind's **placeholder** + a **datalist** from its suggestions, and `follow()` posts
  the selected `kind` (bioRxiv categories lowercased; PubMed queries keep casing). Subscription chips show a small
  source tag (`.feed-sub-kind`). The hardcoded category list is gone (now from `source_meta`).

## Key technical detail

- **The registry promise extends to the Feed UI:** because the Follow picker renders from `source_meta`, adding the
  next Feed source (e.g. journal-by-ISSN, SP2c-2) is one backend `register()` + the source's metadata — **no frontend
  edit**.
- **No import cycle:** `pubmed_provider` imports `FeedEntry` from `feed.py`; `feed.py` lazily imports the sources only
  inside `build_default_feed_registry()` (verified by an import smoke test).

## Manual verification script

Hermetic: `pytest tests/test_feed.py` (PubMed feed mapping + sort=date + registry `source_meta`). **Live spot-check:**
`PubMedKeywordFeedSource(email=<contact>).fetch("crispr off-target", limit=3)` → 3 recent records, newest-first.
**Headed, no egress** (`.local/visual/drive_inc189_feedsources.py`, two fake sources): the source `<select>` shows
both labels, switching to PubMed updates the placeholder, **Follow** creates a PubMed-tagged subscription, **Refresh**
polls it → 1 item; 0 console/page/genai. PASS.

## Gates

- **pytest 651** (+1 net: a PubMed-feed test; the default-registry test expanded to assert both sources +
  `source_meta`; the endpoint test asserts `source_meta`). `ruff` check + `format --check` clean.
- **Audit:** addendum to `.claude/security-audits/2026-06-28_feed.md` **PASS** (PubMed feed reuses the audited NCBI
  host; the only new wrinkle is `sort="date"`, a bound param; `source_meta` is non-secret display metadata; no new
  endpoint/migration/dependency).
- **QA (rule #10):** no new API/FE surface beyond the existing `/feed/*` + `30e_feed.jsx` (the `<select>` + datalist
  are claimed by `route_44`) → surface **132/132 API + 655/655 FE, 0 uncovered**.
- **help corpus:** the Feed section now covers PubMed searches as a source (`HELP-DOCS-SYNCED` → 189).
- **No migration, no new dependency, no new endpoint.**

## NEXT (#28 optional/later)

- **SP2c-2:** a journal-by-ISSN Feed source (Crossref `/works?filter=issn:…&sort=published`) — one `register()` + its
  metadata; the Follow picker already supports it. Its own audit (Crossref host, already audited).
- **SP2c-3:** an optional auto-refresh cadence; PubMed abstracts via efetch.
