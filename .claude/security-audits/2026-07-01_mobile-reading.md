# Security audit — B5 SP1: mobile reading (read-only over the tunnel), inc 237

**Date:** 2026-07-01. **Change:** a **responsive** single-column mobile layout (frontend), plus a **read-only**
deployment path over the existing cloudflared tunnel. Files: `access_control.py` (a method-level read-only gate),
`app_settings.py` (`read_only_mode()`), `04_layout.jsx`/`02_mobilenav.jsx`/`40_app.jsx`/`styles.css` (responsive),
`adapters/mobile/cloudflared-config.yml` + `README.md`, `tools/run_tunnel.py --mobile`.

**Audit-gate triggers:** new auth/authorization logic (#4 — the read-only method gate) + a new exposure path (the
read-only tunnel). **NOT triggered:** no new API endpoint (the gate is middleware; the ingress is config), no external
fetch, no new dependency, no migration, no new served route (the responsive app is the same `/`).

## Threat review

- **Read-only guarantee — two layers.** cloudflared matches **path**, not method, and a path like `/papers/5` serves
  both a GET read and a DELETE/PATCH write — so a path allowlist alone can't be read-only. The **method gate**
  (`CALLOSUM_READ_ONLY=1` → any method ∉ {GET, HEAD, OPTIONS} returns **403** at the middleware, before the handler)
  is the real boundary; the **read-only cloudflared ingress allowlist** (forward only `/`, `/health`, `/papers`,
  `/papers/{id}`, `/papers/{id}/pdf`, `/summaries*`, `/help/corpus`; everything else → 404) is defense in depth,
  keeping `/settings`, the scan/import routes, `/axes`, `/tags` unreachable at the tunnel. Verified: read GETs pass,
  every mutating method (incl. a POST that path-matches a read path, `POST /papers/export`) → 403; the ingress regex
  forwards the read paths and blocks the write/config paths (`tests/test_mobile_ingress.py`).
- **Default-off, env-only.** `CALLOSUM_READ_ONLY` is an env var (a remote caller can't set env on the user's machine —
  the `CALLOSUM_DISABLE_REMOTE_ACCESS` recovery-hatch pattern); **unset → zero change** (the middleware is a
  pass-through; the whole suite is unaffected). The maintainer runs a **second, read-only instance** for the tunnel
  (the inc-170 isolated-instance pattern) pointed at the library DB (SQLite WAL → concurrent readers safe); the
  desktop instance stays read-write.
- **Token still required.** Remote access (inc 168) is on for the tunnel instance, so the bearer token gates all
  access; the read-only gate runs *before* the remote-access check, so a write is 403 regardless of token, and a read
  still needs the token. No secret is added, logged, or returned; the ingress config commits only placeholders
  (`<TUNNEL_ID>`), the filled copy is gitignored (`adapters/mobile/cloudflared-config.local.yml`).
- **No new served surface / SSRF / egress.** The responsive app is the same `/` shell (no new route). The mobile view
  uses only existing read endpoints; the PDF is the browser's own render of `/papers/{id}/pdf` bytes. The tunnel is
  the audited inc-169 bridge; no new egress vector (a Quick Tunnel `--mobile` drops the ingress allowlist → the method
  gate + token are then the sole boundaries, documented in the README).
- **Responsive layout.** Pure client CSS/JS gated on a `matchMedia` viewport check; desktop (>760px) renders the
  unchanged 3-pane grid (`test_frontend_assembly` + headed both viewports). No data-handling change.

## Negative-path checks (`tests/test_mobile_ingress.py`, hermetic)

- `CALLOSUM_READ_ONLY=1`: GET `/papers` → 200; POST `/summarize`, DELETE `/papers/999`, POST `/papers/export` → **403**. ✔
- Unset (default): DELETE `/papers/999` reaches its handler → **404** (not the 403 gate). ✔
- The ingress regex **forwards** each read path and **does not match** `/settings`, `/library/scan`, `/axes`, `/tags`,
  `/papers/5/re-resolve`, `/summaries/5/reverify`, `/reading-queue`, `/agent/status`. ✔

**Security Audit: PASS.** Read-only is enforced at the method level (the real boundary) with the ingress allowlist as
defense in depth; default-off + env-only; the token still gates; no new endpoint/dependency/migration/egress. Deferred
(SP2): an app-side read-only *UI* that hides write controls for a clean companion (the tunnel already blocks writes, so
this is UX, not security).
