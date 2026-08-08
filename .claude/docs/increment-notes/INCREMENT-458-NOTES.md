# Increment 458 — Day-level publication dates for followed-author Feed items (backlog #28)

## Implemented

Inc 455 wired a followed author's works into the literature Feed, but `posted_date` fell back to a bare "YYYY"
(OpenAlex's authored-works listing was only ever asked for `publication_year`) — a known, documented limitation:
a bare-year item sorts correctly relative to other years but lands at the *end* of its own year among same-year
dated items from other Feed sources (bioRxiv/PubMed/journals all carry a real `YYYY-MM-DD`).

OpenAlex's Work object already carries a real `publication_date` — it just wasn't being requested. This
increment closes the gap:

- **`AuthorWork` gains a `publication_date: str | None = None` field** (`integrations/openalex/author.py`) —
  additive, so every existing construction site (tests, cached-work reconstruction) keeps working unchanged.
- **`_fetch_all_works`'s `select=` param** now asks for `publication_date` alongside the existing
  `id,doi,title,publication_year,cited_by_count`.
- **`_work_from_obj`** extracts it through a new `_normalize_publication_date` validator — OpenAlex responses are
  untrusted input (rule #4), so a malformed value (anything not `\d{4}-\d{2}-\d{2}`) is dropped rather than
  trusted verbatim into Feed's sort-order field.
- **`fetch_author_works`'s cache-read branch** reconstructs `publication_date` from the cached dict too, not just
  `doi`/`title`/`year`/`cited_by_count`/`openalex_work_id` — otherwise a cache hit would silently lose the new
  field even after a live fetch had populated it.
- **`followed_author_feed_source.py`'s `_to_entry`** now sets `posted_date=work.publication_date or (str(work.year)
  if work.year else None)` — the real date when OpenAlex supplies one, the old bare-year fallback otherwise (a
  pre-458 cached work, or a work OpenAlex itself never dated precisely).

## Key technical detail

**Backward compatibility is structural, not incidental.** A pre-458 cached `works` blob (from `fetch_author_works`
before this increment) has no `publication_date` key; `.get("publication_date")` on that dict returns `None`,
`AuthorWork.publication_date` defaults to `None`, and `_to_entry` falls through to the exact same bare-year logic
that shipped in inc 455. No cache invalidation, no migration, no behavior change for data fetched before this
increment — the day-level precision only appears once a `refresh=True` re-fetch (or a fresh author) pulls the new
field from OpenAlex.

The validator (`_normalize_publication_date`) is deliberately strict (`\d{4}-\d{2}-\d{2}` only) rather than
permissive — this value flows directly into `feed_repo.list_items`'s `ORDER BY posted_date DESC`, so an
unvalidated string from an external API is exactly the kind of untrusted input rule #4 exists for, even though
the practical risk here is low (OpenAlex's `publication_date` is reliably well-formed in practice).

## Housekeeping / gates

- **No new end-user surface** (no new endpoint, request/response contract, control, or async job) — QA-POLICY's
  rule #10 gate doesn't trigger; `build_surface_map.py check` confirmed unchanged (382/382 API, 1625/1625 FE).
- **No Principles-gate trigger** — this is a precision fix to an already-shipped signal's internal sort field,
  not a new claim/signal/judgment, and the egress posture is identical (same OpenAlex host, same existing
  `/works` call, one more field in an already-present `select=` param).
- `.claude/docs/INCREMENT-BACKLOG.md`: #28 remaining slice marked **✅ CLOSED inc 458**.
- `.claude/CLAUDE.md`: counter bumped to 458; the Literature gap-finder paragraph gained a closing sentence.

## Manual verification script

Not practically observable in the UI within a single session (OpenAlex's day-level precision only becomes
visible when two followed-author works share the same year but different months, which depends on real author
data) — verified instead by the two new tests below, which directly exercise the parse/validate/cache/fallback
contract against both a fake fetcher and a fake author client.

## Verification

- `pytest tests/test_feed.py tests/test_my_publications.py tests/test_followed_authors.py -q` → **79 passed** (2
  new: `test_followed_author_source_prefers_real_publication_date_over_bare_year`,
  `test_author_client_works_publication_date_parsed_validated_and_cached`).
- `python tools/check_line_budget.py`: clean.
- `ruff format` + `ruff check`: clean.
- `python tools/qa/build_surface_map.py check`: unchanged (382/382 API, 1625/1625 FE).

## Rollback

Revert `integrations/openalex/author.py` and `app/backend/discovery/followed_author_feed_source.py` to their
pre-458 state (the field addition is purely additive, so a partial revert of just the feed-source change is also
safe). Revert the 2 new tests. No schema/migration.
