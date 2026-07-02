# Increment 253 — Extraction workspace (meta-analysis workbench SP2a-1)

The SP2 slice of the meta-analysis extraction workbench (`future-tracks/opus4.8_future-tracks_metaanalysisextractionworkbench.md`):
a stateful **"Extract" workspace** where a researcher assembles a meta-analysis dataset from their library. SP1 (inc
252) shipped the deterministic effect-size **converter**; SP2a-1 is the **workspace** that feeds it. Manual — no LLM,
no egress (the LLM-drafted extraction is SP2b).

## Decomposition (AskUserQuestion, 2026-07-02)

- **SP2 first slice = the manual workspace** (SP2a) — the egress-free human harness; the LLM drafting (SP2b) rides on
  this later (the doc's "the LLM drafts for a human coder" veto needs the coder's UI to exist first).
- **Provenance = full select-in-PDF anchoring per cell** (the target). SP2a-1 stores the full anchor **model** (page +
  quote + bbox columns) and sets it by a **manual page + quote** entry that opens the paper's PDF at that page;
  **SP2a-2** upgrades to select-in-PDF capture (exact bbox + highlight).
- **Templates = preset-seeded + editable** — a design seeds the converter-input columns; the user adds moderator/notes.

## Implemented

- **`app/backend/persistence/schema_workbench.py` (NEW) + migration 0033:** `ma_projects` (name + protocol_note +
  `design` + `template_json`) / `ma_rows` (project FK CASCADE + a **no-FK** `paper_id` that survives a purge, inc-216
  pattern + `converted_json`) / `ma_cells` (row FK CASCADE + value + page + quote + bbox_json, UNIQUE(row, field_key)).
  Additive/guarded/no-op-downgrade (the 0021-0032 pattern); re-exported from `schema.py` (the schema_findings split).
- **`app/backend/persistence/workbench_repo.py` (NEW):** `DESIGN_TEMPLATES` (three designs → ordered
  `{key,label,type,role}` fields) + `CONVERT_MAP` (design + a row's cells → the SP1 `(family, inputs)`, values passed
  through so `convert` coerces + fails closed) + `role_columns` + all CRUD (`project_view` nests rows+cells+paper
  titles).
- **`app/backend/api/routers/workbench.py` (NEW, sync, before papers):** 11 endpoints —
  `GET/POST /workbench/projects`, `GET/PATCH/DELETE /workbench/projects/{id}`, `POST /workbench/projects/{id}/rows`,
  `PATCH/DELETE /workbench/rows/{id}`, `PUT /workbench/rows/{id}/cells/{field_key}`,
  `POST /workbench/rows/{id}/convert`, `GET /workbench/projects/{id}/export?format=csv|audit`.
  Pydantic `extra="forbid"` + bounded fields; `_validate_template` protects the design's role spine (422 on removing/
  hijacking a converter-input column); the convert hook wraps `convert` fail-closed → 422; the CSV export neutralizes
  spreadsheet formula injection (`_csv_safe` prefixes a leading `= + - @` with `'`). Wired in `app.py`.
- **`app/frontend/js/45_workbench.jsx` (NEW) + `30c_frame.jsx`:** the **"Extract" center-tab** — a project picker +
  New-project form; a project view (editable name + protocol note, the template columns + **+ col**, the extraction
  grid); per-row a paper link (opens the PDF) / editable label, one cell input per field, a per-cell **📎 anchor**
  (a page + quote popover; an anchored cell's 📎 opens the paper's PDF at that page, region precision), a **Convert →**
  button + the resulting **g / variance**; **+ Add paper** (a `/papers?q=` search picker) / **+ Add row**; **Export
  CSV / Provenance JSON**. `.wb-*` CSS (tokens only). Hidden on a read-only companion.

## Key technical detail

**The load-bearing boundary extends SP1 — extract/structure/convert/export, never synthesize.** The workspace converts
one row (study) at a time; **no endpoint combines two rows**, and export is data + provenance, never a pooled estimate.
Every value is **hand-entered by a human** (SP2a-2 will let a PDF selection fill it, still human-confirmed) — nothing
is computed/inferred into a cell. Enforced structurally (no aggregation code path / control) + QA-asserted (`route_65`).

**The template spine is tamper-protected:** `_validate_template` requires the design's role (converter-input) columns
to stay, with matching key/role/type, and forbids a non-role column claiming a role — so the deterministic convert
hook can't be hijacked. Moderator/notes columns are freely added.

**The no-FK `paper_id`:** a row references a paper but survives its purge (the dataset is the user's own extracted
data); `project_view` tolerates a gone paper.

## Experience pass (rule #11, meta-analyst persona, inline)

The meta-analyst can assemble a dataset from the library, anchor each datum, convert, and export metafor-ready.
**Fixed-cheap in-increment:** editing any cell on a **converted** row now **clears the stored effect size** (server +
local) so the "Convert →" button honestly reappears — a stale, silently-wrong g is worse than none. **Deferred (SP2a-2
/ follow-ups):** the select-in-PDF capture UX (the "wow"); wiring the converter's alternate inputs (t/F, SD-derivation)
into the grid; a duplicate-row affordance for multiple effects from one paper (works today by adding the paper twice).

## Manual verification script

`.local/visual/drive_inc253_workbench.py` (headed, no egress): seed 2 papers → **Extract** tab → New project
(two-group continuous) → **+ Add paper** → fill the 6 cells (50/103/5.5/50/100/4.5) → 📎 anchor one to a page + quote
→ **Convert →** → **Hedges' g = 0.592442** → **Export CSV** (the `/export?format=csv` request fires) → confirm no
pool/aggregate control among the pane's buttons + the hand-off note. 0 console/page/genai. **PASS.**

## Gates

- **Audit `.claude/security-audits/2026-07-02_extraction-workspace.md` PASS** (local, no egress/LLM/external-fetch/
  new-dependency; bound-param SQL; typed/validated + allowlisted bodies; CSV formula-injection neutralized; the
  convert-spine tamper-protected; the no-FK paper_id; additive/guarded migration).
- **Principles + A-A (rule #9) — aligned** (extends SP1's extract-never-synthesize; export is data + provenance, never
  a synthesized estimate; every datum human-entered + provenance-anchored — facts-vs-candidates #3, inspectability #8;
  the "pool these / run the meta-analysis / forest plot" easy path declined structurally). No new A-A veto in play.
- **QA (rule #10):** new `route_65_workbench.md`; surface **194/194 API + 883/883 FE, 0 uncovered**.

## Pytest

**991** (+8 hermetic `tests/test_workbench.py`: create-seeds-template + list; add-row/upsert-cell/view; CONVERT_MAP ↔
SP1 (two-group/binary/correlation); CASCADE delete + no-FK paper survives a purge; the endpoint CRUD + convert +
CSV/audit export + the stale-clear; template PATCH guards the role spine; CSV formula-injection escape; delete →
404). `ruff check` + `ruff format --check` clean; frontend rebuilt (`test_frontend_assembly` 5/5).

## NEXT — SP2a-2 (the deferred slice)

The **select-in-PDF capture** UX: arm a cell → open the paper → the next text-selection records exact page/bbox/quote
+ pre-fills the value; click an anchor chip → jump to the **exact highlight** overlay (reuses the inc-30/34/156 viewer
selection→bbox). Then **SP2b** — LLM-drafted, provenance-anchored, human-verified extraction (the egress + heavy-A-A
slice: mandatory human verification, LLM-never-an-independent-coder). Further deferred (per the doc): screening/PRISMA,
double-coding/IRR, RoB instruments, figure/plot digitizing (point at WebPlotDigitizer).
