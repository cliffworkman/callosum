# Design — Meta-analysis extraction workspace (workbench SP2)

**Status:** approved (2026-07-02). The SP2 slice of the meta-analysis extraction workbench
(`future-tracks/opus4.8_future-tracks_metaanalysisextractionworkbench.md`). SP1 (inc 252) shipped the deterministic
effect-size **converter** (`methods/effectsize.py` + `POST /methods/effect-size`). SP2 is the **workspace** that
assembles a dataset and feeds it to that converter.

## What it is

A stateful **"Extract" workspace** where a researcher assembles a meta-analysis dataset from their library: define an
extraction **template**, add rows (one row = one effect/comparison, optionally linked to a library paper), hand-enter
each reported statistic **anchored to its exact source location in the PDF**, convert each row into a common
effect-size metric (via the SP1 converter), and **export** a metafor/JASP-ready dataset plus a full provenance/audit
trail.

**Maintainer scope (AskUserQuestion, 2026-07-02):**
- **First slice = the manual workspace** (SP2a) — the egress-free human harness; the LLM-drafted extraction (SP2b, the
  egress + heavy-A-A slice) rides on this later.
- **Provenance depth = full select-in-PDF anchoring per cell** — a value can be set by selecting text in the PDF
  viewer, which records the exact page/bbox/quote and links the value back to an exact highlight.
- **Templates = preset-seeded + editable** — a project picks a design that seeds the converter-needed columns; you can
  add moderator/notes columns.

## The load-bearing boundary (extends SP1)

The workbench **extracts / structures / converts / exports — it never pools, models heterogeneity, meta-regresses, or
does bias inference.** SP1's converter boundary is inherited (each row converts *one* study; there is no code path that
combines two rows). **Export is data + provenance, never a synthesized result** (no pooled estimate, no I²/τ², no
forest plot). Every extracted datum is **provenance-anchored and human-confirmed** before it enters the dataset — the
value is only ever set by a human (typing it, or confirming a selection), never computed or inferred. In SP2a there is
**no LLM and no egress** at all.

## Delivery — two increments (engine-first)

