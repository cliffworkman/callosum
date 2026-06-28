# Increment 187 — Literature Feed SP2a: the engine + store + endpoints + the bioRxiv source

Backlog #28 SP2 (the design-led, migration-bearing one; user greenlit "pull-only, no auto-subscribe"). SP2a is the
**backend**: subscriptions + polling + a read/starred store + the flagship **bioRxiv-by-category** source. **The Feed
tab UI is SP2b (inc 188).** Design spec: `.claude/docs/specs/2026-06-28-discovery-search-design.md` (SP2 section).

## Implemented

- **`app/backend/persistence/schema_feed.py`** (NEW) + **migration 0021** — `feed_subscriptions` (kind+value+label,
  UNIQUE(kind,value), `last_polled_at`) + `feed_items` (subscription FK CASCADE, dedup_key, the bibliographic fields,
  `is_read`/`is_starred` 0/1, UNIQUE(subscription_id, dedup_key)). Split out of `schema.py` (rule #1), re-exported from
  it (mirrors `schema_findings.py`). Additive + guarded migration (like 0002–0020).
- **`app/backend/persistence/feed_repo.py`** (NEW) — bound-param subscription CRUD (get-or-create) + `upsert_items`
  (INSERT-OR-IGNORE → re-poll never duplicates or resets read state) + `list_items` (unread/starred/subscription
  filters, newest-posted first) + `set_item_state` + `mark_all_read` + `unread_count`.
- **`app/backend/discovery/feed.py`** (NEW) — `FeedEntry` (the stored subset) + a `FeedSource` Protocol + `FeedRegistry`
  (`register`/`get`/`kinds`) + `build_default_feed_registry()` (registers bioRxiv) + the service: `refresh_subscriptions`
  (poll each subscription via its source → upsert; **a source that raises is skipped**, never aborts) + `feed_view`
  (list + compute `in_library` at read time, like Search).
- **`app/backend/discovery/biorxiv_source.py`** (NEW) — `BioRxivFeedSource` (`kind="biorxiv_category"`): `_biorxiv_fetch`
  pulls recent detail pages over a server-derived date window from the **constant** `https://api.biorxiv.org` host
  (cursor pagination, fail-closed); `record_to_entry` maps a collection record → `FeedEntry` (DOI, `authors` split on
  `;`, year, the biorxiv content URL, abstract); `fetch(category, limit)` **filters by category client-side** + dedups.
  Injectable `fetcher` for hermetic tests.
- **`app/backend/api/routers/feed.py`** (NEW) — `GET/POST/DELETE /feed/subscriptions`, async `POST /feed/refresh` +
  `GET /feed/refresh/{job_id}` (JobStore + a worker connection, mirrors the gap-finder), `GET /feed` (items +
  `unread_count`; computes `in_library`), `POST /feed/items/{id}/state`, `POST /feed/mark-read`. `add` validates `kind`
  against the registry (422 unknown).
- **`app/backend/api/app.py`** — wired: `feed` router; `create_app(feed_registry=None)` param;
  `api.state.feed_registry = feed_registry or build_default_feed_registry()`; `api.state.feed_jobs = JobStore()`.

## Key technical detail

- **Pull-only, opt-in, no push** (the user's chosen posture): a source is followed only by an explicit
  `POST /feed/subscriptions`; `POST /feed/refresh` is the only poll; nothing auto-subscribes. INSERT-OR-IGNORE makes a
  re-poll idempotent **and** non-destructive (the user's read/starred state survives).
- **No SSRF:** the bioRxiv URL is a constant host + server-derived date path; the subscribed category is filtered
  client-side (never in the URL).
- **Registry promise again:** adding the next Feed source (journal-by-ISSN, PubMed-keyword) is one `register()` — no
  endpoint/UI/store change (the `FeedRegistry` mirrors the Search `SourceRegistry`).

## Manual verification script

Hermetic (injected fake source + injected bioRxiv collection fetcher): `pytest tests/test_feed.py`. **Live spot-check**
(public metadata): `BioRxivFeedSource(window_days=10, max_pages=3).fetch("neuroscience", limit=5)` → 5 real preprints
mapped (title / DOI / year / posted date) end-to-end, confirming the live schema the hermetic tests assume.

## Gates

- **pytest 650** (+7 `tests/test_feed.py`: repo subscriptions/items/state + cascade, bioRxiv record mapping + category
  filter + dedup, default registry, refresh upsert + `in_library` view + re-poll-idempotent, refresh-skips-a-failing-
  source, the 8 endpoints incl. async refresh + 422-unknown-kind + mark-read + delete-cascade). `ruff` check +
  `format --check` clean. Migration head via `alembic_head()` (no hardcoded revision).
- **Audit:** `.claude/security-audits/2026-06-28_feed.md` **PASS** (constant host + server-derived path +
  client-side category filter → no SSRF; bound-param + non-destructive re-poll; public-metadata egress, not the Gemini
  gate; additive guarded migration; no new dependency). Values: pull-only/opt-in/no-auto-subscribe/augment-never-filter.
- **QA (rule #10):** new `route_44_feed.md` declares the 8 `/feed/*` endpoints → surface **132/132 API + 631/631 FE,
  0 uncovered**.
- **help corpus deferred to SP2b** (no usable UI yet — honest; the `HELP-DOCS-SYNCED` marker stays at 186).
- **No new dependency** (httpx); migration 0021 (the discovery track's first).

## NEXT — SP2b (inc 188): the Feed tab UI

A **Feed** center tab in `30c_frame.jsx`: a subscription manager (add bioRxiv category / remove) + the item list
(unread/starred filters, mark-read, star, save-to-library via `/discovery/save`, refresh) + an unread badge; headed
verify; help-corpus "Following sources (Feed)" + a `fe:` claim on `route_44`. (Later SP2c: journal-by-ISSN +
PubMed-keyword sources — each a `register()` + its own audit; an optional auto-refresh cadence.)
