# Increment 446 — expose state for three "state-blind" LibreOffice adapter toggles

## Implemented

Closes the backlog #33/#34 UX-follow-up debt flagged across incs 374/375/376/382/383: three per-document
LibreOffice Writer toggles — automatic bibliography rebuilding, citation-to-bibliography links, and
bibliography title/DOI links — announced only their *new* state after acting, with no way to check current
state without side-effecting it by clicking. Two additive, zero-risk mechanisms close this for all three
(`adapters/libreoffice/callosum_cite.py`):

1. **`diagnose_document`** (the existing read-only "Document diagnostics…" health check) gained a
   `"preferences"` key reusing the three existing getters — `bib_auto_enabled`, `bibliography_links_enabled`,
   `bibliography_external_links_enabled` — no new state-reading logic.
2. **`document_diagnostics_interactive`** now always appends a "Current settings" section listing all three as
   ON/OFF, whether or not any issues were found; "No issues found." continues to describe only the issues
   portion.
3. **`toggle_bib_auto_interactive` / `toggle_bibliography_links_interactive` /
   `toggle_bibliography_external_links_interactive`** now capture the prior state and report the transition
   (`"Automatic bibliography rebuilding: ON → OFF."`) instead of only the destination, sidestepping
   singular/plural label agreement with a uniform arrow template.

