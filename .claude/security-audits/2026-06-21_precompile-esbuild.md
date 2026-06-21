# Security audit — Precompile the JSX with esbuild (drop in-browser Babel), inc 102

**Date:** 2026-06-21
**Trigger:** Audit gate #6 — a new third-party (build-time) dependency (`esbuild`) + a new subprocess invocation.
**Scope:** `package.json`/`package-lock.json` (new), `app/backend/api/frontend.py` (esbuild subprocess),
`app/frontend/index.html`, `tools/build_frontend.py`, `.github/workflows/ci.yml`.

## What changed
JSX is now transpiled to plain JS **at build/assembly time** by esbuild (invoked from `frontend.py`), instead of
by `babel-standalone` in the browser at runtime. The served `callosum-app.html` loads React/ReactDOM from cdnjs
(unchanged, SRI-pinned) + one precompiled `<script>` — no Babel CDN.

## Threat review

| Area | Assessment |
|---|---|
| **Supply chain (new dep)** | `esbuild` pinned to **0.28.1** in `package.json`; `package-lock.json` committed (full tree pinned by integrity hash). CI installs via `npm ci` (lockfile-exact, no drift). `node_modules/` gitignored. esbuild is a single, widely-used, audited build tool. |
| **Subprocess / injection** | esbuild is invoked as a **fixed argument list** (`[node, esbuild_cli, --loader=jsx, …]`) with `shell=False`; the (project-owned) JSX is piped via **stdin**, never interpolated into a command line or a shell. No user/external input reaches the call — the input is the app's own source chunks. |
| **Path safety** | The esbuild CLI path is resolved relative to the project root (`node_modules/esbuild/bin/esbuild`) and `node` via `shutil.which`; no user-supplied paths. |
| **Data egress** | None. esbuild runs **locally at build time**, offline; transpiles project-owned source. No library text, no network. The Gemini egress gate is untouched. |
| **Serve-time posture** | Normal serving reads the **static** prebuilt `callosum-app.html` (no Node, no subprocess at serve time). The rare live-assembly fallback calls esbuild; if esbuild is absent it raises `RuntimeError`, which the `/` route catches → a graceful "frontend needs a build" response (never a 500, never a shell). |
| **Output encoding** | The generated JS is injected into the existing `{{SCRIPT}}` placeholder, same as before; React/ReactDOM CDN lines keep their SRI hashes. No new file-serving surface. |
| **Resource caps** | Build-time only; single esbuild pass over the concatenated source (bounded by the repo's own chunk size). |

## Negative-path checks (recorded)
- [x] esbuild missing → `_transpile_jsx` raises a clear `RuntimeError` (guards `shutil.which("node")` +
      `_ESBUILD_CLI.is_file()`); `tools/build_frontend.py` surfaces it; the `/` live-fallback route catches
      `RuntimeError` → `_assembly_unavailable_response()` (no 500). Verified by code review of the three sites.
- [x] Transpiled `<script>` body passes `node --check` (valid JS; 153 `React.createElement` calls, **0** leftover
      `className="` JSX) — verified against the rebuilt `callosum-app.html`.
- [x] App renders with **0 console errors** — the opt-in Playwright smoke (`CALLOSUM_RUN_E2E=1 pytest tests/e2e`)
      passed; React mounts and the page loads clean. Structurally, `babel.min.js` + `type="text/babel"` are gone
      from the output, so the two Babel console messages cannot appear.
- [x] No new file-serving surface; React/ReactDOM CDN lines keep their SRI; `node_modules/` gitignored;
      `package-lock.json` committed (esbuild 0.28.1 pinned; `npm ci` reported 0 vulnerabilities).

## Outcome
Security Audit: **PASS**.
