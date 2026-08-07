<!-- qa-coverage
api: /feed, /feed/subscriptions, /feed/subscriptions/{sub_id}, /feed/refresh, /feed/refresh/{job_id}, /feed/items/{item_id}/state, /feed/mark-read, /feed/library-journals
fe: 30e_feed.jsx
-->

# ROUTE 44 — Literature Feed (subscriptions + polling + read/starred)

**Tier:** 2 external (bioRxiv metadata)
**Goal:** Exercise the Feed end to end — the **Discover → Feed** center sub-tab: follow a bioRxiv category (subscription),
**Refresh** to poll it, then triage the polled items (read / starred / save). **Pull-only, opt-in** — nothing
auto-subscribes, nothing pushes; the user adds a source, then a refresh polls it. Public-metadata polling (bioRxiv
now) — **never** the Gemini gate. Save reuses `/discovery/save` (metadata-only, **no PDF**). Backend = inc 187 (SP2a);
the Feed tab UI (`30e_feed.jsx`) = inc 188 (SP2b).

## UI flow (the Feed tab, inc 188)

- The Discover workspace has a persistent **Feed** sub-tab before Search. It shows the followed-source chips (each with an
  unfollow ×), an add-a-category box (a datalist of common bioRxiv categories) + **Follow**, a **Refresh** button,
  an **All / Unread (N) / Starred** filter, and **Mark all read**.
- Each item row: an unread dot + serif title (read items dim), authors/posted-date/journal meta, a **★** star toggle,
  **Save** / **✓ in library**, and an **Abstract** toggle. Clicking a row marks it read.
- **inc 455 — followed authors flow into the Feed too.** Following an author (Discover → Followed Authors tab, or
  the My-Publications citing-authors quick-action) also creates a `kind="followed_author"` subscription here —
  its chip appears in the same `feed-subs` row (tag "Followed") but is **not selectable in the "Add source"
  picker** (`user_addable:false` — the picker only ever offers Journal/bioRxiv/medRxiv/PubMed). A followed
  author's items carry a small indigo **"Followed"** badge next to the title, distinguishing them from ordinary
  journal/bioRxiv/PubMed items in the same chronological list. Unfollowing **either** here (the chip's ×) **or**
  from the Followed Authors tab removes both the subscription and the `followed_authors` row — a bidirectional
  sync, not two independent lists.

## Environment

Clean seeded instance (`_TEMPLATE.md` → Environment). **Egress UNSET** (the library-text gate must never fire;
bioRxiv metadata is fine). Register console/pageerror/request listeners before navigation.

**Seed note:** the real bioRxiv poll hits the network (date-windowed pages). To exercise the flow **offline +
deterministically**, inject `app.state.feed_registry` with a `FeedRegistry` holding a fake `FeedSource` (mirror
`tests/test_feed.py`'s `_FakeSource` → `kind="test_source"`, `fetch` returns `FeedEntry` rows; add a subscription of
that kind). The refresh job runs `refresh_subscriptions` over the registry in a worker connection.

**Use a free port** — stray uvicorns can serve a stale app (assert your own process + that `/feed` doesn't 404).

## Standing assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **Egress gate.** ANY request to a `generativelanguage`/Gemini/genai host is **Critical** (the Feed is public
  metadata only — bioRxiv, never the library-text gate).
- **Pull-only, opt-in.** A source is followed only by an explicit `POST /feed/subscriptions`; there is no
  auto-subscribe and no push. `POST /feed/refresh` is the only poll. `kind` must be a registered source kind (an
  unknown kind → **422**).
- **Re-poll is idempotent + non-destructive.** `upsert_items` is INSERT-OR-IGNORE on (subscription, dedup_key): a
  re-refresh adds no duplicates **and never resets read/starred state** (read state is the user's).
- **`in_library` is read-time truth.** `GET /feed` computes `in_library` per item against the live library (a saved
  item shows in-library without a re-poll) — like the Search tab.
- **A bad source never sinks the run.** `refresh_subscriptions` skips a source/subscription that raises.
- **Save = metadata-only, no PDF** (reuses `/discovery/save` — the OA-acquire lane is untouched).
- **Follow journals by TITLE; suggestions are the user's own library (inc 295).** `journal` (by title) is the default
  Follow kind (ISSN dropped). `GET /feed/library-journals` returns `[{journal, count}]` from `papers.venue` —
  **read-only, local, no egress** — powering the **Suggest** modal + the follow typeahead. It is a **tally of the
  user's own library, ordered by count — NOT a quality ranking or recommendation** (signal-not-verdict). The
  journal-title poll resolves title→ISSN then works via the **already-audited Crossref host** (egress only on
  Refresh); a blank/oversized title fetches nothing.
- **The followed-author source shows everything, never dedupes at write time (inc 455).** Unlike the Followed
  Authors tab's own "what am I missing" candidate list, a followed author's Feed items are **not** filtered
  against the library — `in_library` is computed at read time exactly like every other Feed source, so an
  already-owned paper by a followed author still appears here (with `✓ in library` instead of Save). This is a
  deliberate difference in purpose (a full stream vs. a gap-triage list), not an inconsistency.
- **The "Add source" picker never offers "Followed author."** `source_meta` carries a `user_addable` flag;
  `kind="followed_author"` is `false` — following an author only happens through its own dedicated resolve flow
  (name/ORCID/direct), never a raw-author-id text field here.

## Adversarial checklist

- Add a subscription with an unknown `kind` → 422; a duplicate (kind,value) is get-or-create (no second row)
- Refresh → items appear unread; refresh again → no new items, read state preserved
- Mark an item read → it drops from `?unread=true`; star it → it shows in `?starred=true`
- `mark-read` clears the unread count; deleting a subscription cascades (its items vanish)
- A subscription whose source raises → refresh still completes (new_items=0), no crash
- Follow an author (elsewhere), confirm its chip appears here tagged "Followed" and is absent from the "Add
  source" picker's own dropdown; unfollow via THIS chip's × → confirm the author also disappears from the
  Followed Authors tab (the reverse sync)

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
   most-frequent first (a paper with no venue is excluded); **no external request**. (UI) The Follow kind defaults to
   **Journal**; typing predicts from those library journals; **Suggest** opens a modal listing them by count with a
   **Follow** (already-followed → ✓ Following) that `POST /feed/subscriptions {kind:"journal"}`.
8. (inc 455) Follow an author from the Followed Authors tab (or inject a `followed_author` subscription +
   a fake author-client the way `tests/test_feed.py`'s `_FakeAuthorClient` does). `GET /feed/subscriptions` →
   `source_meta` includes `{kind:"followed_author", user_addable:false}`; `POST /feed/refresh` → the author's
   works appear in `GET /feed` intermixed with other items, each with `subscription_id` matching the
   `followed_author` subscription (UI: the "Followed" badge). `DELETE /feed/subscriptions/{id}` for that
   subscription → `GET /followed-authors` no longer lists the author (reverse sync).

## Pass criteria

- Subscriptions are explicit/opt-in (422 on unknown kind); refresh polls + stores; re-poll is idempotent + preserves
  read state; read/starred/mark-read/`in_library` all behave; delete cascades.
- A followed author's items appear intermixed, badged, never pre-filtered against the library; the picker never
  offers "Followed author" directly; unfollowing from either surface (this tab's chip, or the Followed Authors
  tab) clears both records.
- 0 console/page errors; **0 genai-host requests**.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_44_feed.md` + `screenshots/` (see `_TEMPLATE.md`).
