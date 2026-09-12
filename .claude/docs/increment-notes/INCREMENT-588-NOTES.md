# Increment 588 — Wanted-list OA triage + sticky selection bar + human-readable OA-fetch failures, shipped in 0.5.11

Two threads from live 0.5.10 use, both shipping in 0.5.11: (1) turn the **Wanted modal** from a wall of cryptic
403s into an actionable OA-acquisition triage surface; (2) keep the library's **selection actions bar** visible
on scroll (freeze-pane). Plus a future-track GitHub issue for a browser-extension importer.

## The Wanted rework

### The missing-link bug (fix A)
`wanted_repo.list_wanted` selected the wanted row's *own* `doi` column, which is **NULL for every library-synced
paper** (`sync_from_library` inserts only `paper_id`) — so the inc-587 "Open article" link (keyed on `it.doi`)
never rendered for library papers. Fix: `list_wanted` now also selects `papers.c.doi.label("paper_doi")` (mirrors
`list_open`), and `routers/wanted.py::_to_response` coalesces `doi = own doi or paper_doi`. The link now renders
for every wanted paper with a resolvable DOI.

### Structured acquisition state — fix the lossy boundary, don't parse prose (fix B)
The real defect was architectural: `run_recheck` computed `AcquireOutcome.reason_code` (structured) but persisted
only `human_detail()` (prose like "…HTTP 403 from openalex"), so any triage had to reconstruct state by parsing
that string — making `human_detail` wording an accidental durable contract.

Now the structured state flows end-to-end: **`AcquireOutcome.reason_code → wanted_items.last_reason_code → API
acquisition_state → frontend`**.
- **Migration 0082** adds `wanted_items.last_reason_code` (additive, nullable).
- `wanted_repo.mark_checked`/`mark_fulfilled` take a `reason_code`; `run_recheck` persists it at every branch
  (`needs_id | no_candidate | candidates_exhausted | acquired | error`) straight from the outcome / control flow —
  no string inspection.
- `routers/wanted.py` derives `WantedItemResponse.acquisition_state` from `last_reason_code`
  (`candidates_exhausted→blocked`, `no_candidate→no_oa`, …). **Structured state wins whenever present.**
- `_legacy_state_from_last_result` is a **narrow, explicitly-named COMPATIBILITY** classifier used *only* for
  pre-inc-588 rows (`last_reason_code IS NULL`); a row gains a structured code the next time it is re-checked,
  after which the legacy parser is never consulted. Tested as compatibility, not as the canonical derivation.
- **Round-trip test**: `run_recheck` with a fake registry whose download raises `OaFetchError(403)` →
  `last_reason_code == "candidates_exhausted"` and the API `acquisition_state == "blocked"`; every branch covered;
  the legacy parser tested separately + that structured wins over prose.

### Humanize by default, keep provenance inspectable (fix C)
Plain-language default messages keyed off structured state, on **all three** OA-failure surfaces — the Wanted
modal, the Details "Acquire OA copy" row (`AcquireOaRow`), and the **Add-with-DOI modal** (`28e_add_doi.jsx`,
added at the maintainer's request so a DOI-add whose OA fetch fails says *why* in plain language too). The raw
technical string is **not deleted** — it stays reachable under a "Technical details" `<details>` disclosure
(Details / Add-DOI) or a row tooltip (Wanted). "No HTTP 403 anywhere" is deliberately **not** the invariant;
"understandable by default, provenance on demand" is. Language is precise: **"the automatic download was
blocked"**, never "the publisher blocked it" (the evidence doesn't name a blocker); the DOI link opens the
**article's page**, not necessarily the same OA copy that failed.

### Triage features — honest about what's actionable
Pure-frontend over the loaded items + `acquisition_state`: **sort** blocked-to-top (stable state-rank);
**filter** "Show only blocked open-access"; a **summary banner** with *honest* counts (openable = blocked **with a
DOI**, stated separately from the blocked total, never conflated); and a **bounded "Open all"** that opens only
openable items, ≈15 per click, behind a confirm, advancing a cursor with remaining-count feedback — never silently
opening ~100 tabs. Reuses `.axis-bulk-bar`'s accent-soft palette; `--flag` amber for the blocked row status.

## Sticky selection actions bar (freeze-pane)
The bulk `.axis-bulk-bar` was a sibling *after* the sticky `.pane-head`, so it scrolled out of view — selecting a
dozen papers for Critical Read meant scrolling back up. It now lives as the **last child inside `.pane-head`**, so
it's pinned under the search/filter bar whenever a selection exists and — because `position: sticky` *reserves*
space — pushes the cards down instead of covering them. Gated `!fulltextMode` (pane-head renders in both modes).
CSS scoped to `.pane-head .axis-bulk-bar` so other `.axis-bulk-bar` uses (axes, reference-integrity) are unchanged.

## Browser-extension importer (future-track issue)
Filed GitHub issue: a browser extension to one-click-import a paper the user **already opened in their own
browser** — framed strictly around capturing already-accessed material, never paywall circumvention or autonomous
fetching (APPROACH-AVOIDANCE veto).

## Gates
`tests/test_wanted.py` (18, incl. the structured round-trip + legacy-compat) + `test_acquisition*`/`test_job_store`/
`test_doi_add`/`test_frontend_assembly` green (161 in the affected run); ruff + line budget OK (condensed a schema
comment to stay under the 600 cap); QA surface map OK; drift gates declined at inc 588. No new endpoint/external
fetch (the DOI link is a browser navigation) → no new security-audit trigger.

**Live in-app verification (Playwright, seeded 20-paper scratch DB, worktree server):** migration 0082 applied on
startup (`0081 -> 0082`). Wanted triage confirmed end-to-end — banner "**6 … couldn't be downloaded automatically ·
5 can be opened directly**" (honest counts: one blocked paper had no DOI, so openable ≠ blocked), blocked rows
sorted to top, filter collapses to exactly the 6 blocked, messages plain-language ("automatic download was
blocked", never "publisher"), the raw "HTTP 403…" string preserved in the row tooltip, 16 Open-article links.
Sticky bar confirmed — `.axis-bulk-bar` is a direct child of the sticky `.pane-head`, stayed pinned (bar top
232px → 232px through a 500px scroll), opaque backgrounds (alpha 1) + header z-index 5 over card z-index auto (cards
scroll *behind* it, not through), wraps rather than overflowing. **Still verify in the packaged app:** the bounded
"Open all" `window.open` loop opens external browser tabs (single-link `window.open` is already confirmed working
packaged; degrade the batch if not).
