# Design spec — My Publications overhaul, SP1: dashboard restructure & publication cards

**Date:** 2026-06-24
**Status:** approved design → spec under review
**Scope:** SP1 of a 3-sub-project overhaul. Covers TDL items **#1, #3, #4, #5, #6, #7, #8, #10, #11, #12, #13**.
**Deferred to later sub-projects:** SP2 — domain organization (#9, #15, #16, #17, #18); SP3 — citing articles & citation counts (#14).

---

## 1. Problem & goal

The current My Publications dashboard (`31_mypubs_dashboard.jsx`, 281 lines) is a single scrolling tab that reads as an *analytics report*: header attribution line → 4 metric tiles → gap line → **two** side-by-side year charts → research-domains list → AI summary editor. It surfaces the user's own corpus only as aggregate stats and rough domain bars — there is no way to **browse the actual publications** as papers.

**Goal (SP1):** restructure the tab so an author sees, in priority order, **their metrics, their summary, then their publications as first-class library-style cards**, with OpenAlex provenance/sync demoted to a footer card. Reuse existing components and data wherever possible; add no new network calls and no new endpoints.

Author-priority ordering (user decision): metrics & pubs lead; OpenAlex provenance comes last.

---

## 2. Target layout

Top-to-bottom render order in the dashboard tab:

```
1. Overview          (collapsible)   metrics 2×2  |  one flip-chart (Publications ⇄ Citations)
2. Research summary                  existing editor (+ #8 star-filter fix)
3. Publications                      controls row (search/filter/sort + Decompose) + library-style cards
4. OpenAlex card     (footer)        as-of date · gap · richer stats · Review-missing · Refresh
```

ASCII reference:

```
Clifford I. Workman

▾ Overview                                              [collapse]
┌ metrics (2×2) ───────┐  ┌ chart ─────────────────────────────┐
│ 1,605 Cites  23 h    │  │ Publications ⇄ Citations   [flip]   │
│ 32 i10  79 Works     │  │  ▁▂▃▅▇▆▅▃   ('17 … '26, 10 yrs)     │
└──────────────────────┘  └────────────────────────────────────┘

┌ Research summary ───────────────────── AI draft · [Gen][Save] ┐
│ This researcher investigates…                                 │
└───────────────────────────────────────────────────────────────┘

Publications (71)   [search…] [type ▾] [sort ▾]      [Break down ▾]
┌───────────────────────────────────────────────────────────────┐
│ Workman et al. — 2021 — Soc Psychol Pers Sci         📋   ☐    │
│ Beck, Workman, & Christensen — 2022 — Pers Sci       📋   ☐    │
│ …library-style cards, scoped to the My-Publications axis…      │
└───────────────────────────────────────────────────────────────┘

┌ OpenAlex ───────────────────────────────── as of 2026-06-21 ──┐
│ 79 indexed · 71 in library · 8 not imported      [Review 8 →]  │
│ 2-yr mean citedness 4.1 · <affiliation> · [OpenAlex profile ↗] │
│                                          [↻ Refresh from OpenAlex]│
└───────────────────────────────────────────────────────────────┘
```

---

## 3. Section designs

### 3.1 Overview — collapsible metrics + flip-chart (#3, #4, #5)
- **One row, two columns.** Left: the existing four metric tiles in a **2×2** grid (Citations, h-index, i10-index, Indexed works). Right: a **single** year chart.
- **Flip toggle (#4/#5):** replaces today's two side-by-side charts with one chart and a **Publications ⇄ Citations** toggle. Default = **Publications**.
- **10-year window (#4):** charts render the **last 10 years** (was ~14), with **apostrophe year labels** (`'17 … '26`).
- **Collapsible (#3):** the whole Overview block collapses/expands (chevron). **Expanded by default**; collapsing lets the user focus on the publications list. Collapse state persisted to `localStorage` (mirrors existing UI-pref pattern, e.g. `callosum.mypubsOverviewCollapsed`).
- Metrics remain **OpenAlex's verbatim figures, attributed** (no callosum-computed composite) — unchanged from inc 81.

### 3.2 Research summary (#8)
- The existing editor is unchanged **except**: the **"⭐ only"** toggle is **hidden when the user has no starred publications** (`starred_paper_ids` empty). Today it always renders; SP1 conditionally renders it.

### 3.3 Publications list (#7, #10, #13, + full library-card parity)
- The list is the **existing library card rendering driven by `GET /papers?axis_id=<my-publications axis id>`** — the dashboard tab already receives the My-Publications `axisId`.
- Reusing this gives, for free: the **library-card aesthetic (#13)**, **checkbox multi-select + bulk bar** (summarize / export / delete), **copy-BibTeX**, **open-on-double-click**, and **search / type-filter / sort (#10)** (the `/papers` endpoint already composes `q`/`search_field`/`item_type`/`sort` with `axis_id`).
- **Controls row (#10):** a search box + type filter + sort dropdown, **plus the relocated "Break down ▾" Decompose button** (moved out of the old domains section to "hang with search/filter & sort"). The Decompose button's *grouped output* is SP2; SP1 only relocates the trigger (it runs the existing decompose job).
- Scope: the ~71 own-papers that are **in the library** (axis members). The 8 indexed-but-missing works are **not** cards here — they live in the missing-works modal (§3.5).

### 3.4 OpenAlex card — footer (#1, #6, #11)
Consolidates today's scattered top-attribution + gap + refresh into one footer card:
- **`as of <date>`** moved here from the top header; **drop "· refresh in ⚙ Settings"** (#6).
- **Gap line:** `79 indexed · 71 in library · 8 not imported` with a **"Review 8 →"** button opening the missing-works modal (§3.5).
- **Richer OpenAlex stats:** 2-year mean citedness + affiliation (last-known institution) + a link to the OpenAlex author profile. These are **OpenAlex facts shown verbatim + attributed**, parsed from the already-cached author object (no new egress).
- **Refresh from OpenAlex (#11):** the second on-tab instance of the Settings "Refresh my papers" action (reuses `POST /my-publications/refresh`).

### 3.5 Missing-works modal (#12)
- The current inline **missing-works queue** (Import / Dismiss) and **dismissed-works** (Restore) sections move **verbatim into a modal**, opened by the OpenAlex card's "Review N →" button. Same endpoints (`/my-publications/works/{import,dismiss,undismiss}`), no behavior change — purely a clutter-reduction relocation.

---

## 4. Backend changes (additive; **no new endpoints → no audit gate**)
- **`integrations/openalex/author.py`:** add `two_year_mean_citedness: float` and `affiliation: str | None` (last-known institution) to `ResolvedAuthor`, parsed from the **already-cached** OpenAlex author object (`summary_stats["2yr_mean_citedness"]`, `last_known_institutions`). No new network call.
- **`clustering/my_publications.py` / `routers/my_publications.py`:** surface those two fields in the dashboard response as a new optional **`openalex_extra`** block (`{two_year_mean_citedness, affiliation, openalex_author_id}`), kept separate from `DashboardMetrics` (which stays the four headline figures). `openalex_author_id` lets the card link to the OpenAlex profile (`https://openalex.org/<id>`).
- Everything else reuses existing endpoints: `GET /papers?axis_id=…`, `GET /my-publications/dashboard`, the missing-works routes, `POST /my-publications/refresh`, `POST /my-publications/domains`.

No migration. No new egress. No change to the egress/verification posture.

---

## 5. Frontend file plan (600-line cap)
`31_mypubs_dashboard.jsx` is 281 lines and SP1 adds substantial UI. Plan:
- Keep **`31_mypubs_dashboard.jsx`** as the orchestrator: Overview (r1) + Research summary (r2) + OpenAlex card (r4) + layout.
- Extract the **missing-works modal** into a **new chunk** (e.g. `32_mypubs_missing.jsx`).
- **Reuse the library `PaperList`** for the publications list (r3).
- If a single chunk still approaches 600 lines, further-split the Overview/chart into its own chunk.

**Implementation risk to verify in the plan:** how tightly `PaperList` (in `10_pdf_layer.jsx`) is coupled to the sidebar/library state in `40_app.jsx`. If it can be parameterized with an injected `axis_id` scope + its own search/sort/selection state, reuse it directly. **Fallback:** if it's too coupled to extract cleanly, reuse only the card *rendering* (a presentational card + a scoped data hook) — still preserves the #13 aesthetic. The plan resolves which.

---

## 6. Principles / gate check
- No new claim/signal/judgment, no new external fetch, no new endpoint → **no security-audit gate, no Principles-gate trigger.** The added OpenAlex stats are pre-cached facts shown verbatim + attributed (consistent with inc 81's "OpenAlex's authoritative figures, never a callosum composite").
- **Rule #8 (DESIGN.md)** applies: any new CSS conforms to tokens/recipes; the publication cards reuse existing library-card styling; new controls reuse `.btn-*`/token recipes.

---

## 7. Verification plan
- **pytest** green (extend My-Pubs dashboard tests for the two new OpenAlex fields; assert the dashboard response shape).
- **ruff** clean; rebuild `callosum-app.html`.
- **Playwright (headed, against :8888 live data):** confirm the four-section order; Overview collapse/expand; chart flip Publications⇄Citations + 10-year `'NN` labels; star-filter hidden when no starred pubs; the publications list renders library-style cards scoped to the axis with working search/sort; the OpenAlex footer card shows as-of/gap/stats/refresh; the "Review N →" modal opens and Import/Dismiss/Restore still work.

---

## 8. Out of scope (SP2 / SP3)
- **SP2:** group-by-domain layout (#9), rename domains vs axes (#15), domains → AXES-card subheadings (#16), starred-first A–Z sorting within cards (#17), chart-filter-on-domain-select (#18).
- **SP3:** citation counts on cards + click → citing-articles modal → import (#14) — needs a new OpenAlex "cited-by" fetch (audit + Principles gate).
- SP1 only **relocates** the Decompose button (#10); its grouped output is SP2.
