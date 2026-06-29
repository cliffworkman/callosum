# Increment 192 — Feed SP2c-3 (part 2): the auto-refresh cadence — **#28 complete**

Backlog #28 SP2c-3, the frontend half + the last open item on the discovery track. An **opt-in, staleness-gated
auto-refresh** when you open the Feed — pull-first, no background daemon. **This closes #28 entirely.**

## Implemented (frontend-only)

- **`app/frontend/js/30e_feed.jsx`** — `FeedPane` gains:
  - an `autoRefresh` toggle (`localStorage["callosum.feedAutoRefresh"]`, **default off**) + a "**Auto-refresh on
    open**" checkbox in the controls row;
  - an `active` prop (true when the Feed tab is the open tab) + an effect that, when **active && autoRefresh &&
    a source is stale**, fires `refresh()`. Stale = the newest `last_polled_at` across subscriptions is > **6h** ago,
    or never polled. **Throttled** to ≤1/min (`autoRanRef`); skipped while already refreshing. After a refresh the
    polls become fresh, so the effect self-quiesces (no loop). The naive-UTC `last_polled_at` is treated as UTC (append
    `Z`) so the staleness compare isn't skewed by the local timezone.
- **`app/frontend/js/30c_frame.jsx`** — passes `active={activeTab === "feed"}` to `FeedPane`.
- **`app/frontend/styles.css`** — `.feed-controls-right` + `.feed-autorefresh` (tokens only).

## Key technical detail

- **Pull-first, opt-in, no daemon** (the #28 values posture, all the way to the end): there is no server-side
  scheduler — the refresh fires only when *you* open the Feed, only if you opted in, only if the data is actually
  stale. Mirrors the watched-folders on-launch/focus rescan (inc 98/136). Default off → zero behavior change for
  anyone who doesn't want it.
- **No backend change:** the toggle drives the existing audited `/feed/refresh` on a staleness condition — no new
  endpoint/egress/migration; the inc-187 feed audit covers the refresh path.

## Manual verification script

Headed, no egress (`.local/visual/drive_inc192_autorefresh.py` — a fake source + a seeded **stale** subscription
[`last_polled_at` NULL]): open the Feed (toggle off → **0 items**, never polled) → tick **Auto-refresh on open** →
the stale subscription triggers a refresh with **no manual Refresh click** → the polled item appears; 0
console/page/genai. PASS (first run).

## Gates

- **pytest 654** unchanged (frontend-only; `test_frontend_assembly` 5/5 confirms `30e_feed.jsx` is in the build +
  `callosum-app.html` in sync). `ruff` clean (no Python change). Build green.
- **QA (rule #10):** the new checkbox is claimed by `route_44`'s `30e_feed.jsx` → surface **132/132 API + 657/657 FE,
  0 uncovered**.
- **Principles non-triggering** (a UI convenience over the audited refresh; pull-only/opt-in/default-off posture
  preserved — not a new claim/signal/egress). **No audit gate** (no new endpoint/external-fetch/migration).
- **help corpus:** the Feed section notes the auto-refresh toggle (`HELP-DOCS-SYNCED` → 192).

## #28 — DONE

The literature discovery track is complete:
- **Search:** Crossref + PubMed — deduped, in-library marked, axis-relevance highlighted.
- **Feed:** bioRxiv + medRxiv (by category) + PubMed (keyword) + journal (ISSN) — follow → poll (manual or
  opt-in auto-on-open) → triage (read/star/save), with PubMed/preprint abstracts.

No open #28 sub-tasks remain. (A future, separate idea if ever wanted: a true background polling daemon — deliberately
**not** built, to keep the pull-first/no-surprise-egress posture.)
