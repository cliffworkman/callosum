# Increment 455 — Followed authors flow into the Feed (backlog #29)

## Implemented

Increment 454 gave followed authors a dedicated Discover → Followed Authors tab, an actionable "what am I
missing" list (works absent from the library, Add/Dismiss). This increment adds a second, complementary view:
a followed author's new publications now also flow into the existing literature **Feed** (Discover → Feed),
intermixed chronologically with bioRxiv/PubMed/journal items, visually distinguished by a small "Followed" badge.

`app/backend/discovery/followed_author_feed_source.py` (new) implements the existing `FeedSource` protocol,
wrapping the same already-audited `OpenAlexAuthorClient.fetch_author_works` the Followed-Authors tab itself uses.
It **deliberately does not dedupe against the library** — unlike the gap list, Feed's own long-established
convention (journal/bioRxiv/PubMed) is to store everything polled and compute `in_library` at read time, so a
followed author's already-owned paper still appears here (badged "✓ in library" instead of Save), never silently
hidden. Works with no DOI are skipped (no stable `dedup_key` to store).

`app/backend/discovery/feed.py`'s `build_default_feed_registry()` gained optional `engine`/`author_client`
parameters — only the real app-boot call site (`app.py`) passes them, so the new source is registered
conditionally, never by mutating an already-built or test-injected `FeedRegistry` after construction. The
`FeedSource` protocol gained an optional `user_addable` attribute (default `True`); `FollowedAuthorFeedSource`
sets it `False` so the frontend's generic "Add source" picker never offers it directly (a raw OpenAlex author id
is not something a user should type — the Followed-Authors tab's name/ORCID/direct-resolve flow stays the only
sanctioned way to follow an author), while an already-followed author's subscription **chip** still resolves its
friendly label correctly (the frontend filters only the picker's dropdown, not the full `source_meta` array the
chip lookup uses).

Follow/unfollow now keeps `followed_authors` and `feed_subscriptions` in sync, **in both directions**:
`followed_authors.py::follow_author` also calls `feed_repo.add_subscription(kind="followed_author", ...)`
(idempotent, safe on a re-follow); `followed_authors.py::unfollow_author` also removes the matching subscription;
and `feed.py::remove_subscription` (unfollowing via Feed's own chip) also removes the matching `followed_authors`
row, so "unfollow" means the same thing regardless of which UI surface the user clicked. A startup self-heal
(`followed_author_repo.backfill_feed_subscriptions`, called from `app.py`'s `lifespan()` next to the existing
`_upgrade_database_to_head` migration self-heal) back-fills a matching subscription for any author followed
before this increment shipped, since re-following just returns `already-following` and gives the user no organic
trigger to create one otherwise.

## Key technical detail

**Registration had to be conditional, not a post-hoc mutation, to avoid breaking existing tests.**
`tests/test_feed.py::test_default_feed_registry_registers_sources` asserts `build_default_feed_registry()`
(called bare) returns exactly the 4 pre-455 kinds, and `test_feed_endpoints` injects a custom `feed_registry` via
`create_app(..., feed_registry=...)` and asserts exact equality on `source_meta`. Registering the new source by
mutating `api.state.feed_registry` after construction (the first design considered) would have silently broken
both — a test-injected registry has no reason to expect an extra, unrequested source appended to it. The fix:
`build_default_feed_registry(*, engine=None, author_client=None)` only registers the new source when `engine is
not None`, and registration happens exactly once, at construction, never as a later mutation. This was caught by
a Plan-agent review pass before any code was written, not discovered by running the tests after the fact.

**A real ordering bug caught by live testing, not by the test suite.** `feed_repo.list_items` sorts
`posted_date DESC` (SQLite treats NULL as smallest, so a NULL always sorts *last*), and the first cut of
`FollowedAuthorFeedSource._to_entry` never set `posted_date` at all — every followed-author item would have
silently sunk to the very bottom of the feed, regardless of how recent it actually was, directly undermining the
whole point of "intermixed chronologically." The hermetic tests never caught this because they only assert
`fetch()`'s own output shape and dispatch, never the resulting *global* sort order across a large, realistic
feed. Caught only by refreshing against the real testing library (800+ real feed items) and noticing a followed
author's brand-new 2026 work wasn't visible anywhere near the top. Fixed by setting `posted_date=str(work.year)`
— OpenAlex's authored-works listing (`AuthorWork`) only exposes a coarse year, never a full date, so this is a
**known, accepted precision limit**, not a full fix: a bare "2026" sorts correctly *before* any 2025/2024 item
but *after* every dated "2026-MM-DD" item from another source, since a shorter string that's a prefix of a
longer one compares as "less than" it. Getting day-level precision would mean extending inc 454's own
`AuthorWork`/`OpenAlexAuthorClient` to fetch and carry a real publication date — a real scope expansion into
already-shipped, already-audited code, deliberately left as a documented follow-up rather than done here.
Regression test: `test_followed_author_source_items_sort_correctly_alongside_dated_sources`.

**The `user_addable` vs. `source_meta` tension.** The naive fix — excluding `followed_author` from `source_meta`
entirely — would have silently broken the existing subscription-chip label lookup
(`sourceMeta.find(m => m.kind === s.kind)` in `30e_feed.jsx`), making an already-followed author's chip fall back
to showing the raw string `"followed_author"` instead of "Followed author." The actual fix keeps `source_meta`
complete (additive `user_addable` key, nothing removed) and filters **only** the picker's own dropdown/datalist
client-side — the chip lookup stays against the full, unfiltered array.

## Housekeeping / gates

- **Security audit**: appended a dated addendum to `.claude/security-audits/2026-08-07_followed-authors.md` —
  PASS. No new external host (reuses the already-audited `OpenAlexAuthorClient`); the bidirectional sync is
  bounded (one extra idempotent write per direction, reusing the existing cascade paths); the startup backfill is
  bounded by however many authors the user actually follows.
- **QA routes**: extended `route_44_feed.md` and `route_87_followed_authors.md`'s narrative sections (no new
  `@router.` decorator or JSX interactive handler was added, so no new `qa-coverage` header entries are required
  by the hard gate — confirmed via `build_surface_map.py check`, not assumed).