A fourth flagged item — "consider an explicit Restore References affordance" on the bibliography-heading
dialog — is evaluated and closed with **no code change**: `set_bibliography_heading_interactive` already
pre-fills the current effective heading and its prompt text already states the reset mechanism ("blank
restores References"), so current state and the reset path are both already visible.

Also touched: `adapters/libreoffice/oxt/description.xml` (version `0.30.0` → `0.31.0`, this project's
established one-bump-per-adapter-touching-increment cadence) and the matching literal in
`tests/test_libreoffice_oxt.py`.

## Key technical detail

**Why a live checkmark on the menu item itself is out of reach.** This adapter's dispatcher
(`callosum_addon.py`) implements `XJobExecutor` (the `service:` Job-dispatch protocol) rather than
`XDispatch` — a deliberate architecture choice for path-independence. LibreOffice's checkable-menu-item
mechanism (`FeatureStateEvent`/`addStatusListener`) only works through a real `XDispatch`/`XDispatchProvider`;
Job dispatch is fire-and-forget with no live status-push channel. Zero precedent for the `XDispatch` mechanism
exists anywhere in this codebase, and rewiring to it would be a much larger, riskier change than this backlog
item warrants. Hence: passive surfacing via an existing read-only command, not a menu checkmark.

**Why a confirm-before-toggle gate was rejected in favor of the above.** The natural alternative design —
read state, show a `_confirm_box` Yes/No, only flip on confirmation — was considered and rejected.
`_confirm_box`'s real-headless-UNO return value for a 2-button dialog has never been exercised anywhere in
`selftest_uno.py`: its one existing caller (the "Remove all section bibliographies?" confirm) is proven by
calling the underlying mutation function directly, bypassing the dialog entirely. Gating a real state mutation
behind an unverified headless dialog-return-value risked silently breaking behavior in a way pytest cannot
catch (real UNO dialog behavior is explicitly outside pytest's remit here — see Verification). The shipped
design has no such risk: both mechanisms are purely additive to existing, already-proven code paths.

**Two pre-existing real-UNO coverage gaps found and closed along the way**, not introduced by this change:
`spike_bibliography_links` previously only exercised the direct setters (`set_bibliography_links`/
`set_bibliography_external_links`), never the `_interactive` wrapper functions this backlog item is actually
about — added one isolated round-trip through each wrapper. `document_diagnostics_interactive`'s actual
assembled dialog text had zero coverage anywhere (only the underlying `diagnose_document` dict was checked) —
added a real-UNO capture of its `_msgbox` call on the clean-document path.

**A real, unrelated pre-existing bug blocked verification and was fixed to unblock it.**
`adapters/libreoffice/run_roundtrip.py`'s `seed_db()` called `embed_chunks(conn, model=..., vector_store=...)`
with neither `chunk_ids` nor `document_roles` — a call shape `embed_chunks` has rejected
(`ValueError: Embedding all chunks requires an explicit document_roles scope`) since inc 425's document-scope
invariant landed, with nothing exercising this harness in between to catch it. Fixed with one added
`document_roles=("article-fulltext",)` kwarg, matching the fixture's `role="primary"` attachments (which
`document_roles.py`'s legacy-role map normalizes to `article-fulltext`). Unrelated to this increment's actual
feature work but required to run the mandated verification gate at all.

## Housekeeping

- **No security-audit-gate trigger.** No new endpoint/external fetch/ingestion path/auth logic/dependency;
  total diff is well under 300 LOC. Touches 5-6 files, which could look like it trips the "3+ files" language
  in isolation — this project's practice (see inc 423's identical reasoning) reads that trigger as LOC-driven
  for a scope-limited, non-net-new-surface change, not file-count alone.
- **No QA route needed.** `tools/qa/build_surface_map.py` only scans `app/backend/api/routers/` and
  `app/frontend/js/*.jsx`; the LibreOffice adapter is explicitly outside that mechanism, carved out to
  `selftest_uno.py`/`run_roundtrip.py` instead (Verification protocol #4). No existing `.claude/qa-routes/`
  file claims to cover it.
- **Increment numbering:** inc 445's notes mention "Inc 446" in passing about the unrelated WIP Meta-Reference
  backlog item — not a hard reservation. Numbers are assigned by ship order in this project's actual
  convention; this work ships first and becomes 446, the WIP item becomes 447 whenever it lands.

## Manual verification script

1. Open a real Writer document with `callosum.oxt` installed, insert at least one citation.
2. Run **Document diagnostics…** — confirm a "Current settings" section always appears (with or without other
   issues present), listing all three preferences as ON/OFF matching their actual current state.
3. Run **Toggle automatic bibliography rebuild** twice — confirm the message states the transition each time
   (`ON → OFF`, then `OFF → ON`), matching Document diagnostics' report before/after each click.
4. Repeat for **Toggle citation-to-bibliography links** and **Toggle bibliography title/DOI links**.

## Verification

- `pytest tests/test_libreoffice_adapter.py tests/test_libreoffice_oxt.py tests/test_frontend_assembly.py -q`
  → **202 passed in 37.47 s**.
- `ruff format` + `ruff check` on every touched `.py` file: clean.
- `python tools/check_line_budget.py`: **469/469 application-source files within the 600-line cap** (the
  LibreOffice adapter is outside this gate's `app/`/`integrations/` scope regardless).
- `git diff --check`: clean (CRLF-on-touch warnings only, expected on this Windows checkout).
- **Real headless-UNO round trip** (`python adapters/libreoffice/run_roundtrip.py`, the actual gate for this
  surface): after the `run_roundtrip.py` fix above, a full run completed **`SELFTEST OK`, exit code 0** —
  every spike in the matrix passed, including the three extended for this increment
  (`spike_toggle_bib_auto`, `spike_bibliography_links`, `spike_document_diagnostics`). `check()` raises
  `AssertionError` immediately on any failure, so reaching the run's terminal "OK" lines for every later spike
  in sequence (through P1 #11/#15/#13) is direct proof every new assertion passed, not just that the process
  didn't crash.

## Rollback

Revert the four `callosum_cite.py` function edits (`diagnose_document`, `document_diagnostics_interactive`,
the three `toggle_*_interactive` functions), the `oxt/description.xml` version bump, and the two test files.
The `run_roundtrip.py` fix is independent and should be kept regardless — it is a correctness fix for a
harness that was silently broken for any adapter change since inc 425.
