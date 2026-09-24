# Packaged acceptance harness — browser capture (#61 Phase 2)

**Status: EXECUTED against a real Edge browser.** `run_acceptance_AtoE.py` (not `acceptance_harness.py`
below, which remains the original single-case, human-paused script) drives the real click via Windows
UI Automation keyboard-focus navigation — proven in isolation against a throwaway probe extension
before being trusted here (see `click_extension.ps1`'s header comment) — rather than pausing for a
human to click. All five cases (A-E) ran against a real packaged `callosum-shell.exe`, a real Edge
browser with the real extension loaded, and (for A/B/C) a real, live PLOS ONE article, in one
isolated session. See `evidence-run/evidence.json` and the per-case screenshots for the recorded
outcomes, and the security audit / architecture doc for the full findings and their disposition.

Two genuine product/tooling defects were found and fixed as a direct result of this run (see git
history for the actual fixes): the dev connector's `.bat`-wrapper launcher broke native messaging's
HTTP client when invoked as a grandchild of `cmd.exe`; `capture.py`'s admission path never fell back
to a default `CrossrefClient` the way `acquisition.py`'s sibling endpoint already does, so no
DOI-bearing capture could ever resolve. A third, environment-only hazard was found and fixed in the
harness itself: launching the real packaged binary on a real developer machine auto-scans "the
library folder" (Documents by default) on startup, which resolved to the maintainer's real,
Dropbox-synced document library — `CALLOSUM_LIBRARY_DIR_OVERRIDE` (a new, narrowly-scoped env var
override in `backend.rs`) redirects this to a disposable directory for any test launch that sets it.

This is the **local** half of the split the plan calls out explicitly: local acceptance proves the
product loop (capture -> admission -> Library state -> what the extension renders); it does **not**
prove installer ownership or reversibility — that is what `.github/workflows/desktop-shell-windows.yml`'s
new CI steps prove, on a clean runner, with the real NSIS installer. Neither half implies the other.

## Why this registers the DEV connector, not the real installer

Running the real NSIS installer locally would upgrade/replace the maintainer's existing 0.5.15
install. `acceptance_harness.py` instead reuses `tools/run_dev.py`'s own
`_register_dev_connector` / `_clear_dev_connector` functions directly (imported, not
reimplemented) to register `org.callosum.connector.dev` — the exact same mechanism a developer
already gets from `python tools/run_dev.py`, pointed at a **packaged** `callosum-shell.exe` instead
of a dev `uvicorn` process for this harness's purposes.

## Isolation

Reuses the exact procedure `.claude/experiments/native-messaging-probe/observe_packaged_role.py`
already proved: refuse to run if Callosum is already running, rename the real
`%APPDATA%\com.callosum.desktop` aside, let the packaged exe create a fresh disposable one, run the
case, delete the disposable directory, restore the real one unchanged. If any step of teardown
can't complete, the harness stops rather than leaving the maintainer's real library at risk.

## Fixtures are local, not live publisher pages

Same principle the extension's own unit tests use ("no CI dependency on live publisher pages"),
extended to acceptance: `fixtures.py` serves small local HTML/PDF fixtures over a throwaway
`http://127.0.0.1` server rather than depending on a real journal site staying up or keeping its
markup stable. A real PDF fixture is generated with PyMuPDF (already a project dependency) rather
than hand-crafted bytes.

## Running the automated A-E sweep

```
python .claude/experiments/browser-capture-acceptance/run_acceptance_AtoE.py
```

Runs all five cases in one isolate/restore cycle, driving the real click via
`click_extension.ps1` (keyboard-focus navigation, not raw mouse coordinates — see its header comment
for why), waiting for real page loads via `wait_for_page_ready.ps1`, and reading the extension's
rendered badge/title back over CDP via `read_extension_state.ps1`. Evidence (screenshots, DB
before/after, extension state) is written incrementally to `evidence-run/evidence.json` after every
case, so a mid-run failure never loses already-collected evidence. Retries transient
"database is locked" contention (the real backend's own background jobs can briefly hold the WAL
writer) rather than treating it as a hard failure.

Cases D and E pre-seed Library state (a trashed paper; an existing attachment) via direct SQL
against the disposable database before launching Edge — a documented shortcut for this harness, not
something product code does. Cases A/B/C hit one real, openly-licensed PLOS ONE article — a
deliberate, one-time exception to the extension unit tests' own "no live publisher pages" rule,
appropriate only for a human-authorized acceptance run, never a CI gate.

## Running a single case by hand

```
python .claude/experiments/browser-capture-acceptance/acceptance_harness.py --case A
```

The original, human-paused script: prints the fixture URL it opened in Edge and pauses for you to
click the toolbar icon yourself, then inspects the disposable library's SQLite directly. Still useful
for manual spot-checks; superseded by `run_acceptance_AtoE.py` for the full real acceptance sweep.
