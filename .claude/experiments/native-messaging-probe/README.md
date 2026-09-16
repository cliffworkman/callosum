# Native-messaging feasibility probe (EXPERIMENTAL HARNESS)

Answers one bounded question for issue #61: **is native messaging viable as the canonical packaged
discovery/control boundary?** It is **not** the production connector host and must not become one —
the real host has to be re-derived against the packaged contract.

Results are recorded in `.claude/docs/research/2026-09-15_browser-capture-architecture.md` §22.

## What it showed (Windows, 2026-09-15)

- The browser launches the host and round-trips a versioned handshake.
- The host reads the **real packaged port** from `%APPDATA%\com.callosum.desktop\last-port.txt` —
  state an extension cannot read but a local process can.
- The calling extension's origin arrives as **argv[1]**.
- All three negative cases fail closed: wrong origin, missing manifest, and a **registered manifest
  whose host binary is gone** (the packaged upgrade/uninstall case).

## Running it

`run_scenarios.py` drives the four scenarios under Edge. It **writes and removes an HKCU registry
key** (`Software\Microsoft\Edge\NativeMessagingHosts\com.callosum.connector.probe`) and leaves it
removed at the end. Nothing outside `HKCU` and temp profiles is touched.

Chrome 153 refuses `--load-extension` (disabled since Chrome 137), which is why this runs under Edge.
That constrains the dev harness only, not a store-installed extension.