- `.claude/docs/INCREMENT-BACKLOG.md`: no separate entry needed — this extends #29's already-closed inc-454 entry.
- `.claude/CLAUDE.md`: counter bumped to 455; the gap-finder/Feed narrative extended.

## Manual verification script

1. Start the app against a seeded DB with at least one real followed author (or follow one live). Open
   **Discover → Feed** — confirm a subscription chip tagged "Followed" appears, and that the generic "Add
   source" picker's dropdown does **not** offer "Followed author" as a selectable kind.
2. **Refresh** the Feed → confirm the followed author's works appear intermixed with other Feed items,
   chronologically ordered, each carrying the small indigo "Followed" badge next to its title.
3. Confirm a followed author's already-in-library work still appears (badged "✓ in library"), proving Feed does
   NOT dedupe against the library the way the Followed-Authors tab's own candidate list does.
4. Unfollow via **Feed's own chip** (×) → confirm the author also disappears from the **Followed Authors** tab.
   Re-follow, then unfollow via the **Followed Authors tab** instead → confirm the Feed chip also disappears.
5. Zero console errors throughout; zero requests to a `generativelanguage`/genai host.

## Verification

- `pytest tests/test_feed.py tests/test_followed_authors.py -q` → **32 passed** (11 new: conditional registry
  registration, `FollowedAuthorFeedSource.fetch()` mapping/no-DOI-skip/limit, dispatch via
  `refresh_subscriptions`, the reverse-Feed-unfollow sync, forward-sync-on-follow, idempotent re-follow, and the
  real-ASGI-lifespan backfill).
- `pytest tests/test_gapfinder.py tests/test_status.py -q` → **30 passed**, confirming no regression and no
  missed `JobStore` invariant (no new `JobStore` this increment — the new source runs inside Feed's existing
  `feed_jobs` refresh job).
- `python tools/check_line_budget.py`: clean (496 files, all under cap).
- `python tools/qa/build_surface_map.py check`: 382/382 API, 1625/1625 FE surfaces covered — unchanged from
  pre-455 (no new hard-gated surface).
- `ruff format` + `ruff check`: clean. `python tools/build_frontend.py` + `pytest tests/test_frontend_assembly.py -q`: clean, 64 passed.

## Rollback

Remove `app/backend/discovery/followed_author_feed_source.py`; revert `discovery/feed.py`'s `user_addable`
attribute, the `source_meta` key, and `build_default_feed_registry`'s new parameters (back to a bare factory);
revert the `app.py` call-site + lifespan backfill call; revert the sync calls in `followed_authors.py` and
`feed.py`; revert the `followed_author_repo.backfill_feed_subscriptions` addition; revert the `30e_feed.jsx`
picker-filter + badge and the one new CSS class. No schema/migration to revert — `feed_subscriptions.kind` is a
plain string column, and the new `feed_subscriptions` rows this feature creates are ordinary rows in an existing
table (deleting them via the app's own unfollow flow, or leaving them inert, is sufficient — no destructive
cleanup required).
