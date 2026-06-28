# Increment 188 — Literature Feed SP2b: the Feed tab UI

The frontend half of #28 SP2 (the backend — subscriptions + polling + the bioRxiv source + 8 endpoints — was SP2a,
inc 187). Makes the Feed usable end-to-end: follow a bioRxiv category, refresh, triage. **This completes #28** (Search
+ Feed). Frontend-only — reuses the inc-187 `/feed/*` endpoints (already audited).

## Implemented

- **`app/frontend/js/30e_feed.jsx`** (NEW) — `FeedPane({ onSaved })`:
  - **Subscription manager:** followed-source chips (`.feed-sub`, each with an unfollow ×) + an add box (a `<datalist>`
    of common bioRxiv categories) → **Follow** → `POST /feed/subscriptions {kind:"biorxiv_category", value, label}`.
  - **Refresh:** `POST /feed/refresh` → polls `GET /feed/refresh/{job_id}` to done → reloads items.
  - **Filter** (All / Unread (N) / Starred — the `.tags-srcfilter` segmented recipe) + **Mark all read**.
  - **Item rows** (reuse the `.discover-item` recipe + `.feed-*`): an unread dot + serif title (read rows dim), authors
    /posted-date/journal meta, a **★** star toggle, **Save** / **✓ in library**, an **Abstract** toggle. Clicking a row
    marks it read (optimistic + `POST /feed/items/{id}/state`); star + save are optimistic too. Save reuses
    `/discovery/save` (metadata-only, no PDF) + bumps the Library refresh.
  - **The complete polled list is shown** — read/starred are the user's state, never an AI filter.
- **`app/frontend/js/30c_frame.jsx`** — a persistent **Feed** tab + a `frame-pane` rendering `<FeedPane onSaved={onDiscoverSaved}/>`.
- **`app/frontend/styles.css`** — `.feed-*` recipe (subscription chips = accent chips; unread dot; read-dim; star;
  controls row) — tokens only (DESIGN rule #8).

## Key technical detail

- **Distinct root class:** FeedPane's root is `className="discover feed"` — it reuses the `.discover` flex-column layout
  but the `.feed` class disambiguates it from the (also-mounted) Discover pane.
- **Reuses the Discover save path** (`/discovery/save`) — one metadata-only, deduped save flow for both discovery
  surfaces.

## Manual verification script

Headed, no egress (a fake FeedSource + a seeded library paper):

```
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python .local/visual/drive_inc188_feed.py
```

→ open the Feed tab (empty state) → Follow `neuroscience` → a chip → Refresh → **3 items** (1 ✓ in library + 2 Save,
unread 3) → click a row marks it read (dims) → ★ stars → **Save** flips a row to ✓ in library + the paper appears in
the Library tab. **0 console/page/genai. PASS.** (Harness note: kill stray `uvicorn`/`inc18*` python between rapid
re-runs — a lingering server holds the throwaway DB/port and makes the cross-check flaky; the clean run is green.)

## Gates

- **pytest 650** unchanged (frontend-only; `test_frontend_assembly` 5/5 confirms `30e_feed.jsx` is in the build +
  `callosum-app.html` in sync). `ruff` n/a (no Python). Build green.
- **QA (rule #10):** `route_44_feed.md` gained `fe: 30e_feed.jsx` + the UI flow → surface **132/132 API + 653/653 FE,
  0 uncovered**.
- **Principles:** non-triggering (a UI over the audited SP2a endpoints; pull-only/opt-in/augment-never-filter posture
  unchanged; no new claim/signal). No new endpoint/migration/egress/dependency.
- **help corpus:** new "Following sources (Feed)" section (`HELP-DOCS-SYNCED` → 188; also covers the inc-186 PubMed
  source line in Discover, already added).

## NEXT (#28 remaining is optional / later)

- **SP2c:** more Feed sources — journal-by-ISSN (Crossref) + PubMed-keyword (esearch by date) — each a `register()` +
  its own audit if a new host; an optional auto-refresh cadence; PubMed abstracts via efetch. **#28's core (Search +
  Feed) is complete.**
