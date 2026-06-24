# My Publications SP2 — Domain Organization — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline). Steps use `- [ ]` checkboxes.

**Goal:** Organize the My Publications corpus by research domain — group-by-domain (dashboard + sidebar card), rename domains (axis-suggested, persistent across re-decompose), starred-first sorting, and domain-driven chart locking.

**Architecture:** Additive backend (expose `paper_ids`/`starred_ids`/per-paper `domain`; one rename endpoint; decompose preserves custom labels by paper-overlap). Frontend: a group-by-domain toggle + grouped rendering in `MyPubsPublications` and the `15_axes.jsx` My-Pubs card; a rename affordance; the Overview chart lock. Spec: `.claude/docs/specs/2026-06-24-mypubs-sp2-domains-design.md`.

**Tech Stack:** FastAPI/SQLAlchemy Core (backend); React JSX chunks + esbuild (frontend); pytest + ruff + headed Playwright (`.local/visual/`, server `:8099`).

## Global Constraints
- 600-line cap. `31_mypubs_dashboard.jsx` 296, `33_mypubs_pubs.jsx` 136, `15_axes.jsx` ~500, `clustering/my_publications.py` ~505, `routers/my_publications.py` ~430 — watch the two backend files.
- Parameterized SQL; the rename is a pure profile-JSON write. **No migration, no egress.** `custom` flag lives in the existing `research_domains` JSON.
- Rule #8 (DESIGN.md) for CSS; tokens/recipes only. Rule #9: SP2 is organizational — no Principles trigger; the one new endpoint → a short security audit.
- After any `app/frontend/` edit: `python tools/build_frontend.py`; verify headed on `:8099`. `pytest` + `ruff format`/`check` green before each commit. Commit locally; push is enabled (end-of-session default).

---

## Task 1: Backend — grouping inputs (`paper_ids`, `starred_ids`, per-paper `domain`)

**Files:** `routers/my_publications.py` (`Domain`, `DashboardResponse`, the clusters response for my-pubs), `clustering/my_publications.py` (`build_dashboard`, and the my-pubs branch of the clusters builder), `routers/axes.py` if the clusters response model lives there; `tests/test_my_publications.py`.

**Interfaces:**
- Produces: `Domain.paper_ids: list[int]`; `DashboardResponse.starred_ids: list[int]`; `ClusterPaperResponse.domain: str | None` (populated only for `kind="my_publications"`, like `starred`).

- [ ] **Step 1 — failing test:** assert `build_dashboard(...)["domains"][0]["paper_ids"]` is the cluster's ids and `["starred_ids"]` reflects the profile; assert the my-pubs clusters response carries `domain` per paper. (Extend the existing dashboard + clusters tests; reuse `_ADA_STATS` + a profile with `research_domains` set.)
- [ ] **Step 2 — run, verify fail.**
- [ ] **Step 3 — implement:**
  - `build_dashboard`: in the domains list comprehension add `"paper_ids": d.get("paper_ids", [])`; add top-level `"starred_ids": list(profile.get("starred_paper_ids") or [])`.
  - `Domain` model: `paper_ids: list[int] = []`. `DashboardResponse`: `starred_ids: list[int] = []`.
  - Clusters (my-pubs): build a `paper_id → domain label` map from `research_domains` and set `domain` on each `ClusterPaperResponse` (mirror the inc-84 `starred` gating — only when `axis.kind == "my_publications"`). `ClusterPaperResponse.domain: str | None = None`.
- [ ] **Step 4 — run tests, verify pass.**
- [ ] **Step 5 — full `pytest -q` + `ruff check`.**
- [ ] **Step 6 — commit** `feat(my-pubs): expose domain paper_ids + starred_ids + per-paper domain (SP2 T1)`.

---

## Task 2: Backend — rename a domain + persist across re-decompose

**Files:** `persistence/profile_repo.py` (`rename_domain`), `routers/my_publications.py` (endpoint + model), `clustering/my_publications.py` (`decompose_domains` preserve-by-overlap), `tests/test_my_publications.py`, `.claude/security-audits/2026-06-24_mypubs-domain-rename.md`.

**Interfaces:**
- Produces: `POST /my-publications/domains/rename` body `{paper_ids: list[int], label: str}` → 204; sets the matching `research_domains` entry's `label` + `custom=True`. `profile_repo.rename_domain(conn, paper_ids, label) -> bool`.

