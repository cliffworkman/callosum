# Increment 558 Notes — closing out inc 557's handoff follow-ups

## Outcome

Immediately after inc 557 (the Local AI reliability audit Wave 1/2 fix set) landed and CI went green, this
increment closes out the smaller "still open" items flagged in that increment's Codex handoff
(`.claude/docs/2026-09-01_codex-local-ai-audit-handoff.md`) rather than leaving them to a later round.

## Implemented

- **Fixed a real, pre-existing bug found while testing inc 557**: `app/backend/workbench_assist.py::
  page_tagged_text` dropped a chunk entirely (returning `""`) rather than truncating it when that single
  chunk's own page-tagged text alone exceeded `cap` — the loop broke before appending anything on the very
  first chunk. Now truncates the oversized chunk to fit instead, preserving "some representation" rather than
  "no extracted text at all" for a paper with one unusually dense chunk (more likely to matter now that
  `MAX_TEXT_CHARS_MANAGED_LOCAL` is a much tighter 8,000 chars).
- **Bounded the standalone Critical Review triage endpoint's request body**
  (`app/backend/api/routers/critical_review_triage.py`): `candidate_ids` now has
  `Field(min_length=1, max_length=500)` — a resource-amplification guard at the boundary (rule #4). The
  evaluator itself already caps processed items at 50, but the DB fetch ran before that cap ever applied, so
  an oversized request body could still force a large `IN (...)` query and response. No current frontend
  caller exists for this endpoint yet (confirmed by direct grep — it's a re-triage utility surface), so this
  is defense-in-depth, not a live-exploited bug.
- **Investigated and resolved (no code change) two more items from the handoff:**
  - **Help's `help_assistant_enabled` toggle staying independent of the active provider is confirmed
    intentional**, not a bug. `integrations/gemini/help_assistant.py`'s own module docstring/inline comment
    states the toggle is deliberately independent of both the library egress flag and the provider's
    `requires_egress` — sending the user's typed question anywhere, even to a local/no-egress provider,
    gets its own explicit opt-in by design. The toggle already has its own clearly-labeled Settings control
    (`35b_providers.jsx`'s `toggleHelp`/`helpOn`), distinct from "Allow AI features." Selecting Local AI
    correctly does not silently enable a second consent gate.
  - **Windows credential-fallback hardening is confirmed low-priority and already honestly documented.**
    `app_settings.py`'s `os.chmod` owner-only-permission call is POSIX-only (a no-op on Windows, per its own
    existing comment); this only matters for a source checkout where the optional `keyring` extra isn't
    installed — the packaged desktop build installs `keyring` as a **hard** dependency
    (`app/desktop-shell/packaging/build_python_windows.ps1`, confirmed by direct read: "hard dependency in
    the packaged build — see CLAUDE.md rule #2 / BYOK"), so real end users of the Windows-first packaged app
    are unaffected. No action taken.

## Verification

- `pytest tests/test_workbench_assist.py tests/test_workbench.py tests/test_critical_review_triage.py -q` —
  45 passed.
- `ruff format` + `ruff check` on all 4 touched files — clean.
- `python tools/check_line_budget.py` — clean (578 files).
- `python -m tach check` — clean.
- Full CI (`gh run watch`) confirmed green after push — see the commit for the exact run.

## Revert

Revert this increment's commit. No database migration or data mutation involved.