- **SP2a-1 (this spec's buildable scope):** the backend spine (migration + CRUD + convert + export endpoints) + the
  Extract center-tab + grid + preset-seeded/editable template + the convert hook + export. The **full provenance-anchor
  model is stored** (page + quote + bbox columns); in SP2a-1 a cell's anchor is set by a **manual page + quote** entry,
  and an anchored cell opens its paper's PDF at that page (region precision). Hermetically testable; ships a usable
  manual workbench.
- **SP2a-2 (next increment):** the **select-in-PDF capture** UX — arm a cell → open the paper → the next text-selection
  records exact page/bbox/quote + pre-fills the value; click an anchor chip → jump to the **exact highlight** overlay.
  Reuses the existing viewer selection→bbox machinery (inc 30/34/156); headed-verified.

## Surface (SP2a-1)

A new **"Extract" center-tab** in `app/frontend/js/30c_frame.jsx` (alongside Library / Search / Feed; a `frame-pane`
gated on `activeTab === "extract"`). New chunk `app/frontend/js/45_workbench.jsx` (`WorkbenchPane`):

- **Empty / picker state:** a list of projects (name · design · row count) + **New project** (name + design picker).
- **Project view:** a header (name, protocol note [editable], design), the **template** (its columns; an **+ column**
  to add a moderator/notes field of type number/text/choice), and the **grid**:
  - rows = effects; each row shows its optional **paper link** (title, opens the PDF), an editable **label**, one input
    per template field, a per-row **Convert → effect size** button + the resulting **g / variance** (once converted),
    and a **remove-row** ×.
  - each **cell** = a value input + an **anchor** control (SP2a-1: a small "set anchor" popover with page + quote; an
    anchored cell shows a 📎 chip whose click opens the paper's PDF at that page — region precision).
  - **+ Add paper** (adds a row linked to a chosen library paper — reuse the `/papers?q=` search picker, the inc-162
    add-citation pattern) and **+ Add row** (an unlinked/manual row).
- **Export** buttons: **CSV** (the dataset) + **Provenance (JSON)** (the audit trail).

`.wb-*` CSS (tokens only, rule #8; a grid/table recipe). The Extract tab is hidden in read-only mode (`hideInReadOnly`
posture — a write surface).

## Data model (migration 0033, additive/guarded; `persistence/schema_workbench.py` re-exported from `schema.py`)

- **`ma_projects`** — `id` PK, `name` TEXT, `protocol_note` TEXT nullable, `design` TEXT (`two_group_continuous` /
  `binary_2x2` / `correlation`), `template_json` TEXT (the ordered fields — see Templates), `created_at`, `updated_at`.
- **`ma_rows`** — `id` PK, `project_id` INT FK→ma_projects CASCADE, `paper_id` INT nullable (a **plain column, no FK** —
  it references `papers.id` but must survive a paper purge, like `agent_writes.target_paper_id` inc 216), `label` TEXT
  nullable, `position` INT, `converted_json` TEXT nullable (the stored `Conversion.to_dict()` after a convert),
  `created_at`.
- **`ma_cells`** — `id` PK, `row_id` INT FK→ma_rows CASCADE, `field_key` TEXT, `value` TEXT nullable, `page` INT
  nullable, `quote` TEXT nullable, `bbox_json` TEXT nullable; **UNIQUE(row_id, field_key)** (one cell per field per row
  → upsert). `bbox_json` is set only by SP2a-2's capture.

The **included set** = the distinct `paper_id`s across a project's rows (adding a paper creates a row) — no extra table.

## Templates (preset-seeded + editable)

A template is an ordered list of fields: `{key, label, type, role}` where `type ∈ {number, text, choice}` (choice
carries `options`), and `role` maps a field to a converter input (or `null` for a moderator/notes column). Creating a
project **seeds `template_json` from its `design`**; the user may add/rename/remove **non-role** columns (role columns
are the design's spine and are not removable, to keep the convert hook deterministic).

- **`two_group_continuous`** → roles `n1, m1, s1, n2, m2, s2` (labels "N (group 1)", "Mean 1", "SD 1", …). Convert →
  family `smd`, inputs `{method:"means", m1, s1, n1, m2, s2, n2}`.
- **`binary_2x2`** → roles `a, b, c, d` + a `measure` choice field (`or`/`rr`/`rd`, role `measure`). Convert → family
  `binary`, inputs `{a, b, c, d, measure}`.
- **`correlation`** → roles `r, n`. Convert → family `correlation`, inputs `{r, n}`.

SP2a-1's convert hook uses the design's canonical inputs only. Alternate inputs (a row reporting only a *t* or *F*, or
an SD needing derivation from an SE/CI/IQR) are handled for now by the standalone METHODS **Effect-size converter** +
its copy button; wiring them into the grid is a deferred follow-up (noted).

## Endpoints (`app/backend/api/routers/workbench.py`, registered before `papers.router`)

All local, sync (no async job — CRUD is fast), bound-param. `_project_view` returns a project + its template + rows +
cells (nested).

- `GET /workbench/projects` — list (id, name, design, row_count, updated_at).
- `POST /workbench/projects` `{name, design}` — create; seeds `template_json` from `design`; **422** on a bad
  name/design.
- `GET /workbench/projects/{id}` — the full nested view; **404**.
- `PATCH /workbench/projects/{id}` `{name?, protocol_note?, template_json?}` — validate template (only non-role columns
  editable; a typed model at the boundary, rule #4) → 422 on tampering with role columns.
- `DELETE /workbench/projects/{id}` — CASCADE.
- `POST /workbench/projects/{id}/rows` `{paper_id?, label?}` — append a row (position = max+1); **404** on an unknown
  paper_id.
- `PATCH /workbench/rows/{id}` `{label?, paper_id?, position?}`.
- `DELETE /workbench/rows/{id}`.
- `PUT /workbench/rows/{id}/cells/{field_key}` `{value?, page?, quote?, bbox_json?}` — upsert one cell (field_key must
  be in the project's template → 422 otherwise; `value`/`page`/`quote` bounded).
- `POST /workbench/rows/{id}/convert` — read the row's role-mapped cells → build `(family, inputs)` from the project's
  `design` → `methods.effectsize.convert(...)` → store `converted_json` → return the `Conversion`; **422** if a required
  role cell is empty/degenerate (reuses the SP1 fail-closed).
- `GET /workbench/projects/{id}/export?format=csv|audit` — a `Response`: `csv` = a wide CSV (label + template columns +
  `effect_size`/`variance`/`metric` from `converted_json` where present) with a constant filename; `audit` = a JSON
  (project + per-row per-cell `{value, page, quote, bbox}` + timestamps). Bound-param reads; escaped CSV.

New `persistence/workbench_repo.py` (all data access) + `create_app` wires nothing new beyond the router (no injected
client, no job store — it's synchronous local CRUD).

## Gates

- **Security audit** `.claude/security-audits/2026-07-02_extraction-workspace.md` (triggered: new endpoints + a new
  write path + a migration). Cover: bound-param SQL throughout (rule #3); typed/validated bodies + field-key/template
  allowlisting at the boundary (rule #4); CSV output escaped (no formula-injection — prefix a leading `=`/`+`/`-`/`@`
  in a cell with `'`); **no egress, no LLM, no external fetch** (fully local — the SP1 posture, extended to a stateful
  store); the `paper_id` no-FK survives a purge; export is data+provenance only (no synthesized result); additive/
  guarded migration. End PASS.
- **Principles + A-A (rule #9):** the extends-SP1 boundary — extract/structure/convert/export, **never pool/model/
  adjudicate**; export carries data + provenance, never a synthesized estimate; every datum is human-entered +
  provenance-anchored (facts-vs-candidates #3; inspectability #8; the deterministic substrate is the source of truth,
  the tool only structures it #4). The misaligned easy path (a "pool these rows / run the meta-analysis / here's the
  forest plot" button, or an auto-filled value with no human confirmation) is **declined structurally** — there is no
  such endpoint, and a value is only ever set by a human. **No new A-A veto in play** (no accusation, no paywall
  circumvention, no reaching into another tool's store; the export is the user's own extracted data). SP2b (the LLM
  drafting) will run its own heavy A-A pass.
- **QA (rule #10):** new `route_65_workbench.md` declaring the ~11 API endpoints + the honesty assertions (no
  pool/aggregate control; export = data + provenance; provenance-anchored + human-confirmed) + the `fe:` claim on
  `45_workbench.jsx`. `build_surface_map.py check` at 0-uncovered.
- **Rule #1:** `routers/workbench.py` + `persistence/workbench_repo.py` + `45_workbench.jsx` each kept well under 600
  (split the router by concern if it approaches the cap). **No new dependency.**

## Verification (SP2a-1)

- **pytest `tests/test_workbench.py` (hermetic):** create-project seeds the design's template; add a row (linked +
  unlinked); upsert cells + field-key-not-in-template → 422; convert a two-group-continuous row → the stored `Conversion`
  (g/var matches the SP1 anchor) + a degenerate row → 422; convert binary + correlation designs; CSV export shape
  (header + a converted row's g/var; a leading-`=` cell is escaped); audit export carries per-cell page/quote; template
  PATCH edits a moderator column but **rejects role-column removal** (422); DELETE project CASCADEs rows+cells; the
  `paper_id` column survives a paper delete (no crash on export).
- **Full suite green; ruff check + format; QA check 0-uncovered; `test_frontend_assembly` 5/5** (frontend rebuilt).
- **Headed** `.local/visual/drive_inc253_workbench.py` (no egress): seed 2 papers → Extract tab → New project
  (two-group-continuous) → add both papers as rows → fill a row's cells (with a manual page+quote anchor on one) →
  **Convert** → g/var shows → **CSV export** downloads a dataset row with g/var → confirm **no pool/aggregate control**;
  0 console/page/genai.
- **Docs:** `INCREMENT-253-NOTES.md`; `changes.md`; CLAUDE (count, decision-log, footer, directory-layout — the new
  router/repo/schema + the Extract tab); help corpus "Extracting a meta-analysis dataset" (`HELP-DOCS-SYNCED` → 253);
  backlog (SP2a-1 shipped; SP2a-2 = select-capture; SP2b = LLM drafting). Commit (excluding `www/`), push, watch CI.

## Out of scope (deferred, per the future-track doc)

SP2b LLM-drafted extraction (the egress + heavy-A-A slice); screening/PRISMA front end; double-coding/IRR; RoB
instruments; figure/plot digitizing (point at WebPlotDigitizer); alternate converter inputs wired into the grid;
importing an existing dataset.