- [ ] **Step 1 — open the audit stub** (input validation: label ≤ 80 chars / stripped / plain text; identify-by-paper_ids set-equality; local profile-JSON write; no egress; no SQL surface).
- [ ] **Step 2 — failing tests:** (a) rename sets label + `custom` on the entry whose `paper_ids` match; empty label / no match → the endpoint 422. (b) after a rename, `decompose_domains` re-run carries the custom label onto the new cluster sharing ≥0.5 of its papers.
- [ ] **Step 3 — run, verify fail.**
- [ ] **Step 4 — implement `rename_domain`** in `profile_repo.py`: load profile, find the `research_domains` entry with `set(d["paper_ids"]) == set(paper_ids)`, set `label` (stripped, capped) + `custom=True`, write back; return False if none matched.
- [ ] **Step 5 — endpoint** in `routers/my_publications.py`: `RenameDomainRequest{paper_ids: list[int], label: str}`; 422 if `not label.strip()` or `rename_domain` returns False; else 204.
- [ ] **Step 6 — preserve-by-overlap in `decompose_domains`:** before overwriting, snapshot `[(d["label"], set(d["paper_ids"])) for d in old research_domains if d.get("custom")]`. After building new clusters, for each new domain compute Jaccard vs each snapshot; if best ≥ 0.5 (and that snapshot unused), set the new domain's `label` = snapshot label + `custom=True`. Highest overlap first; each snapshot label used once.
- [ ] **Step 7 — run tests pass; full `pytest -q` + `ruff`.**
- [ ] **Step 8 — finish the audit (PASS).**
- [ ] **Step 9 — commit** `feat(my-pubs): rename domains (persist across re-decompose by paper-overlap) (SP2 T2)`.

---

## Task 3: Frontend — dashboard group-by-domain + starred-first

**Files:** `33_mypubs_pubs.jsx` (grouping + starred-first), `31_mypubs_dashboard.jsx` (pass `domains` + `starredIds`), `styles.css`.

**Interfaces:** `MyPubsPublications` gains props `domains` (`[{label, paper_ids}]`) + `starredIds` (`number[]`); a `groupByDomain` toggle (persisted `localStorage["callosum.mypubsGroupByDomain"]`).

- [ ] **Step 1** — `MyPubsDashboard` passes `domains={data.domains}` + `starredIds={data.starred_ids}` to `MyPubsPublications`.
- [ ] **Step 2** — add a **starred-first comparator**: `starred (A–Z by title) then non-starred (A–Z)`, `starredIds` as a Set. Apply to the flat list always.
- [ ] **Step 3** — add the **"Group by domain"** toggle to the controls row (`.mypubs-pubs-controls`). When ON: build `domainOf = paper_id → label` from `domains`; partition `papers` into per-domain buckets (in `domains` order) + an **"Other"** bucket (no domain); render each as a `.mypubs-domain-group` (a `.mypubs-domain-group-head` with label + count, then its cards in a `.mypubs-domain-group-body` with a left rule), starred-first within each. Search filters before grouping. OFF → the flat starred-first list.
- [ ] **Step 4** — CSS (read DESIGN.md): `.mypubs-domain-group`, `.mypubs-domain-group-head` (label + muted count), `.mypubs-domain-group-body { border-left: 2px solid var(--line); padding-left: …; }`. Tokens only.
- [ ] **Step 5** — rebuild; headed verify on `:8099` (`drive_mypubs.py`): toggle ON → cards regroup under domain headers + "Other"; starred float to the top of each group; search still narrows; toggle OFF → flat list. Screenshot.
- [ ] **Step 6** — `pytest -q` + `ruff check` (frontend-only; confirm). Commit `feat(my-pubs): dashboard group-by-domain + starred-first (SP2 T3)`.

---

## Task 4: Frontend — rename domains (axis-suggested) + Overview chart lock (#18)

**Files:** `31_mypubs_dashboard.jsx` (rename UI in the domains section + chart lock), `styles.css`.

