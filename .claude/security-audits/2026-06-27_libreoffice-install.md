# Security audit — LibreOffice plugin install/download from Settings (inc 162)

**Date:** 2026-06-27
**Feature:** Install the callosum LibreOffice extension from Settings — `GET /integrations/libreoffice/plugin.oxt`
(serve the built `.oxt`) + `POST /integrations/libreoffice/install` (open the `.oxt` with the OS handler so
LibreOffice's Extension Manager pops up). Router `app/backend/api/routers/libreoffice.py`; built by
`tools/build_libreoffice_oxt.py::build_oxt`.
**Audit triggers:** a new API endpoint + a new **process/file-launch** path + a new file-serving path.

## Threat review

- **Input validation / path safety.** Neither endpoint takes any request input that reaches a path. The served /
  opened file is the **fixed** built artifact `adapters/libreoffice/dist/callosum.oxt` (a constant under the project
  tree). No user/request string is interpolated into a filename, command, or path → **no path traversal, no command
  injection**. `build_oxt` zips a fixed list of in-repo source files (no request input).
- **Process launch.** `install` calls `os.startfile` (Windows) / `open` / `xdg-open` on that fixed path — it opens
  the OS's default handler for an `.oxt` (LibreOffice's Extension Manager), not an arbitrary command. The argument
  is the constant artifact path. Any failure (no handler / headless) is caught → `{opened: false}` with a download
  fallback message; it never 500s and never crashes.
- **Local-only posture.** The app binds 127.0.0.1; "the server opens a desktop app / serves a file" is a property
  of *the user's own machine*. **Gate before any hosted/remote deployment** — a remote caller must never be able to
  make the host launch a process or download server files (same class as the inc-87 folder-scan + inc-160
  library-folder notes; recorded in the Security baseline deployment checklist).
- **Data egress (invariant #3).** None. No external call; the `.oxt` is built from local source; nothing leaves the
  machine. Not behind / unrelated to the Gemini egress gate.
- **Secrets.** None read, written, or logged. The `.oxt` bundles only the adapter source (no keys; the server URL it
  ships with is the default `127.0.0.1:8080`, configured client-side at runtime).
- **Supply chain.** No new dependency (stdlib `zipfile`/`os`/`subprocess`; `tools.build_libreoffice_oxt` is in-repo).
- **The shipped extension itself.** The `.oxt` is callosum's own audited adapter (inc 108/156/157/162): a thin,
  local-only (127.0.0.1) field-placer; stdlib `urllib`; no egress; never auto-inserts (every action is user-invoked).
  Its dispatcher component runs only the bundled `callosum_cite` actions.

## Negative-path checks (from `tests/test_libreoffice_install.py`)

- `GET /integrations/libreoffice/plugin.oxt` returns a valid zip (the `.oxt`) with the expected entries + the
  extension media type. ✓
- `POST …/install` with the OS opener stubbed → `{opened: true}`. ✓
- opener raising (no handler / headless) → `{opened: false}` + a download-fallback message, HTTP 200 (no 500). ✓
- a `GET` on the install route (wrong method) → 405. ✓

## Principles (rule #9)

Non-triggering — packaging + an install convenience; no claim/signal about the literature, no provenance /
fact-vs-candidate / egress change. Credit-the-lineage already satisfied (the Zotero `CSL_CITATION` field *pattern*
is credited in the adapter README + `THIRD-PARTY-NOTICES.md`; reused as a pattern, no code copied).

## Result

**Security Audit: PASS.** Fixed-artifact path (no injection/traversal), local-only, graceful degradation (no 500,
no crash), no egress, no secrets, no new dependency. Flagged for the pre-hosted-deploy gate (process/file launch).
