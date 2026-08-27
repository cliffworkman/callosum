<!-- qa-coverage
api: /feed, /feed/subscriptions, /feed/subscriptions/{sub_id}, /feed/refresh, /feed/refresh/{job_id}, /feed/items/{item_id}/state, /feed/mark-read, /feed/library-journals, /feed/suggest-authors, /discovery/relevance, /followed-authors, /followed-authors/{author_id}
fe: 30e_feed.jsx, 30g_feed_suggest.jsx
-->

# ROUTE 44 — Literature Feed (subscriptions + polling + read/starred + Suggest + Author follow)

**Tier:** 2 external (bioRxiv/OpenAlex metadata)
**Goal:** Exercise the Feed end to end — the **Discover → Feed** center sub-tab, now the sole home for
following sources (journals, bioRxiv/medRxiv categories, PubMed searches, and **authors** — the standalone
Followed Authors tab was consolidated in here 2026-08-27): follow a source (subscription), **Refresh** to poll
it, then triage the polled items (read / starred / save). **Pull-only, opt-in** — nothing auto-subscribes,
nothing pushes. Public-metadata polling (bioRxiv/OpenAlex) — **never** the Gemini gate. Save reuses
`/discovery/save` (metadata-only, **no PDF**). Backend = inc 187 (SP2a); the Feed tab UI (`30e_feed.jsx`) =
inc 188 (SP2b).

## UI flow

- The Discover workspace has a persistent **Feed** sub-tab before Search. It shows the followed-source chips
  (each with an unfollow ×, capped to one visible row with a **"…"** overflow button when they don't fit — see
  below), an add-a-source row (a **Journal / bioRxiv category / medRxiv category / PubMed search / Author**
  dropdown + a text box with a datalist + **Follow** / **Suggest** / **Refresh**), a merged **All / Unread (N) /
  Highlighted / Starred** filter, an **Auto-Refresh** checkbox, and **Mark All Read**.
- Each item row: an unread dot + serif title (read items dim), authors/posted-date/journal meta, a **★** star
  toggle, **Save** / **✓ in library**, and an **Abstract** toggle. Clicking a row marks it read.
- **Following an author is now a Feed-native action.** Selecting **Author** in the dropdown and typing either a
  plain name or an ORCID iD (bare `0000-0002-1825-0097` or a full `https://orcid.org/...` URL, auto-detected)
  and clicking **Follow** resolves it via `POST /followed-authors` (the same endpoint the old standalone tab
  used) — a no-match shows an inline error, never a crash. A followed author's chip appears in the same
  `feed-subs` row (tag "Author") exactly like any other source, and its items carry a small indigo **"Followed"**
  badge next to the title. Unfollowing via this chip's × removes both the `feed_subscriptions` row and the
  underlying `followed_authors` row (the two were always kept in sync; there is no second tab to sync with
  anymore).
- **Suggest is a 5-tab modal** (Journal / bioRxiv Categories / medRxiv Categories / PubMed Search / Author),
  always opening on the Journal tab. Journal is unchanged (library-frequency journals, click-to-follow).
  bioRxiv/medRxiv show every fixed category, matched ones first with the matching axis/tag named as the reason
  (a plain text match, never a hidden score). PubMed Search suggests from your Discover→Search history, your
  axes, and your tags (keywords + your own), each labeled by source. Author shows library-frequency authors
  (excluding you and anyone already followed) via `GET /feed/suggest-authors`. Every tab's Follow click follows
  immediately (no populate-then-click-Follow-again step).

## Environment

Clean seeded instance (`_TEMPLATE.md` → Environment). **Egress UNSET** (the library-text gate must never fire;
bioRxiv/OpenAlex metadata is fine). Register console/pageerror/request listeners before navigation.

