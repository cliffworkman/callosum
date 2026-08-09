# Increment 462 — Open-science statement insertion (backlog #33/#34, P2 item #21)

## Implemented

Fourth item in the confirmed P2-leapfrog roadmap (#19 → #17 → #20 → **#21** → #18 → #22; see memory
`callosum-p2-leapfrog-roadmap`). Extends the shipped CRediT-insertion pattern (build → stage → LibreOffice
pulls & inserts) to 7 more manuscript-level disclosures: data availability, code availability, preregistration,
funding, conflict of interest, ethics, and AI use. Two scope decisions confirmed with Cliff before the plan:
(1) each of the 7 gets click-to-fill canned starting phrases (mirroring CRediT's own role-bundle pattern), and
(2) one combined mechanism — a single new tab, one generalized backend pending store keyed by kind, and one new
LibreOffice command with a picker — rather than 7 parallel endpoints/menu items.

Research confirmed none of the 7 has any structured source of truth in callosum today (checked `wip_manuscripts`
and the funding-search tables `research_funding_profiles`/`funding_search_runs` — the latter is a
funder-discovery search profile, not a record of funding actually received); every one is, like CRediT itself,
something only the author can assert.

### New backend router: `app/backend/api/routers/statements.py`

Generalizes `credit.py`'s own single-slot `_pending_statement = {"text": ""}` hand-off into a dict keyed by
kind. Not folded into `credit.py` (materially different content, and `credit.py` stays untouched). No
formatting endpoint (unlike CRediT's `/credit/statement`) — a statement here is just the text the author typed,
not a computed layout from structured input.

```python
STATEMENT_KINDS = (
    "data_availability", "code_availability", "preregistration",
    "funding", "conflict_of_interest", "ethics", "ai_use",
)
_pending_statements: dict[str, str] = {}

@router.post("/statements/pending", response_model=dict[str, str])
def stage_pending_statement(payload: PendingStatementRequest) -> dict[str, str]:
    if payload.kind not in STATEMENT_KINDS:
        raise HTTPException(status_code=422, detail=...)
    text = payload.text.strip()
    if text:
        _pending_statements[payload.kind] = text
    else:
        _pending_statements.pop(payload.kind, None)  # clearing the box un-stages it
    return dict(_pending_statements)
```

Mounted beside `credit.router` in `app.py`.

### New frontend tab: `app/frontend/js/38b_statements.jsx`

Sorts right after `38_credit.jsx` in the alphabetical build order (the `10_pdf_layer.jsx`→`10b_libmenus.jsx`
naming convention). `registerWorkspaceTab({ id: "work" }, { id: "statements", label: "Statements", order: 31,
... })` — right next to CRediT (order 30). A fixed `STATEMENT_TYPES` array (2-4 canned phrases per kind, real
common scholarly-publishing boilerplate — e.g. data availability's "available on request" / "openly available"
/ "restricted third-party" / "no new data"). Each of the 7 sections: a label, a row of short-labeled phrase
buttons, a textarea, Copy, and Send to LibreOffice. Clicking a phrase **replaces** the textarea (these are full
alternative sentences, not fragments to append) — gated by a `window.confirm` if the box already holds text the
user typed or edited, never a silent overwrite. State persists per-context via `_loadLayout`/`_saveLayout`
keyed on `ctx.selectedPaper` with a `"_"` fallback, the exact CRediT scoping convention.

Reuses CRediT's own outer-wrapper classes (`grim-section ws-pad`) and the generic `settings-input` textarea
recipe; adds a small `.statements-*` CSS block that mirrors `.credit-author`/`.credit-presets`/`.credit-preset`/
`.credit-actions`/`.credit-staged` token-for-token under its own prefix (DESIGN.md §3 #8's own precedent — a
legitimately distinct control, not a re-type).

### Adapter: `adapters/libreoffice/callosum_cite.py` (no new sibling module)

Unlike inc 461's three-dialog "Insert evidence" flow, this reuses the **existing** `_choice_box` helper
directly — no new dialog construction needed:

```python
def insert_staged_statement(doc, base=DEFAULT_BASE):
    staged = statements_pending(base)
    if not staged:
        _msgbox("No open-science statements staged yet — ...")
        return
    options = tuple((f"{STATEMENT_KIND_LABELS.get(kind, kind)} — {text[:60]}", kind) for kind, text in staged.items())
    chosen = _choice_box(doc, "Insert statement", "Choose which staged statement to insert:", options, options[0][1])
    if chosen is None:
        return
    doc.getText().insertString(_insertion_cursor(doc), staged[chosen] + "\n", False)
```

Registered as `_ACTIONS["insertStagedStatement"]`, a new macro `CallosumInsertStagedStatement` +
`g_exportedScripts` entry, and a new Addons.xcu menu node ("Insert statement…", next to "Insert evidence…").
CRediT's own "Insert CRediT statement" command is completely untouched.

## Key technical detail

**Un-staging on empty text keeps the picker honest.** Unlike CRediT's own `/credit/pending` (which stores
whatever text is sent, even `""`, and lets `insert_statement`'s own `if not text` check catch the empty case),
this router actively **removes** a kind from `_pending_statements` when its staged text is blank. This matters
specifically because `insert_staged_statement` builds a picker listing every currently-staged kind — a stored-
but-empty entry would show up as a confusing blank choice in that list. CRediT never needed this because it has
only ever had one slot, never a list to browse.

## Housekeeping / gates

- **Security audit**: `.claude/security-audits/2026-08-08_open-science-statements.md` (gate criteria #1 new
  endpoints, #5 net-new feature 3+ files) — no egress, no SQL, no new dependency, bounded text (4000 chars),
  kind validated against a fixed allowlist, in-memory only, not on the cloudflared cite-endpoint allowlist
  (matches `/credit/*`'s own precedent). PASS.
- **QA route**: `.claude/qa-routes/route_88_statements.md` (route 88, next free number), modeled on
  `route_66_credit.md`'s shape (build-never-infer boundary, egress-off assertion, canned-phrase-confirm-gate
  assertion).
- `.claude/docs/INCREMENT-BACKLOG.md`: P2 item #21 marked **✅ CLOSED inc 462**; roadmap-order note updated.
- Memory `callosum-p2-leapfrog-roadmap` updated: item #21 marked closed, #18 named as next up.
- `.claude/CLAUDE.md`: counter bumped to 462; pytest count updated to the actual measured total.

## Manual verification script

1. Open Work → Statements. Confirm all 7 sections render with the intro copy.
2. Click a canned phrase for Data availability → confirm the textarea fills; edit the placeholder text; click a
   different phrase → confirm a confirm-before-replace prompt appears.
3. Send to LibreOffice for 2-3 different statement kinds. Confirm each shows its own persistent "Staged…" hint.
4. In real Writer, run Insert statement… → confirm the picker lists exactly the staged kinds with a text
   preview, pick one, confirm it lands at the cursor as plain text (no citation mark).
5. Confirm Work → CRediT's own tab, grid, and "Insert CRediT statement" command all still work unchanged.

## Verification

- `pytest tests/test_statements.py tests/test_libreoffice_adapter.py tests/test_libreoffice_composer.py
  tests/test_libreoffice_oxt.py tests/test_credit.py tests/test_frontend_assembly.py -q` → **266 passed** (7
  new backend staging tests + 4 new adapter tests, all UNO-free via monkeypatching).
- `ruff format` + `ruff check`: clean on all touched files.
- `python tools/check_line_budget.py`: unaffected (`501 application-source files within the 600-line cap`; the
  new frontend chunk is 155 lines, the new backend router 55 lines).
- `python tools/build_frontend.py`: rebuilt after the new `38b_statements.jsx`.
- `python tools/qa/build_surface_map.py check`: `API surfaces: 386 | covered: 386 | uncovered: 0` (up from 384).
- Real-UNO: `python adapters/libreoffice/run_roundtrip.py` — the new `spike_insert_staged_statement` proves the
  real multi-kind staging round trip through the actual endpoint and that the picker inserts exactly the chosen
  kind's text (not the other staged kind's), plus the honest "nothing staged" message path.

## Rollback

Revert `app/backend/api/routers/statements.py` (new file, delete), the statements import/mount in
`app/backend/api/app.py`, `app/frontend/js/38b_statements.jsx` (new file, delete; re-run
`tools/build_frontend.py` after), `app/frontend/styles.css`, `adapters/libreoffice/callosum_cite.py`,
`adapters/libreoffice/oxt/Addons.xcu`, and `adapters/libreoffice/selftest_uno.py` to their pre-462 state. All
changes are additive/backward-compatible (a new endpoint pair, a new frontend tab, a new adapter command); no
schema/migration involved.
