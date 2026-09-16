# Packaged acceptance harness — browser capture (#61 Phase 2)

**Status: built, NOT executed.** This harness proves the *product loop* end to end against a real
packaged `callosum-shell.exe` and a real Edge browser with the actual extension loaded. It has not
been run in this session — running it needs a human (or a session with real browser/click control)
to physically click the extension's toolbar icon, which is outside what this session could do.
Everything else — isolation, disposable-library setup, connector registration, Edge launch, and the
post-click Library-state assertions — is scripted and ready to run.

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

## Running it

```
python .claude/experiments/browser-capture-acceptance/acceptance_harness.py --case A
```

For each case, the harness prints the fixture URL it opened in Edge and pauses. Click the Callosum
Capture toolbar icon, note the badge/tooltip you see, then press Enter. The harness then inspects
the disposable library's SQLite directly and prints PASS/FAIL against the expected Library state,
and asks you to confirm the extension's rendered status agreed with it.

Cases D and E pre-seed Library state (a trashed paper; an existing attachment) via direct SQL
against the disposable database before launching Edge — a documented shortcut for this harness, not
something product code does.
