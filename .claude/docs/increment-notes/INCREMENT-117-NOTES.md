# Increment 117 — My Publications overhaul, SP1: dashboard restructure & publication cards

The first sub-project of the My Publications overhaul (TDL line 1 + items #3–18, decomposed into SP1/SP2/SP3).
SP1 rebuilds the dashboard tab into author-priority order and makes the user's own corpus a first-class,
browsable **publications library**. Spec + plan: `.claude/docs/specs/2026-06-24-mypubs-sp1-{restructure-design,plan}.md`.

Covers TDL **#1, #3, #4, #5, #6, #7, #8, #10, #11, #12, #13**. Deferred: SP2 (domain organization — #9/#15/#16/#17/#18),
SP3 (citing articles + citation counts — #14).

## Implemented

- **Backend (additive; no new endpoint, no migration, no new egress) — `openalex_extra` + `starred_count`:**
  - `integrations/openalex/author.py`: `ResolvedAuthor` gains `two_year_mean_citedness: float` + `affiliation: str | None`,
    parsed in `_author_from_obj` from the **already-cached** OpenAlex author object
    (`summary_stats["2yr_mean_citedness"]`, `last_known_institutions[0].display_name`). No new network call.
  - `clustering/my_publications.py::build_dashboard` returns a new `openalex_extra`
    (`{two_year_mean_citedness, affiliation, openalex_author_id}`) + `starred_count` (`len(starred_paper_ids)`).
  - `routers/my_publications.py`: `OpenAlexExtra` model + `DashboardResponse.openalex_extra` / `.starred_count`.

- **Frontend — shared `PaperCard` (`10_pdf_layer.jsx`):** extracted the per-paper library card from the 40-prop
  `PaperList` monolith into `PaperCard({paper, selecting, isSelected, onSelect, onOpen, checked, onToggleCheck, footExtra})`.
  `PaperList` now renders `<PaperCard>` (its focus/trash buttons go through `footExtra`) — behavior-preserving for the library.

- **Frontend — dashboard restructure (`31_mypubs_dashboard.jsx`):** new section order
  **head → Overview → Research summary → Publications → Research domains → OpenAlex card**.
  - **Overview** (`#3/#4/#5`): collapsible (`localStorage["callosum.mypubsOverviewCollapsed"]`), a 2-column grid —
    2×2 metric tiles (left) + **one** chart (right) with a **Publications ⇄ Citations** flip toggle, replacing the
    old two side-by-side charts. Charts show the **last 10 data-years** with **`'NN`** apostrophe labels.
  - **Research summary** moved to r2; the **"⭐ only"** toggle is hidden when `starred_count === 0` (`#8`).
  - Old top "source: OpenAlex · refresh in Settings" attribution line removed (relocated into the OpenAlex card, `#6`).

- **Frontend — publications list (`33_mypubs_pubs.jsx`, new) — `#7/#10/#13` + full parity:** `MyPubsPublications`
  fetches `GET /papers?axis_id=<my-pubs axis>` (`limit=200`, the endpoint cap) and renders `PaperCard`s with
  search + sort, checkbox multi-select + a bulk bar (**summarize / export / bibliography / delete**), copy-BibTeX,
  open-on-double-click. The **Decompose** button is relocated here (passed in as `decomposeSlot`, `#10`). Summarize
  drives the right-pane synthesis via a threaded `onSummarize(ids)` (`summarizePaperIds` in `40_app.jsx` →
  `LibraryFrame` → `MyPubsDashboard`); single-click sets the Detail pane via threaded `onSelectPaper`.

- **Frontend — OpenAlex footer card + missing-works modal (`32_mypubs_missing.jsx`, new) — `#1/#6/#11/#12`:**
  the OpenAlex card (bottom) shows `as of <date>`, the indexed/library/not-imported gap, the `openalex_extra` stats
  (2-yr mean citedness · affiliation · OpenAlex profile link), and a **Refresh from OpenAlex** button (`#11`, reuses
  `POST /my-publications/refresh`). The missing-works import/reject queue + the dismissed-works list moved into a
  **modal** (`MissingWorksModal`, `#12`) opened by the card's **"Review N →"** button; same endpoints, `onChanged`
  refetches the (cache-only) dashboard.

## Key technical details / non-obvious bits

- **The publications list reuses the library's axis-filter machinery for free.** The My Publications axis is a real
  axis (`kind="my_publications"`, id 7 in the dev DB), so `GET /papers?axis_id=N` already returns exactly its members
  with `q`/`search_field`/`sort` composing — no new endpoint. `PaperList` itself is too coupled (40 props, AddMenu/
  Trash/Wanted/focus banners) to embed, so only the **card** was extracted; `MyPubsPublications` is a focused wrapper.
- **`limit` cap bug:** `/papers` enforces `limit ≤ 200` (`Query(le=200)`) — an initial `limit=500` returned **422**
  (silent empty list). Fixed to 200 (covers 71); an honest "Showing the first 200 — narrow with search" note shows
  if the count ever hits the cap (no silent truncation).
- **Missing-works reachability bug:** the "Review N →" button was gated on `missing_works.length > 0`, but when all
  missing works are dismissed (here: 0 missing / 4 dismissed) the dismissed list became unreachable. The gate is now
  `missing OR dismissed` and the label flips to "Dismissed (N) →" so dismissals stay restorable.
- **OpenAlex stats are pre-cached facts shown verbatim + attributed** (the inc-81 posture) — no new egress, no
  callosum-computed composite. SP1 added no claim/signal/judgment and no external fetch → **no audit/Principles gate**.
- Cross-chunk references work because the concatenated chunks compile to one esbuild IIFE (function declarations hoist):
  `31` renders `MyPubsPublications`/`MissingWorksModal` defined in later chunks `33`/`32`.

## Manual verification script

1. `CALLOSUM_DB_URL=<…/validation-summarize/validation.sqlite> uvicorn app.backend.api.app:app --port 8099 --reload`
   (the DB with a resolved My Publications profile), open `http://127.0.0.1:8099/`.
2. Click **📊** on the My Publications sidebar card → the dashboard tab.
3. **Overview:** confirm 2×2 metrics + one chart; click **Citations**/**Publications** to flip; confirm `'15…'25`
   labels; click **▾ Overview** to collapse/expand (persists across reload).
4. **Summary** sits below Overview; the **⭐ only** toggle shows only if you have starred pubs.
5. **Publications (N):** cards render (library aesthetic); type in search → list narrows; change Sort → reorders;
   tick two checkboxes → the bulk bar appears (summarize/export/bibliography/delete); the **Decompose** button is in
   the controls row.
6. **OpenAlex card** (bottom): as-of, gap, 2-yr mean citedness + affiliation + profile link, **Refresh**, and a
   **Review/Dismissed →** button → opens the modal; Import/Dismiss/Restore work and the lists update.

Verified headed via Playwright against the live `:8099` data (`.local/visual/drive_mypubs.py`, `drive_t5.py`,
`drive_t5b.py`); screenshots in `.local/visual/shots/30-38`. The missing-works modal round-trip (restore→re-dismiss)
confirmed the `onChanged` refetch and left state clean (4 dismissed).

## Pytest

**428 passed, 1 skipped** (+1 new assertion set in `test_my_publications.py` for `openalex_extra` parsing + the
dashboard `openalex_extra`/`starred_count` shape). `ruff format --check` + `ruff check` clean.

## Commits (on main)

`870a96b` (T1 backend) · `0fcd198` (T2 PaperCard) · `abea7a1` (T3 Overview) · `df3c10d` (T4 publications) ·
`c189f83` (T5 OpenAlex card + modal) · this notes/docs commit.

## Next

**SP2 — domain organization** (#9 group-by-domain toggle, #15 rename domains vs axes, #16 domains → AXES-card
subheadings, #17 starred-first sorting, #18 chart-filter-on-domain-select), then **SP3 — citing articles &
citation counts** (#14, a new OpenAlex "cited-by" fetch → audit + Principles gate). The domains section currently
sits below the publications list as a transitional placement; SP2 reworks it.
