# Increment 295 — Feed: follow journals by title (default) + Suggest-from-library + typeahead

The literature Feed's journal source was **by ISSN** — users don't know ISSNs. Make the Feed more useful: follow
journals **by title** (the new default), a **Suggest** button that opens a modal of the journals **already in your
library** (one-click Follow), and journal-title **predictions as you type** — all seeded from the user's own library.

## Implemented

- **Journal-by-title source (`discovery/journal_title_source.py`, new; `JournalIssnFeedSource` removed):**
  `JournalTitleFeedSource` (`kind="journal"`, `label="Journal"`). `fetch(title)` resolves the title → the journal's
  ISSN via Crossref `/journals?query=` (top match) then reuses the ISSN→works fetch for an **exact** recent-works
  list; falls back to a fuzzy `/works?query.container-title=` when no ISSN matches. Reuses the audited Crossref host +
  `crossref_provider.message_to_item`; the title is a URL-encoded query param, length-capped; injectable
  fetcher/lookup for hermetic tests.
- **`discovery/feed.py`:** register `JournalTitleFeedSource()` **first** so it's the Follow picker's default (the
  registry order drives the default); the ISSN source is dropped ("drop ISSN"). `schema_feed.py` kind comment updated.
- **`GET /feed/library-journals` (`routers/feed.py` + `feed_repo.list_library_journals`):** `[{journal, count}]`
  from `papers.venue` (live library, `GROUP BY venue ORDER BY count DESC`). **Read-only, local, no egress** — the
  user's own data, a transparent tally, not a ranking.
- **Frontend (`30e_feed.jsx`):** fetches `/feed/library-journals` on mount; when the source kind is `journal` the
  Follow `<datalist>` predicts from those library journals (typeahead); a **Suggest** button opens `FeedSuggestModal`
  (new, reuses the `axis-modal` + `gap-row` recipes — **no new CSS**) listing library journals by count with a
  Follow / ✓ Following action. Journal is the default kind via the registry order.

## Key technical detail

Follow-by-title stays stateless + reuses infra: the source resolves title→ISSN **per poll** (one extra Crossref
`/journals` call, on the opt-in Refresh), then the exact `filter=issn:` works path — so precision matches the old ISSN
source without the user needing the ISSN. The "Suggest" list and the typeahead share **one** local data source
(`papers.venue`); no per-keystroke egress. Egress happens only on Refresh (the feed's existing public-metadata
channel — never the Gemini gate).

## Gates

- **Security audit `2026-07-18_feed-journal-title-and-library-journals.md` — PASS** (new endpoint read-only/local/
  parameterized; title→ISSN reuses the audited Crossref host with a validated URL-encoded query param, no SSRF; no new
  dep/secret; no library-text egress).
- **Principles (#9):** the Suggest list is the user's own library aggregated (a count, not a verdict/opaque score);
  local. Aligned.
- **QA (#10):** `route_44_feed.md` extended (declares `/feed/library-journals`; asserts the local aggregation, the
  journal-title default, the Suggest modal); `build_surface_map.py check` → 247 API / 1139 FE, 0 uncovered.
- **Help:** the "Following sources (Feed)" section rewritten (Journal-by-title default + Suggest + typeahead;
  HELP-DOCS-SYNCED moved to inc 295).

## Manual verification script

App on :8888 (backend restarted). Discover → Search → **Feed**: the Follow **source type defaults to Journal**; type
a few letters → matching **library** journal titles predict; click **Suggest** → a modal lists your library's journals
by count → **Follow** one → it appears as a subscription chip and the modal shows ✓ Following. **Refresh** → recent
articles from that journal appear; **Save** a couple. No egress until Refresh. (A library with no journals shows the
modal's empty state.)

## Pytest

`tests/test_feed.py`: journal-title source (title→ISSN exact path + no-match container-title fallback + blank→empty);
`/feed/library-journals` (venues + counts, no-venue excluded, most-frequent first); registry-default order updated.
`tests/test_frontend_assembly.py` +1 (Suggest modal + typeahead + follow wiring). Full suite: **1254 passed, 1
skipped** (to confirm on the full run).
