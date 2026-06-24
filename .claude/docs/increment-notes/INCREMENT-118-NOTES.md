# Increment 118 — My Publications overhaul, SP2: domain organization

The second sub-project of the My Publications overhaul. Organizes the user's corpus by **research domain** — group
the publications by domain (dashboard + sidebar card), rename domains (axis-suggested, persistent across re-decompose),
sort starred-first, and let domain selection drive the Overview chart. Spec/plan:
`.claude/docs/specs/2026-06-24-mypubs-sp2-{domains-design,plan}.md`.

Covers TDL **#9, #15, #16, #17, #18**. Builds on SP1 (inc 117). **Next:** SP3 — citing articles & citation counts (#14).

## Implemented

- **Backend — grouping inputs (T1, additive):** `Domain.paper_ids` + `DashboardResponse.starred_ids` exposed on the
  dashboard response (`build_dashboard` + `_dashboard_domains`); a per-paper **`ClusterPaperResponse.domain`** populated
  only for the `kind="my_publications"` axis (mirrors the inc-84 `starred` gating in `routers/axes.py::axis_clusters`
  via a `paper_id → research-domain label` map). No migration, no egress.
- **Backend — rename + persistence (T2):** `POST /my-publications/domains/rename {paper_ids, label}` →
  `profile_repo.rename_domain` sets the matched domain's `label` + a **`custom`** flag (in the existing
  `research_domains` JSON — no migration). `decompose_domains` now snapshots the old `custom`-flagged domains and
  **re-applies their labels to the new clusters by best paper-overlap (Jaccard ≥ 0.5)** via `_reapply_custom_labels`,
  so a Re-decompose doesn't wipe custom names. Security audit PASS (`2026-06-24_mypubs-domain-rename.md`).
- **Frontend — dashboard group-by-domain + starred-first (T3):** `MyPubsPublications` (`33_mypubs_pubs.jsx`) takes
  `domains` + `starredIds`; a **"Group by domain"** toggle (persisted) regroups the cards under per-domain headers
  (cards indented behind a left rule), with an **"Other"** group last for papers in no domain. **Starred-first** is a
  stable partition applied in both modes (each sub-list keeps the chosen backend sort).
- **Frontend — rename UI + chart lock (T4, `31_mypubs_dashboard.jsx`):** each domain row gets a **✎** that swaps to an
  inline input with an axis-name **`<datalist>`**, pre-filled with the closest axis name by domain-term overlap
  (`suggestAxis`); save → the rename endpoint → refetch. **#18:** when ≥1 domain is selected, the Overview chart locks
  to **Publications (domain-filtered)** and the **Citations** pill is `disabled` until the selection clears.
- **Frontend — sidebar card subheadings (T5, `15_axes.jsx`):** the My-Publications card's rows group under
  **collapsible domain subheadings** (ordered by member count, "Other" last), starred-first within each, using the
  per-paper `domain` from T1. Falls back to the flat sorted list when no domains exist.

## Key technical details

- **The sidebar grouping rides a per-paper `domain` field** on the existing `/axes/{id}/clusters` response (gated to
  the my-pubs axis, mirroring inc-84 `starred`) — no new route, no second fetch. Refines the spec's §3.4.
- **Custom-name persistence is overlap-based, not id-based:** `_reapply_custom_labels` matches each new cluster to a
  snapshotted custom label by Jaccard ≥ 0.5 (highest wins, each label used once) — survives the membership churn a
  re-decompose causes. Unit-tested directly (`test_reapply_custom_labels_by_overlap`).
- **Starred-first = stable partition** (`[...starred, ...rest]`) so the chosen sort (the backend `sort` param) is
  preserved within each tier — no client re-sort needed.
- **The `/papers` `limit` cap (200) from SP1** still bounds the dashboard list; grouping operates on the fetched
  (and search-filtered) set.

## Manual verification script

1. Point a server at the resolved-profile DB (`…/validation-summarize/validation.sqlite`); open the dashboard tab.
2. **Group-by-domain:** tick "Group by domain" in the Publications controls → cards regroup under domain headers +
   "Other"; untick → flat list. Starred pubs float to the top of each group/list.
3. **Rename:** click ✎ on a domain → the input pre-fills the closest axis name; save → the label updates;
   **Re-decompose → the custom name persists** (overlap match).
4. **Chart lock:** click a domain bar → the Overview chart locks to Publications (filtered) + the Citations pill
   disables; clear → it re-enables.
5. **Sidebar:** expand the My-Publications sidebar card → rows grouped under collapsible domain subheadings,
   starred-first; collapse a subheading.

Verified headed via Playwright against the live `:8097` data (`drive_t3.py`, `drive_t4.py`, `drive_t5sb.py`); the
chart-lock + rename round-trip were asserted by computed state and left the data clean.

## Pytest

**432 passed, 1 skipped** (+4 over inc 117: `openalex_extra`/`starred_ids`/`paper_ids` shape, per-paper `domain`,
rename endpoint, `_reapply_custom_labels` overlap). `ruff format --check` + `ruff check` clean.

## Commits (on main)

`8eb3e52` (T1) · `f028939` (T2 + audit) · `df0ef22` (T3) · `1078d42` (T4) · `922c063` (T5) · this docs commit
(also applies a `ruff format` pass the T1/T2 commits had missed).

## Next

**SP3 — citing articles & citation counts (#14):** citation counts on the publication cards → click → a modal of the
papers that *cite* yours → import them. Needs a **new OpenAlex "cited-by" fetch**, so it trips both the security-audit
gate and the Principles gate (a new discovery signal) — built last, on its own.
