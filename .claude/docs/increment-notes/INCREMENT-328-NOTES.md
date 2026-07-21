# Increment 328 — LibreOffice adapter rework: Phase 10 (test-hardening, closes backlog #33/#34's P0 batch)

## Context
A strategic release-readiness review earlier this session flagged a real structural gap: the LibreOffice/Word/
Google-Docs adapters sit entirely outside the QA surface-map gate (`tools/qa/build_surface_map.py` only walks
`app/backend/api/routers/` and `app/frontend/js/`) — the fastest-changing subsystem this week (9 phases, a real
data-loss bug fixed) had **zero CI enforcement**, only a manual, gitignored local harness. Cliff asked for this
as an explicit final phase after Phase 9. Scoped via a quick AskUserQuestion: a **separate, non-blocking,
path-scoped CI workflow** (not folded into the main gate, given observed real transient soffice-startup flakiness
even locally; not "commit but no CI," since that leaves the actual gap unclosed).

## Implemented
- **`adapters/libreoffice/run_roundtrip.py`** (new, committed): the orchestrator promoted out of the gitignored
  `.local/lo_roundtrip/run_roundtrip.py` (deleted — superseded). Made **cross-platform**: Windows (local dev)
  uses the LibreOffice installer's bundled `soffice.exe`/`python.exe`/`unopkg.com`; Linux (CI) uses
  `shutil.which("soffice"/"unopkg")` + the **system** `/usr/bin/python3` (the one Ubuntu's `python3-uno` package
  installs the `uno` bridge into — not a project venv, not whatever `actions/setup-python` provisions). Process
  listing/killing abstracted (`tasklist`/`taskkill` vs `pgrep`/`kill`). Generated artifacts (temp DB, LO profile)
  still land in `.local/lo_roundtrip/` (gitignored) via an explicit path, not `__file__`-derived — only the
  script itself moved.
- **`.github/workflows/libreoffice-adapter.yml`** (new): triggers on push/PR paths under `adapters/libreoffice/**`,
  the citation backend (`app/backend/citations/**`, `routers/citations.py`), the frontend deep-link
  (`40_app.jsx`), or the workflow file itself, plus `workflow_dispatch`. Installs `libreoffice` + `python3-uno`
  via apt, runs the roundtrip harness **twice on failure** (mirrors this session's own "just retry" handling of
  the transient flake) with `continue-on-error: true` so neither attempt failing blocks the job — a final step
  emits a `::warning::` annotation if both fail, so it's visible without gating merges.
- Docstring/README updates pointing at the new path: `selftest_uno.py`, `tests/test_libreoffice_install.py`,
  `tests/test_libreoffice_oxt.py`, `adapters/libreoffice/README.md` (new "Testing" section), `CLAUDE.md`
  (Verification protocol gained item 4: word-processor adapter changes).
- **Timeout fix found while re-verifying the move**: the selftest subprocess timeout (180s, set at inc 157) no
  longer had headroom now that Phase 8/9 added real work (4 more documents' worth of round-trips in Phase 9
  alone) — bumped to 300s after a live run hit it and got killed mid-Phase-9, producing a `DisposedException`
  from the torn-down bridge. Not a code bug — a stale budget.
- Cleared an unrelated stray artifact found in passing: a gitignored, month-stale `ci.yml.tmp.*` temp file
  (superseded by the real `ci.yml`, harmless but dead weight).

## Tests / verification
- `python adapters/libreoffice/run_roundtrip.py` — run 3 times during this phase (first hit the pre-existing
  180s ceiling as noted above; second and third: `SELFTEST OK`, all 10 phases including Phase 9's new spike).
- `pytest tests/test_libreoffice_adapter.py tests/test_libreoffice_install.py tests/test_libreoffice_oxt.py -q`
  — 35 passed.
- `ruff format` / `ruff check .` — clean. `python -c "import yaml; yaml.safe_load(...)"` — the new workflow YAML
  parses.
- **NOT verified**: an actual GitHub Actions run of `libreoffice-adapter.yml` on a real `ubuntu-latest` runner.
  There is no way to execute a GitHub-hosted runner from this environment — the Linux code path (package names,
  `python3-uno`'s install location, whether Xvfb is needed for any UNO call this harness makes) is reasoned
  through carefully but **unverified until it actually runs after a push**. Flag this explicitly rather than
  claim full confidence — the workflow is deliberately non-blocking specifically because of this residual
  uncertainty, not only the known local flakiness.

## Gates
- **Security audit:** not triggered — no new endpoint, no new egress target (CI installing `libreoffice`/
  `python3-uno` via apt is standard CI tooling, not a runtime dependency change), no file-ingestion path change.
- **Principles/A-A:** unchanged — pure test/CI infrastructure, no claim/signal/judgment surface.

## Next
This closes the P0 batch's smaller phases (0–4, 6–10 all shipped). **Phase 5 (the composer UI)** is the one
deliberately deferred piece — the largest remaining chunk (locators/prefixes/suffixes/suppress-author, true
multi-item citation composition, a "revert manual overrides" affordance) — deferred per Cliff's own request
until after a context compaction. See the Codex handoff (`.claude/codex-handoffs/`) for a fuller state summary
and the broader backlog, written because this session is near its context limit.
