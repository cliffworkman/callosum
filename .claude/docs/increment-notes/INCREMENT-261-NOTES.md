# Increment 261 — CRediTer (CRediT contribution-statement builder) + THEORY authoring-cluster reorg

## Context — two requests, one increment

1. **"Add tenzing"** — a **CRediT contribution-statement generator**. Shipped as **CRediTer** (a deliberately
   distinct name, per credit-the-lineage — never "tenzing" for our own tool). An **authoring aid**: an authors ×
   14-NISO-role grid → a human-readable contributorship statement. It is a **builder, not a verifier** — it formats
   the contributions the author *asserts*; it never infers, scores, or judges who did what. Local, deterministic,
   no AI, no egress. (Future track #26.)
2. **Move "Review" + "Where to submit"** from the METHODS pane to the THEORY pane. Combined with CRediTer, THEORY
   becomes the **authoring / workflow cluster** (understand → cite → where to submit → credit → review) and METHODS
   stays the per-paper stats-audit suite.

Three forks were locked by the user via AskUserQuestion: output = copy **and** native LibreOffice injection
(copy is the universal fallback); placement = THEORY; statement style = **both** layouts (by-author / by-role) with
a toggle (backend returns both; the toggle only switches which is shown — no re-POST).

**Model mirrored:** the effect-size converter (inc 252) — the closest deterministic/local/no-egress/no-LLM analog
(`methods/effectsize.py` + a `routers/methods.py` endpoint + `08i_methods_effectsize.jsx` + `tests/` + a QA route).

## Implemented

**Part 1 — THEORY reorg** (display order is data-driven by `order`, so these are pure `paneId` flips):
- `app/frontend/js/08_methods_findings.jsx` — "Review" (id `findings`): `paneId: "methods"` → `"theory"`, `order: 40`.
- `app/frontend/js/08e_methods_publishers.jsx` — "Where to submit" (id `publishers`): `paneId: "methods"` → `"theory"`,
  `order: 30`.
- Resulting THEORY order: axes 10 · synthesis 20 · cite 25 · Where to submit 30 · **CRediT statement 35** · Review 40.
- Copy/doc follow-through: `js/35_settings.jsx` ("Theory → Where to submit"); QA `route_38_findings.md` +
  `route_60_publishers.md` placement prose METHODS → THEORY (coverage map unaffected — same chunk filenames + APIs).
  `route_38` line 73 ("Statistics check" section) left as METHODS — **statcheck did not move**, only "Review" did.

**Part 2 — CRediT builder core** (deterministic, local, no egress):
- `app/backend/methods/credit.py` (new, 144 lines) — `CREDIT_ROLES` (the 14 NISO roles, canonical order),
  `DEGREES = ("lead","equal","supporting")`, and `format_statement(authors)` → `{by_author, by_role, roles}`.
  `by_author` lists each author's roles in canonical order (`(degree)` only when set; role-less authors omitted);
  `by_role` lists each role's authors in input order (only roles with ≥1 author). `validate()` rejects unknown
  role/degree + over-cap (`MAX_AUTHORS=50`, `≤14` roles/author, name `≤200`). `NO_INFERENCE = True` is a module
  constant pinned by an AST test (below).
- `app/backend/api/routers/credit.py` (new, 88 lines) — `POST /credit/statement` (Pydantic `Field(max_length=…)`
  caps mirror `validate`; `ValueError`/`KeyError`/`TypeError` → 422), plus the Part-4 pending holder. **Not** added
  to `routers/methods.py` (already 619 lines, over the 600 cap — see hygiene note); mounted in `api/app.py`.
- `app/frontend/js/38_credit.jsx` (new) — `CreditSection` in the THEORY pane: the authors × 14-role grid (role
  chips with an optional degree select), "⤵ pull authors from this paper" (`GET /papers/{id}`, non-destructive),
  per-paper localStorage scratchpad (with a `loadedKeyRef` clobber guard across paper switches), a debounced
  `POST /credit/statement`, the by-author/by-role toggle (no re-POST), Copy + Send-to-LibreOffice, the honesty
  caveat, and the credit block. `registerPaneSection({ id: "credit", paneId: "theory", order: 35, hideInReadOnly:
  true })`.
- `app/frontend/styles.css` — the `.credit-*` recipe (reusing tokens + existing classes only); recorded in
  `DESIGN.md`'s Pass-2 worklist.
- `tests/test_credit.py` (new, 12 tests) — formatter (both layouts, canonical order, degree, dedup, empty→empty,
  unknown role/degree raise, caps raise), an **AST no-inference scan** (`methods/credit.py` imports no
  network/model lib and defines no `infer`/`score`/`judge`/`verify`/`classify`/`predict`/… function), and the 3
  endpoint paths + the pending round-trip.

**Part 3 — QA** (rule #10): `.claude/qa-routes/route_66_credit.md` (new) — covers `/credit/statement`,
`/credit/pending`, `38_credit.jsx`; asserts 0 genai-host requests, build-never-infer, facts≠candidates /
signal-not-verdict, credit-the-lineage, + the adversarial 422 paths. `build_surface_map.py check` clean
(**206/206 API + 987/987 FE**, 0 uncovered).

**Part 4 — native LibreOffice injection** (the grid lives in the web UI; the macro only reaches the server over
HTTP, so a UI→server→macro hand-off): `POST /credit/pending {text}` stores a transient in-memory statement;
`GET /credit/pending` returns it. `38_credit.jsx`'s **Send to LibreOffice** stages the text; the adapter's new
`insert_statement()` (`adapters/libreoffice/callosum_cite.py`, exempt from the 600-cap) pulls it and inserts it at
the cursor as **plain static text** (a contributorship statement is prose the author asserts, not a live citation
field — no ReferenceMark). Registered in `_ACTIONS` + `CallosumInsertStatement` + `g_exportedScripts`; wired as the
`Addons.xcu` menu item "Insert CRediT statement". v1 = LibreOffice only (Word = fast-follow; Docs blocked on the
cloudflared allowlist — both backlogged); copy-to-clipboard covers Word/Docs now.

**Experience-pass fixes** (rule #11 — the "deadline author" persona; four cheap findings fixed in-increment):
Copy made the **primary** button + "Send to manuscript" relabeled **"Send to LibreOffice"** (it is add-on-only, so
the universal action leads); a by-author layout hint under the toggle; the staged confirmation now **persists** and
**clears when the grid changes** (never inject a stale statement); the credit block reframed **"About this tool:"**
so it no longer reads as citations to add to the manuscript. Three larger/debatable findings (per-author role
presets; an "and" before the last by-role name; accordion discoverability) filed to backlog #26, tagged to the
persona.

## Key technical detail

- **The deterministic substrate is the source of truth; the UI only renders it.** The statement text is produced
  by the Python formatter (`format_statement`), never assembled in JS — the by-author/by-role toggle just picks
  which pre-computed list (`result.by_author` / `result.by_role`) to show. There is **no model, no network, no DB**
  anywhere in the path.
- **Build-never-infer is machine-enforced.** `test_no_inference_code_path` AST-scans `methods/credit.py`: any
  future edit that imported a network/model library or defined an inference/scoring/aggregation function would fail
  the test. The fact/candidate line (the human asserts; callosum formats) is a pinned invariant, not just prose.
- **The pending holder is a single module-level variable** in the single-user, single-process uvicorn — transient,
  in-memory, secret-free, touches no file and not the machine-global `app-settings.json`. The macro inserts the
  pulled text as a literal string (`insertString(cursor, s, False)`) — no formula/markup/field injection.

## Gate summary

- **DESIGN (rule #8):** a new `.credit-*` recipe was needed (no existing grid/checkbox recipe). It reuses **tokens
  only** (`--line`, `--panel-2`, `--accent`/`--accent-soft`, `--radius-sm`) and existing classes (`.es-in`,
  `.method-credit`, `.btn*`, `.settings-sub`, `.statcheck-caveat`, `.grim-section`). **Deviation from the plan:** the
  plan sketched a `.credit-grid` *matrix* (authors × roles as a true grid); the built UI uses wrapping **role chips**
  per author instead — far better in the narrow (~260px) sidebar than a 14-column matrix. Recorded in DESIGN.md's
  Pass-2 worklist.
- **PRINCIPLES (rule #9):** aligned. Principle touched — *facts ≠ candidates* / *the human is the filter*. The
  statement is the **author's asserted facts, formatted** — not a callosum claim about the literature; no confidence
  number, no composite score, no verdict. The misaligned easy path (declined): auto-**inferring** roles from the PDF,
  or copy implying callosum *verifies* contributions. Credit-the-lineage honored: the panel credits **tenzing**
  (Holcombe et al. 2020) + the **CRediT/NISO taxonomy** (Brand et al. 2015) in-context with a one-click, idempotent
  library-add, under a distinct name.
- **QA (rule #10):** new `route_66_credit.md`; surface-map `check` clean (206/206 API + 987/987 FE).
- **EXPERIENCE (rule #11):** persona experience agent dispatched (deadline author finalizing a submission). No
  blocker; flow completes end-to-end. 4 cheap findings fixed in-increment; 3 backlogged (above).
- **Security audit:** `.claude/security-audits/2026-07-04_credit-statement.md` — **PASS** (triggers #1 new
  endpoints, #5 3+-file feature). Zero-egress proven statically (no network imports; AST no-inference scan); caps +
  allowlists fail closed at 422; plain-text output.
- **Help corpus:** updated — a new "Building a CRediT contribution statement" section + the three METHODS→Theory
  placement fixes (findings / retractions / where-to-submit). `HELP-DOCS-SYNCED` marker moved forward to this
  increment's `changes.md` entry.

## 600-line-cap hygiene (pre-existing, filed, not this increment's to fix)

Two `app/` files have drifted over the cap and the CLAUDE.md watch-list note was stale on both:
`routers/methods.py` = **619**, `persistence/schema.py` = **628**. inc 261 deliberately avoided landing new code in
either (CRediT is a new router). Filed as backlog #47 (split before the next feature touches either).

## Manual verification script (port 8888)

1. Start the app; select a paper. Open the **THEORY** pane — confirm it now shows **Where to submit · CRediT
   statement · Review** (and METHODS no longer shows the two moved sections).
2. **CRediT statement** section → **⤵ pull authors from this paper** seeds the grid with its author names (no roles
   pre-assigned — build-never-infer). Assign roles to 2–3 authors (set a **lead** degree on one). The **By author**
   output generates live, roles in canonical order, `(degree)` only where set.
3. Flip **[By author | By role]** → the layout switches with no network call. The hint under the toggle reads
   "Most journals ask for the by-author layout…".
4. **Copy** (primary) → the statement is on the clipboard. **Send to LibreOffice** (ghost) → the staged hint appears
   and **persists**; edit any cell → the hint **clears**.
5. In LibreOffice (server URL → 8888) run **Callosum → Insert CRediT statement** → the statement lands at the cursor
   as plain text. With nothing staged, the macro says to build one and click "Send to LibreOffice" first.
6. **＋ add these sources to library** adds tenzing + the CRediT taxonomy (idempotent — re-adding does not duplicate).

## Pytest

`pytest --ignore=tests/test_mcp_server.py` → **1044 passed, 1 skipped** (1032 from inc 260 + 12 new in
`tests/test_credit.py`; the optional `mcp` suite is not installed).
