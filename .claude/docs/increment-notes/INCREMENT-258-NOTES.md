# INCREMENT 258 — Workbench SP2b: the dataset loop (Convert all) + stat-package exports (metafor / RevMan)

**Future track:** #36 (meta-analysis extraction workbench). SP1 (effect-size converter, inc 252) → SP2a-1 (the grid,
inc 253) → SP2a-2 (select-in-PDF capture, inc 255) → **SP2b (this): the accumulating dataset loop + native exports.**

## Implemented
Turns the per-row extractions into an **accumulating dataset that feeds the SP1 converter across the whole included
set**, and exports it **stat-package-ready** — deterministic, local, no egress, no values gate.

- **`POST /workbench/projects/{project_id}/convert-all`** (`app/backend/api/routers/workbench.py`) — the dataset loop.
  Runs the existing per-row `effectsize.convert` over **every** row of the project (reusing the cells already in
  `project_view` — no extra query per row). A row with incomplete/invalid inputs is left **honestly un-converted**
  (`set_converted(None)`) and named in an `incomplete` list; a valid row's `converted` is (re)written. Returns
  `{total, converted, incomplete}` — **a count, never a pooled/averaged effect.**
- **New pure export module `app/backend/persistence/workbench_export.py`** (161 lines) — `view -> CSV-text` builders,
  extracted so the router stays thin and each format is unit-testable. Three formats behind a `FORMATS` dict:
  - `generic_csv` — the SP2a-1 format (row label + template columns + converted metric/value/variance), moved here
    verbatim.
  - `metafor_csv` — one row per study: `study,yi,vi,sei,ci_lb,ci_ub,metric,<moderator columns>`. The role (raw-stat)
    columns are omitted (redundant with yi/vi); moderator/notes columns ride along for meta-regression. An
    un-converted row exports **blank** yi/vi (an honest gap, never a fabricated 0). The R handoff
    (`read.csv(...)` → `rma(yi, vi, data=dat)`) lives in the button tooltip + help, **not** in the file (a clean data
    file must survive a plain `read.csv()`).
  - `revman_csv` — RevMan's **raw** study data per design (RevMan computes the effect itself): continuous →
    `Study,Mean 1,SD 1,Total 1,Mean 2,SD 2,Total 2`; dichotomous → `Study,Events 1,Total 1,Events 2,Total 2`
    (Total = events + non-events, i.e. `a+b` / `c+d`); correlation → Generic-IV `Study,Effect,SE` (Fisher's z + SE
    from the converted row, since RevMan has no native correlation outcome).
  - `export_project` now dispatches `csv|metafor|revman` through `FORMATS` and keeps `audit` (provenance JSON);
    unknown `format` → **422** (allowlist).
