# Increment 102 — Precompile the JSX with esbuild (drop in-browser Babel)

A console-hygiene change the user requested. The served page showed two Babel messages in the dev console —
a **"You are using the in-browser Babel transformer…"** warning and a **`babel.min.js.map` 404** source-map error
— because `index.html` loaded `babel-standalone` from cdnjs and ran `<script type="text/babel">`, transpiling JSX
**in the browser at runtime** (the inc-37 "no bundler" design). Precompiling the JSX at build time and dropping
the Babel CDN removes both, plus the ~500KB download + runtime transform. (The third console line the user saw —
`XrayWrapper … content-script.js` "cross-origin object" — is an **external browser extension**, not callosum; it
vanishes in a Private window. Not addressed here.)

## Implemented
- **`package.json` + `package-lock.json` (new)** — pins `esbuild` 0.28.1 as a build-time devDependency
  (`npm install` / `npm ci`); `.gitignore` adds `node_modules/`. `npm ci` reports 0 vulnerabilities.
- **`app/backend/api/frontend.py`** — split + transpile:
  - `assemble_jsx()` — the raw concatenation of the sorted `js/*.jsx` chunks (extracted; lets the
    completeness test stay toolchain-free).
  - `_transpile_jsx(jsx)` — runs esbuild via `node node_modules/esbuild/bin/esbuild` (resolved with
    `shutil.which("node")` + an `is_file()` check) with a **fixed arg list** (`--loader=jsx --jsx=transform
    --jsx-factory=React.createElement --jsx-fragment=React.Fragment --format=iife --target=esnext`), the JSX
    piped via **stdin** (no shell). Missing toolchain / non-zero exit → a clear `RuntimeError`.
  - `build_frontend_document()` — `template.replace("{{STYLES}}", …).replace("{{SCRIPT}}",
    _transpile_jsx(assemble_jsx()))`, cached as before.
- **`app/frontend/index.html`** — removed the `babel.min.js` `<script>` line; changed `<script type="text/babel">`
  → `<script>`. React/ReactDOM CDN lines + their SRI stay.
- **`app/backend/api/app.py`** — the `/` live-assembly fallback wraps `build_frontend_document()` in try/except →
  on `RuntimeError` (esbuild absent) returns the unavailable-response rather than 500. Normal serving reads the
  static `callosum-app.html` (no Node at serve time) — unchanged.
- **`tests/test_frontend_assembly.py`** — updated for precompiled output: `test_every_js_chunk_is_included`
  checks `assemble_jsx()` (raw, no esbuild); `test_assembles_and_placeholders_consumed` asserts no
  `type="text/babel"` / `babel.min.js` and presence of `React.createElement(`; the SRI test drops the
  `babel.min.js` expectation (≥2 hashes). The staleness equality test is unchanged (deterministic per pinned
  esbuild). `tests/e2e/test_smoke.py` comment updated.
- **`.github/workflows/ci.yml`** — both jobs gained `actions/setup-node@v4` (node 24, npm cache) + `npm ci`
  before pytest, so the assembly tests / live-assembly have esbuild.

## Key technical detail
esbuild emits an **IIFE** (`(() => { … })()`) wrapping the whole concatenated source, so every chunk shares one
scope — runtime-identical to the former single `<script type="text/babel">` (where the top-level consts also
shared one script scope). Classic-runtime JSX (`--jsx=transform` → `React.createElement` against the global
`React` UMD) means no module imports and no change to how React is loaded. Output is **byte-stable** for a pinned
esbuild version + fixed flags, so `callosum-app.html` (built once) equals a fresh `build_frontend_document()` —
keeping the in-sync staleness test valid. The **server stays Python-only**: it serves the prebuilt static file;
esbuild only runs at build time (and, rarely, the live-assembly fallback). This reverses the inc-37 "in-browser
Babel / no bundler" decision in favor of a build-time transpile (no app behavior change).

## Manual verification script
1. `npm install` (once) → `python tools/build_frontend.py` rebuilds `callosum-app.html` (no `babel.min.js`, plain
   `<script>`). Confirmed: 153 `React.createElement` calls, **0** leftover `className="` JSX; `node --check` on the
   inline script body passes.
2. Start the app, open it, open DevTools → the two Babel messages are **gone**; only the external extension error
   (#2) may remain. The app renders + behaves identically.
3. Decisive automated check: `CALLOSUM_RUN_E2E=1 pytest tests/e2e -q` (Playwright loads the precompiled app and
   asserts **0 console errors**) — **passed**.

## Pytest
**411 passed, 1 skipped** — unchanged (the 5 assembly tests were updated, not added; no Python behavior changed).
`ruff` clean. Audit `.claude/security-audits/2026-06-21_precompile-esbuild.md` **PASS**.