- [ ] **Step 1 — chart lock (#18):** in `MyPubsDashboard`, when `selectedDomains.size > 0` force `chartMode === "pubs"` for the rendered chart and render the **Citations** pill `disabled` with a title "clear the domain filter to see citations". Clearing re-enables it. (The domain-filtered `chartBars` path already exists from SP1.)
- [ ] **Step 2 — rename affordance:** each `.domain-row` gets an **✎** button (stopPropagation) → swaps the label to an inline `<input>` (+ a `<datalist>` of existing axis labels fetched once from `/axes`). Pre-fill: the closest axis label by simple term-overlap (`domain.terms` ∩ axis label/terms) when overlap is clear, else the current label.
- [ ] **Step 3 — save:** Enter / blur → `apiPost("/my-publications/domains/rename", { paper_ids: domain.paper_ids, label })` → on ok `refetch()`. Esc cancels.
- [ ] **Step 4 — CSS:** `.domain-rename-input` (reuse `.mypubs-pubs-search` recipe); the ✎ reuses `.axis-icon-btn`. Tokens only.
- [ ] **Step 5 — rebuild; headed verify** (`drive_mypubs.py` / a focused driver): select a domain → the Overview chart locks to Publications + the Citations pill is disabled; rename a domain → it sticks; **Re-decompose → the custom name persists** (the T2 overlap path). Screenshot.
- [ ] **Step 6 — `pytest`/`ruff`; commit** `feat(my-pubs): rename domains UI (axis-suggested) + chart lock on domain select (SP2 T4)`.

---

## Task 5: Frontend — sidebar My-Publications card: domain subheadings + starred-first

**Files:** `15_axes.jsx` (the `isMyPubs` branch of `AxisItem`), `styles.css`.

- [ ] **Step 1** — in the `isMyPubs` paper-list render, when papers carry a `domain` (from T1's clusters response), group the `AxisPaperRow`s under **collapsible domain subheadings** (label = the `domain` value; "Other" last), starred-first within each (reuse the comparator; `AxisPaperRow` already shows the ⭐). No domains / none decomposed → the current flat sorted list.
- [ ] **Step 2** — keep the inc-77/79 hide-uncertain behavior working within groups (filter before grouping).
- [ ] **Step 3** — CSS: `.axis-domain-subhead` (small muted, collapsible chevron) + indent the grouped rows. Tokens only.
- [ ] **Step 4** — rebuild; headed verify: expand the My-Publications sidebar card → rows grouped under domain subheadings, starred first; collapse a subheading. Screenshot.
- [ ] **Step 5** — `pytest`/`ruff`; commit `feat(my-pubs): sidebar card groups papers by domain subheading, starred-first (SP2 T5)`.

---

## Task 6: Verification + docs

- [ ] **Step 1** — full `pytest -q` + `ruff format --check` + `ruff check` green.
- [ ] **Step 2** — full headed Playwright pass on `:8099`: group toggle (both surfaces) + "Other" + starred-first + rename (sticky across re-decompose) + chart lock. Read screenshots.
- [ ] **Step 3** — docs: `INCREMENT-118-NOTES.md`; `changes.md` entry (+ HELP-DOCS-SYNCED if the help corpus needs the group/rename note — likely a short My-Pubs addition); `CLAUDE.md` footer + decision-log row + number→118; help corpus My-Pubs section (group-by-domain + rename).
- [ ] **Step 4** — RECOVERY-LOG line; commit `docs(my-pubs): SP2 increment notes + changelog + CLAUDE.md + help (inc 118)`.
- [ ] **Step 5** — push (end-of-session default) on the user's OK.

---

## Self-review
- **Coverage:** #9 → T3 (dashboard) + T5 (sidebar); #17 → T3/T5 starred-first; #15 → T2 (backend persist) + T4 (UI); #16 → T1 (`domain` per paper) + T5; #18 → T4 chart lock. All covered.
- **Refinement of spec §3.4:** the sidebar grouping rides a per-paper `domain` field on the existing `/axes/{id}/clusters` response (gated to my-pubs, mirroring inc-84 `starred`) — no new route, no second fetch.
- **Types:** `paper_ids`/`starred_ids`/`domain` consistent across T1↔T3↔T5; rename body `{paper_ids,label}` consistent T2↔T4.
- **Gate:** one new endpoint (rename) → security audit in T2; no migration/egress; OpenAlex/clustering posture unchanged.