- **Frontend `app/frontend/js/45_workbench.jsx`** — a **Convert all →** button + a **"k of N converted"** readout in
  the project header (`project.rows.filter(r => r.converted).length`), an **Export** label, and four download buttons
  (**CSV / metafor / RevMan / provenance**). A transient `convMsg` note reports the batch result ("Converted k of N
  rows. m still need valid inputs."). `.wb-head` got `flex-wrap: wrap` so the fuller header wraps rather than
  overflowing (reuses `.wb-note` / `.wb-meta` — no new tokens/classes; DESIGN #8 clean).

## Key technical detail
- **The load-bearing boundary is preserved (rule #9 / PRINCIPLES).** Convert-all is the **same audited per-study
  convert, N times** — it introduces **no** pooling, weighting, heterogeneity, meta-regression, or forest plot. The
  "k of N converted" readout is honest **coverage** (Principle #6: signal, not an opaque composite), not a synthesized
  estimate. metafor gets per-study `yi/vi`; RevMan gets **raw** per-group data (the downstream tool computes the
  effect). No export ever carries a summary row. The misaligned easy path (a convenience "pooled effect so far"
  readout) was declined on purpose.
- **Number-aware `_csv_safe` (a correctness fix folded in).** The moved formula-injection guard now neutralises a
  leading `=/+/-/@` **only when the value is not a plain number** (`float(s)` succeeds → pass through). This fixes a
  pre-existing bug where a **negative** effect size / mean was corrupted into `'-0.59`, which would have made
  metafor's `yi` column non-numeric in R. Genuine formula text (`=DANGER()`) is still `'`-prefixed.
- **RevMan dichotomous totals.** Our 2×2 cells are events + non-events per group (`a,b,c,d`); RevMan wants events +
  group **total**, so the export derives `Total 1 = a+b`, `Total 2 = c+d` (rendered as ints when whole), leaving the
  raw events (`a`, `c`) as-is.

## Security
Audit `.claude/security-audits/2026-07-03_workbench-convert-all.md` — **PASS**. New endpoint + two new export shapes;
local-only, no egress, no new dependency; `format` allowlist + int path params (no injection in the
`Content-Disposition` filename); convert-all is O(rows) over already-loaded cells (no N+1, self-bounded); CSV
formula-injection neutralisation hardened (number-aware). Negative paths pinned by tests (unknown project → 404,
bogus format → 422, incomplete rows reported not fabricated, negative number stays clean, `=DANGER()` neutralised).

## Manual verification script
1. `python tools/build_frontend.py`; start on **:8888**; open **Extract**.
2. New project → **two-group continuous**. **+ Add row** ×2. Fill row A validly (m1/s1/n1/m2/s2/n2); leave row B blank.
3. **Convert all →** → header reads **"1 of 2 converted"**; the note names row B as still needing valid inputs (B is
   *not* given a number).
4. **Export → metafor** → a `study,yi,vi,sei,ci_lb,ci_ub,metric` CSV; row A numeric, row B blank yi/vi. If group 1 <
   group 2, confirm yi is a clean negative number (not `'-…`). Add a **+ col** moderator → it appears as a trailing
   column.
5. **Export → RevMan** → `Study,Mean 1,SD 1,Total 1,Mean 2,SD 2,Total 2` with the raw per-group numbers (no computed
   effect). Repeat on a **binary 2×2** project → `Events/Total ×2` with Total = a+b / c+d; on a **correlation**
   project → `Study,Effect,SE` (Fisher's z).
6. **Export → CSV** (generic) + **provenance** (audit JSON) unchanged. Confirm **no pool/forest/heterogeneity control**
   anywhere and **no summary row** in any export.

## Pytest
`pytest --ignore=tests/test_mcp_server.py` → **1012 passed, 1 skipped** (+3 new workbench tests: convert-all honest
coverage; metafor yi/vi columns + negative-effect cleanliness + blank-for-un-converted; RevMan raw data per design).

## Rule #11 — end-user experience pass
Dispatched a persona-grounded experience agent (**deadline meta-analyst**, ~40-study dataset) to drive Convert-all +
the four exports end-to-end (into R). **What held:** the `read.csv(...)` → `rma(yi, vi, data=dat)` handoff works
as-is (extra moderator columns ignored; an un-converted row reads in as `NA` and `rma` drops it — never a fabricated
0); negative effect sizes pass through as plain numbers; RevMan raw columns are right; the live "k of N converted"
readout is honest; and the impatient "just pool it / draw a forest plot here" is correctly **declined** (no pooling
control anywhere) — the load-bearing boundary is felt, not just coded.

**Cheap fixes folded into this increment (frontend-only, count unchanged):**
1. **Name the un-converted rows in the note** — `convertAll` now lists the `incomplete` labels ("Still need valid
   inputs: A, B, …", capped at 6 + "+N more"). The backend already returned them; the count-only message left the
   user hunting *which* rows in a 40-row grid.
2. **The batch note can no longer go stale** — `convMsg` is cleared on a single-row **Convert** and on any **cell
   edit**, so the transient note can't contradict the live "k of N converted" header readout (a mild honesty smell:
   a displayed count lagging the true one).
3. **Tooltips on the CSV + provenance export buttons** (metafor/RevMan already had them) — provenance now says it's a
   JSON audit trail, CSV says it's the general dataset + effect; they no longer read like a fourth spreadsheet format.

**Filed to `INCREMENT-BACKLOG.md` (#36), not cheap enough for this increment:** (a) surface the converter's
**caveats/choices/CI on the converted cell** (an amber marker/tooltip) — Convert-all paints N green `metric = value`
cells silent about continuity corrections (Haldane +0.5) + approximation flags that currently live only in the
provenance JSON — **principle-relevant** (every claim carries its evidence); (b) **field-level "why this row failed"**
+ blank-vs-invalid, and specifically the **comma-decimal** trap (`float("12,5")` throws → a filled-looking cell
silently won't convert); (c) generic-CSV page/quote columns for supplement tables, a **0-converted export guard**, and
promoting **Convert all →** to a real button (DESIGN-gated).
