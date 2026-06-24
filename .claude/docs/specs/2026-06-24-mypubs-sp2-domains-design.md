# Design spec — My Publications overhaul, SP2: domain organization

**Date:** 2026-06-24
**Status:** approved design → spec under review
**Scope:** SP2 of the 3-sub-project overhaul. Covers TDL **#9, #15, #16, #17, #18**.
**Builds on:** SP1 (inc 117 — the restructured dashboard + publications list + flip-chart). **Next:** SP3 — citing articles (#14).

---

## 1. Goal

SP1 made the user's corpus a browsable list. SP2 organizes it by **research domain** (the inc-83 local clustering of
confirmed own-papers, stored as `profile.research_domains` JSON `[{label, terms, paper_ids}]`): group the publications
by domain (in the dashboard *and* the sidebar axis card), let the user **rename** domains (with their axis vocabulary
suggested), sort **starred-first**, and make domain selection drive the Overview chart.

---

## 2. Decisions (from brainstorming)
- **Group-by-domain appears in both** the dashboard Publications list (#9) and the My-Publications sidebar axis card (#16).
- **Custom domain names persist across Re-decompose** by best **paper-overlap** (Jaccard) match — not discarded.
- **Ungrouped papers** (confirmed but in no cluster) collect under an **"Other"** group at the bottom.
- **#18 adapted to SP1's single flip-chart:** selecting domain(s) locks the chart to **Publications (domain-filtered)**
  and disables the **Citations** pill until the selection is cleared.

---

## 3. Backend changes

All additive; the only new endpoint is the domain rename (local profile-JSON edit → a short security audit).

### 3.1 Expose grouping inputs on the dashboard response
- `Domain` model gains **`paper_ids: list[int]`** (the cluster's library paper ids — already in `research_domains`;
  currently dropped from the response). Needed for client-side grouping.
- `DashboardResponse` gains **`starred_ids: list[int]`** (from `profile.starred_paper_ids`) so the client can sort
  starred-first (#17). (SP1 already exposes `starred_count`; this adds the ids.)

### 3.2 Rename a domain — `POST /my-publications/domains/rename`
- Body `{paper_ids: list[int], label: str}` — identify the domain by its `paper_ids` set (stable across reorder),
  set `research_domains[i].label = label.strip()` (cap length, e.g. 80) and mark **`research_domains[i].custom = true`**.
  Idempotent; 422 on empty label / no matching domain. Local, bound nothing-to-SQL (pure profile JSON write).
- `profile_repo.rename_domain(conn, paper_ids, label)`; the `custom` flag lives in the existing `research_domains`
  JSON → **no migration**.

### 3.3 Preserve custom names across Re-decompose
- In `clustering/my_publications.py::decompose_domains`: **before** overwriting `research_domains`, snapshot the
  existing entries that have `custom == true` (their `label` + `paper_ids`). **After** clustering, for each new
  cluster, if a snapshotted custom entry has Jaccard overlap of `paper_ids` ≥ **0.5** with it, carry that entry's
  `label` (and re-set `custom = true`) instead of the auto c-TF-IDF label. Highest-overlap wins; each custom label
  used at most once.

### 3.4 Domains for the sidebar card (#16)
- The My-Publications **axis detail** read (the per-axis papers the sidebar card already fetches) gains a
  **`domains: [{label, paper_ids}]`** block (the current `research_domains`, labels + ids only) so the card can group
  its rows without a second round-trip. (Implementation detail resolved in the plan: either fold into the existing
  axis-detail response for `kind="my_publications"`, or a light `GET /my-publications/domains` the card calls on
  expand. Prefer the former — no new route.)

---

## 4. Frontend changes

### 4.1 Dashboard — group-by-domain (#9) + starred-first (#17)
- `MyPubsPublications` receives `domains` (with `paper_ids`) + `starredIds` as props from `MyPubsDashboard`
  (which has `data.domains` / `data.starred_ids`).
- A **"Group by domain"** toggle on the controls row. OFF → the SP1 flat list (now starred-first sorted). ON →
  render per-domain sections: a **domain header** (label + `Np · C cites`) then that domain's cards **indented behind a
  left vertical rule**; an **"Other"** section last for papers in no domain. Search still filters within groups.
- **Starred-first sort** (both modes): starred (A–Z by title) then non-starred (A–Z). `starredIds` is the key.

### 4.2 Dashboard — rename domains (#15)
- Each domain row in the **Research domains** section gets an **edit (✎)** affordance → an inline input. As the user
  types, a datalist suggests existing **axis** names; the field **pre-fills with the closest axis name** by simple
  term-overlap (domain `terms` vs axis label/description) when one is clearly close, else stays the current label.
  Save → `POST /my-publications/domains/rename`; on success refetch the dashboard.

### 4.3 Sidebar axis card — domains as subheadings (#16) + starred-first (#17)
- In `15_axes.jsx` `AxisItem` (the `isMyPubs` branch), when domains exist, group the `AxisPaperRow`s under
  **collapsible domain subheadings** (label from the card's `domains` data), "Other" last, starred-first within each.
  When no domains (not yet decomposed), fall back to the current flat sorted list.

### 4.4 Overview chart lock (#18)
- In `MyPubsDashboard`: when `selectedDomains.size > 0`, force `chartMode = "pubs"` and **disable the Citations pill**
  (with a tooltip "clear the domain filter to see citations"); the chart shows the domain-filtered pubs (the SP1
  `chartBars` path). Clearing the selection re-enables the flip.

---

## 5. Gate check
- **Audit gate:** one new endpoint (`POST /my-publications/domains/rename`) → a short
  `.claude/security-audits/2026-06-24_mypubs-domain-rename.md` (input validation: label length/encoding; identify-by-
  paper_ids; local profile-JSON write; no egress; no SQL-injection surface — bound params / JSON only).
- **Principles gate:** SP2 is **organizational**, not a new claim/signal/judgment and **no new egress/external fetch**
  (domains are the existing LLM-free local clustering; rename is a user label; chart lock is display). No trigger.
- **Rule #8 (DESIGN.md):** new CSS (group headers, vertical rule, rename input, subheadings) conforms to tokens/recipes.

---

## 6. Verification plan
- **pytest:** rename endpoint (set label + custom flag; 422 empty/no-match); decompose preserves a custom label by
  overlap; dashboard exposes `paper_ids` + `starred_ids`.
- **Headed Playwright (:8099 live data):** group-by-domain toggle regroups the dashboard cards (with "Other"); a domain
  rename sticks and survives Re-decompose; starred-first ordering; the sidebar card groups under subheadings;
  selecting a domain locks the chart to Publications and disables the Citations pill.

---

## 7. Out of scope
- **SP3 — citing articles & citation counts (#14):** citation counts on cards → click → modal of *citing* works →
  import (a new OpenAlex cited-by fetch; trips the audit + Principles gates). Built last.
- The domains section's *position* in the dashboard (it currently sits below the publications list) — SP2 keeps it
  there; a further layout tweak can come later if wanted.