**Seed note:** the real bioRxiv poll and author resolve/refresh hit the network. To exercise the flow
**offline + deterministically**, inject `app.state.feed_registry` with a fake `FeedSource` (mirror
`tests/test_feed.py`'s `_FakeSource`) and `app.state.openalex_author_client` with a fake exposing
`resolve_author(conn, *, orcid=None, name=None)` (mirror `tests/test_followed_authors.py`'s
`_FakeAuthorClient`).

**Use a free port** — stray uvicorns can serve a stale app (assert your own process + that `/feed` doesn't 404).

## Standing assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **Egress gate.** ANY request to a `generativelanguage`/Gemini/genai host is **Critical** (the Feed is public
  metadata only — bioRxiv/OpenAlex, never the library-text gate).
- **Pull-only, opt-in.** A source is followed only by an explicit `POST /feed/subscriptions` (or, for Author,
  `POST /followed-authors`); there is no auto-subscribe and no push. `POST /feed/refresh` is the only poll.
  `kind` must be a registered source kind (an unknown kind → **422**).
- **Re-poll is idempotent + non-destructive.** `upsert_items` is INSERT-OR-IGNORE on (subscription, dedup_key): a
  re-refresh adds no duplicates **and never resets read/starred state** (read state is the user's).
- **`in_library` is read-time truth.** `GET /feed` computes `in_library` per item against the live library (a saved
  item shows in-library without a re-poll) — like the Search tab.
- **A bad source never sinks the run.** `refresh_subscriptions` skips a source/subscription that raises.
- **Save = metadata-only, no PDF** (reuses `/discovery/save` — the OA-acquire lane is untouched).
- **Follow journals by TITLE; suggestions are the user's own library (inc 295).** `journal` (by title) is the default
  Follow kind. `GET /feed/library-journals` returns `[{journal, count}]` from `papers.venue` — **read-only, local,
  no egress** — a tally of the user's own library, ordered by count, **NOT** a quality ranking (signal-not-verdict).
- **The "Add source" picker's real kinds never include "Followed author" as a raw-id field.** `source_meta`'s
  `kind="followed_author"` stays `user_addable:false` server-side — the dropdown's **Author** option is a
  frontend-only pseudo-kind that always routes through the name/ORCID resolve endpoint, never lets a raw
  OpenAlex id be typed into `/feed/subscriptions`.
- **The followed-author source shows everything, never dedupes at write time (inc 455).** A followed author's
  Feed items are **not** filtered against the library — `in_library` is computed at read time exactly like every
  other Feed source, so an already-owned paper by a followed author still appears here (`✓ in library` instead
  of Save). (The old standalone tab's separate "what am I missing" gap list was retired 2026-08-27 — this
  stream is the sole remaining surface for a followed author's works.)
- **Axis-relevance is a hint, never a filter (reuses the Search-tab mechanism unchanged).** After the item list
  loads, a best-effort `POST /discovery/relevance` call may add a `likely: <axis> · match X.XX` badge to items
  whose best-matching axis clears its cutoff — the complete list is always shown, never reordered or hidden by
  this. An item with no badge is "no strong axis match," not "irrelevant" — never presented as a negative signal.
  A failed/slow relevance call must never block or break the item list itself. Any badge, sort order, or filter
  that reads as a composite "relevance score" (rather than one labeled axis + similarity) is **Critical**.
- **All/Unread/Highlighted/Starred is ONE exclusive toggle (2026-08-27 redesign).** A prior design had two
  independent filter groups (read-status + a separate Highlighted on/off, combinable); user feedback confirmed a
  single exclusive 4-way toggle instead — only one of the four is active at a time, in that fixed order.
  Selecting "Highlighted" is a pure client-side view filter over the already-loaded "all" item set (never a
  server re-poll); while relevance is still loading, its empty state must read "Checking axis matches…", never a
  bare "No items" that could be misread as "nothing relevant exists." A design that lets Highlighted combine
  with Unread/Starred again, or that persists as a silent default-on filter across a refresh, is a regression —
  **High**.
- **Followed-sources overflow.** The pill row is capped to one visible line; when pills don't fit, a real
  measured check (not a fixed guessed count) shows a **"…"** button opening a modal listing every followed
  source unconstrained, with the same × unfollow control. The row must never silently truncate pills without
  that "…" affordance appearing.
- **Title Case on control labels.** "Auto-Refresh" and "Mark All Read" (not "Auto-refresh on open" / "Mark all
  read") — a DESIGN.md rule now covers this app-wide for new/changed controls.

## Adversarial checklist

- Add a subscription with an unknown `kind` → 422; a duplicate (kind,value) is get-or-create (no second row)
- Refresh → items appear unread; refresh again → no new items, read state preserved
- Mark an item read → it drops from `?unread=true`; star it → it shows in `?starred=true`
- `mark-read` clears the unread count; deleting a subscription cascades (its items vanish)
- A subscription whose source raises → refresh still completes (new_items=0), no crash
- Follow an author by name, then by ORCID, then by a pasted `https://orcid.org/...` URL → all three resolve
  correctly; a name/ORCID matching nothing → an honest inline error, never a crash
- Follow an author already followed → `already-following`, no duplicate chip; unfollow via the chip's × →
  `GET /followed-authors` no longer lists them
- Suggest: follow from each of the 5 tabs in turn → each appears as a chip of the right kind; an
  already-followed item across any tab shows "✓ Following," not a duplicate-follow control
- Accumulate enough followed sources to overflow one row → the "…" button appears; open its modal, unfollow one
  from inside it → the chip disappears from both the modal and the header row

## Steps

1. (Offline, fake registry as above) `POST /feed/subscriptions {kind:"test_source", value:"x"}` → 200; an unknown
   kind → 422; `GET /feed/subscriptions` lists it + the registry `kinds`.
2. `POST /feed/refresh` → `{job_id}`; poll `GET /feed/refresh/{job_id}` → `done` with `result.new_items`.
3. `GET /feed` → the polled items (title/authors/year/journal/url + `is_read`/`is_starred`/`in_library`) +
   `unread_count`. An item whose DOI matches a seeded library paper is `in_library:true`.
4. `POST /feed/items/{id}/state {is_read:true}` → it leaves `?unread=true`; `{is_starred:true}` → it enters
   `?starred=true`. `POST /feed/mark-read` → unread_count 0.
5. `POST /feed/refresh` again → `new_items:0`, read state intact.
6. `DELETE /feed/subscriptions/{id}` → 204; `GET /feed` → no items (cascade). **0** genai-host requests throughout.
7. (inc 295) `GET /feed/library-journals` → `{journals:[{journal,count}]}` from the seeded library's venues,
   most-frequent first (a paper with no venue is excluded); **no external request**. (UI) The Follow kind defaults
   to **Journal**; typing predicts from those library journals.
8. **Author follow (2026-08-27).** In the UI, select **Author**, type a plain name → Follow → a chip tagged
   "Author" appears; select Author again, type an ORCID → Follow → resolves via the same endpoint. Confirm
   `POST /followed-authors` is called (not `POST /feed/subscriptions`) for both. `POST /feed/refresh` → the
   author's works appear in `GET /feed` intermixed with other items, each `subscription_id` matching the
   `followed_author` subscription (UI: the "Followed" badge). `DELETE /feed/subscriptions/{id}` for that
   subscription → `GET /followed-authors` no longer lists the author.
9. **Axis-relevance highlight.** With at least one axis whose description clearly overlaps one polled item's
   title/abstract and clearly does not overlap another's, refresh the Feed. Confirm the item list renders
   immediately; shortly after, the on-topic item gains a `likely: <axis> · match X.XX` badge next to its title
   (capture the `POST /discovery/relevance` request/response) while the off-topic item does not — and both
   remain visible in their original order (no filtering/reordering). Force the call to fail (e.g. block the
   route) and confirm the item list still renders normally with no badges and no console error.
10. **All/Unread/Highlighted/Starred (one exclusive toggle).** Click each in turn — confirm only one is ever
    active, the order is exactly All/Unread/Highlighted/Starred, and no two combine. On Highlighted, confirm only
    badged items remain visible and the underlying subscriptions/query are untouched (client-side only).
    Immediately after a refresh (before the relevance call resolves), switch to Highlighted and confirm "Checking
    axis matches…" appears rather than a bare empty state. Click back to "All" → every item reappears with no
    data loss (read/starred state intact). On a library with genuinely zero axis matches, confirm the copy
    explicitly says this isn't "nothing relevant," just nothing this local check flagged.
11. **Suggest modal.** Open Suggest → lands on **Journal** (unchanged list/behavior). Switch to **bioRxiv
    Categories**: with an axis or tag whose text plainly overlaps one fixed category name, confirm that category
    is listed first with the matching axis/tag named, and every other category still appears below. Switch to
    **PubMed Search**: confirm entries appear from a real prior Discover→Search query, an axis label, and a tag
    name, each labeled with its source; click one → it becomes a followed `pubmed_query`. Switch to **Author**:
    confirm the list is ranked by real library paper count, the seeded user's own name never appears, and an
    already-followed author never appears; click Follow on one → it flips to "✓ Following" without needing to
    reopen the modal.
12. **Overflow.** Follow enough distinct sources that the pill row would exceed one line at the current viewport
    width → confirm a "…" button appears (not silent clipping); open it → every followed source is listed,
    unconstrained; unfollow one from inside the modal → it's gone from both the modal and the header row.

## Pass criteria

- Subscriptions are explicit/opt-in (422 on unknown kind); refresh polls + stores; re-poll is idempotent + preserves
  read state; read/starred/mark-read/`in_library` all behave; delete cascades.
- Author follow/unfollow (name, ORCID, ORCID URL) works entirely from Feed; a followed author's items appear
  intermixed, badged, never pre-filtered against the library.
- Axis-relevance badges appear only as a non-filtering hint (never reordering/hiding items) and degrade silently
  on failure.
- All/Unread/Highlighted/Starred is one exclusive toggle, always recoverable via "All."
- Suggest's 5 tabs each surface real, inspectable suggestions (never a hidden score) and follow immediately on
  click; the pill-overflow "…" modal appears exactly when pills don't fit and supports unfollow.
- 0 console/page errors; **0 genai-host requests**.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_44_feed.md` + `screenshots/` (see `_TEMPLATE.md`).
