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

## Addendum — SP2 (the read-only companion UI), inc 238

**Change:** the app now advertises read-only via `GET /health` (an additive `read_only` field from
`app_settings.read_only_mode()`) and, when true, hides its write controls + shows a "Read-only" badge — so a read-only
companion reads clean instead of showing buttons that 403/404. Also broadened the read-only cloudflared ingress to
forward the core library **read** GETs (`/axes`, `/axes/{id}/clusters`, `/tags`, `/tags/colors`, `/reading-queue`,
`/papers/{id}/annotations`, `/papers/{id}/chunks`) so those panels *load* read-only over the tunnel; every write on
those paths is still 403'd by the method gate.

**Audit-gate triggers:** a changed response schema (`/health` gains `read_only`) — additive, non-secret; the widened
ingress allowlist. **NOT triggered:** no new endpoint, external fetch, dependency, or migration; no new egress channel
(the widened paths are the user's own library reads over the already-audited token'd tunnel).

- **`/health.read_only` is a UX signal, not the boundary.** It only tells the client to hide controls; the enforcement
  is the SP1 **method gate** (`CALLOSUM_READ_ONLY=1` → 403 on writes) + the ingress. It exposes no secret and is
  additive/default-false. `/health` is already token-exempt + ingress-forwarded, which is *why* the client can read it
  over the read-only tunnel to decide.
- **No doomed writes on load.** A read-only companion must not *fire* a write it will 403. Verified: the on-launch
  watched-folder rescan (`POST /library/watched/rescan`) is suppressed (gated on `healthLoaded && !readOnly`), and the
  Details "Cite as…" render (`POST /citations/render`, a read-implemented-as-POST) only fetches once read-write is
  confirmed (`readOnly === false`). Headed: **0 console/page errors** in read-only mode (was 2 × 403 before the gates)
  — no request 403s on load.
- **Widened ingress is still read-only + minimal.** The added paths are GET reads of the user's own library; every
  mutating method on them is 403'd by the method gate (a `/papers/5` DELETE, an `/axes` POST, a `/reading-queue` PUT).
  The analysis/config routes (`/settings`, `/library/*`, `/methods/*`, `/discovery/*`, `/gaps`, `/agent/*`) remain 404
  at the tunnel. Verified by the enumerated regex checks in `tests/test_mobile_ingress.py`.
- **Client-side hiding is comprehensive, not a substitute for the gate.** The `readOnly` flag hides write controls in
  the library header + Details (fields render static) + Synthesis (run/re-verify/save/delete) + Axes + Tags + Queue,
  hides the METHODS analysis sections + Discover/Feed tabs, and disables drop-to-add/reorder. This is UX; a write that
  *did* leak is still 403'd by the method gate (defense in depth).

**Security Audit (SP2): PASS.** The read-only *guarantee* is unchanged (the SP1 method gate + ingress); SP2 adds a
default-false, non-secret `/health` flag + widened *read* ingress + client-side control-hiding; no doomed writes fire
on load; no new endpoint/dependency/migration/egress channel.
