# Increment 237 — B5 SP1: responsive mobile reading (read-only over the tunnel)

The last B-item, started. Read your library on a phone. Maintainer forks (AskUserQuestion): **make the desktop app
responsive** (one app, not a separate `/m` companion) + **full reader** (browse + paper metadata/abstract + PDF +
read-only syntheses).

## The two things

**1. Responsive layout (the deliverable).** Built on the inc-101 reading-mode collapse.
- `04_layout.jsx::useUiPrefs` gains `mobile` (`window.matchMedia("(max-width: 760px)").matches` + a `change`
  listener — the inc-34 DPR-listener pattern) + a transient `mobilePane` (`"library" | "theory" | "methods"`).
- `40_app.jsx` computes the three region nodes (Sidebar = THEORY accordion, LibraryFrame = center/reader, pane-detail
  = METHODS) + the modals **once**, then branches: desktop = the unchanged 5-cell grid + dividers; **mobile** =
  `.app.mobile`, a single column showing **one region at a time** by `mobilePane` + a bottom **`MobileNav`** (Library /
  Panels / Details).
- `02_mobilenav.jsx` (new) is a presentational leaf (hoists in the IIFE). `styles.css` adds `.app.mobile` (flex column,
  `height: 100dvh` for the mobile address bar) + `.mobile-body` + `.mobile-nav` (tokens only). Desktop is byte-for-byte
  unchanged — the `mobile` branch never runs above 760px.

**2. Read-only over the tunnel (the guarantee).** The app **cannot** tell tunnel from local (the inc-168 lesson), so
read-only is the *deployment*, not an app mode:
- **The METHOD gate (the real boundary):** `CALLOSUM_READ_ONLY=1` (env → `app_settings.read_only_mode()`) makes
  `AccessControlMiddleware` return **403** for any method ∉ {GET, HEAD, OPTIONS}, *before* the remote-access check.
  This is load-bearing because cloudflared matches **path**, not method, and a path like `/papers/5` serves both a GET
  read and a DELETE/PATCH write — a path allowlist alone can't be read-only.
- **The read-only ingress allowlist (defense in depth):** `adapters/mobile/cloudflared-config.yml` forwards only `/`,
  `/health`, `/papers`, `/papers/{id}`, `/papers/{id}/pdf`, `/summaries*`, `/help/corpus`; everything else → 404
  (so `/settings`, the scan/import routes, `/axes`, `/tags` are never reachable at the tunnel).
- Plus the inc-168 **bearer token** (Remote access) gating all access.
- **Recommended deploy:** a second, read-only callosum for the tunnel (the inc-170 isolated-instance pattern) pointed
  at the library DB (SQLite WAL → concurrent readers safe) with `CALLOSUM_READ_ONLY=1` + Remote access on; the desktop
  instance stays read-write. `tools/run_tunnel.py --mobile` runs it; `adapters/mobile/README.md` is the runbook.
- **Default-off, env-only** — a remote caller can't set env (the `CALLOSUM_DISABLE_REMOTE_ACCESS` hatch pattern);
  unset → zero change (the middleware is a pass-through).

## Non-obvious detail — why the method gate, not just the ingress

`/papers/5` is one path but two operations (GET read + DELETE/PATCH write); `/summaries/5` likewise. cloudflared can
only allow/deny by path, so allowing `/papers/5` for reading also allows a DELETE. The method gate closes that at the
app layer (403 on every non-GET), so the ingress allowlist is defense in depth (it narrows *which* paths reach at
all) and the method gate is the actual read-only guarantee. A POST that path-matches a read path (`POST /papers/export`
matches `papers/[^/]+`) is still 403'd by the gate — verified in the tests.

## Verification

`HF_HUB_OFFLINE=1 python -m pytest tests/test_mobile_ingress.py -q` → **22 passed** (parametrized): the ingress regex
**forwards** each read path and **does not match** the write/config paths (`/settings`, `/library/scan`, `/axes`,
`/tags`, `/papers/5/re-resolve`, `/summaries/5/reverify`, `/reading-queue`, `/agent/status`); `CALLOSUM_READ_ONLY=1`
→ GET `/papers` 200 but POST `/summarize`, DELETE `/papers/999`, POST `/papers/export` → **403**; off-by-default →
DELETE reaches the handler (**404**, not 403). Full suite **872 passed, 1 skipped**. QA surface **173/173 API +
758/758 FE, 0 uncovered** (`route_00_smoke_readonly.md` claims `02_mobilenav.jsx`; no new API surface — the gate is
middleware, the ingress is config). Audit `2026-07-01_mobile-reading.md` PASS. No new endpoint, no migration, no new
dependency, no new served route.

**Headed-verified** (`.local/visual/drive_inc237_mobile.py`): at 390×844 the app renders `.app.mobile` single-column
with a bottom `.mobile-nav` (3 tabs, 0 dividers); tapping **Details** shows the pane-detail region + the active tab,
tapping **Library** shows the library search; resizing to 1280×900 restores the 3-pane grid with no mobile nav; 0
console/page errors.

## Deferred (SP2)

An app-side read-only *UI* that hides the write controls (the "+ Add ▾" menu, scan/import, trash, bulk-write actions;
read-only Details) for a clean companion — the tunnel already blocks writes, so this is UX polish, not security. Also
deferred: a mobile-tuned PDF reader / synthesis→PDF citation highlights on mobile.
