# Mobile reading — B5 SP1: responsive layout + read-only tunnel

**Status:** approved (brainstorm 2026-07-01, AskUserQuestion). The last unstarted B-item.
**Maintainer forks:** **make the desktop app responsive** (one app, not a separate `/m` companion); **full reader**
(browse + paper metadata/abstract + PDF + read-only syntheses).

## Goal

Read your library on a phone — browse, open a paper (metadata + abstract + the PDF) and read its syntheses — over the
existing cloudflared tunnel, **read-only**. The responsive layout is the deliverable; the read-only *guarantee* is the
**tunnel ingress allowlist** (the security boundary, matching the inc-169 cite-only pattern).

## The security shape (inc-168/169 precedent)

Two boundaries. The **cloudflared ingress allowlist** (tunnel-side) decides which paths reach localhost; the **bearer
token** (`AccessControlMiddleware`, inc 168) gates every request when Remote access is on. B5 adds a **read-only
ingress allowlist** — forward only the GET read endpoints a reader needs; **every write/scan/edit/delete/settings
route → 404 at the tunnel**, so read-only holds even though those routes exist locally. The app **cannot** tell
tunnel from local (the inc-168 lesson), so read-only is *not* an app mode in SP1 — it's the deployment (the tunnel).

## Responsive layout (frontend, the deliverable)

Built on the inc-101 reading-mode collapse (the backlog's "built on inc-101 read mode").

- **`04_layout.jsx` `useUiPrefs`** gains `mobile` (`window.matchMedia("(max-width: 760px)").matches`, updated by a
  `matchMedia` change listener — the inc-34 DPR-listener pattern) + `mobilePane` state (`"library"` | `"theory"` |
  `"methods"`, default `"library"`).
- **`40_app.jsx`** computes the three region nodes once (Sidebar = THEORY accordion, LibraryFrame = center/reader,
  pane-detail = METHODS accordion) + the modals once, then branches:
  - **Desktop** (`!mobile`): the existing 5-cell grid + dividers (unchanged).
  - **Mobile**: `<div className="app mobile">` → a `.mobile-body` showing **one region at a time** by `mobilePane`
    (the others unmounted) + a **`MobileNav`** bottom bar (Library / THEORY / METHODS) that sets `mobilePane`. No
    dividers. The reader is the LibraryFrame's own PDF tab (already `.pdf-scroll{overflow:auto}` → scrolls on a narrow
    screen). Modals render the same.
- **`02_mobilenav.jsx`** (new, small): a presentational `MobileNav({active, onSelect})` — a leaf, hoists in the IIFE.
- **`styles.css`**: `.app.mobile` (flex column, `height: 100dvh` with a `100vh` fallback for the mobile address bar) +
  `.mobile-body` (flex:1, its child flex:1 full-width) + `.mobile-nav` (fixed-height bottom bar; `.active` = `--accent`).
  Tokens only (rule #8; DESIGN.md gains the recipe). Desktop is byte-for-byte unchanged (the `mobile` branch never
  runs above 760px).

## Read-only tunnel (the boundary + the maintainer's live step)

- **`adapters/mobile/cloudflared-config.yml`** — a read-only ingress allowlist (placeholder `<TUNNEL_ID>`, like
  gdocs): forward ONLY `GET /`, `/health`, `/papers`, `/papers/{id}`, `/papers/{id}/pdf`, `/summaries`,
  `/summaries/{id}`, `/help/corpus`; **everything else → 404** (a single path-regex rule + a 404 catch-all). Writes
  (`/library/scan`, `/papers/{id}/re-resolve`, `/settings`, `/axes`, `/tags`, `DELETE /papers/{id}`, …) are unreachable.
- **`tools/run_tunnel.py`** gains `--mobile` (points `_config()` at the mobile config; prefers a gitignored
  `cloudflared-config.local.yml` copy, the inc-193 pattern).
- **`adapters/mobile/README.md`** — the setup runbook (reuses the gdocs Cloudflare/`cloudflared` steps + the read-only
  ingress; leads with `--quick --mobile` note that a Quick Tunnel can't enforce the allowlist → the token is then the
  sole boundary, so the named read-only tunnel is the recommended path).

## Gates

- **Security audit** `.claude/security-audits/2026-07-01_mobile-reading.md`: the read-only allowlist boundary (no
  write route forwarded — enumerated + a regex proof); the token still required (Remote access); the app served at `/`
  is the same responsive app (no new served surface); no new egress vector beyond the audited tunnel; the app-side
  read-only *UI* is deferred to SP2 (the tunnel is the boundary). **PASS**.
- **pytest** `tests/test_mobile_ingress.py` — parse the ingress `path` regex; assert it **matches** each read endpoint
  (`/papers`, `/papers/5`, `/papers/5/pdf`, `/summaries`, `/summaries/7`, `/help/corpus`) and **does NOT match** the
  write/settings routes (`/library/scan`, `/papers/5/re-resolve`, `/settings`, `/axes`, `/tags`, `/papers/5/read`). A
  pure-python guard on the boundary (no cloudflared needed). Frontend headed-verified.
- **Rule #10 (QA):** `route_00_shell.md` gains `fe: 02_mobilenav.jsx` + a responsive/mobile-nav assertion. Surface
  0-uncovered.
- **Rule #1:** `40_app.jsx` (212 → re-measure), `04_layout.jsx`, `02_mobilenav.jsx` — all under cap.
- No migration, no new dependency, no new served route (the responsive app is the same `/`).

## Verification

- **Headed at a mobile viewport** (390×844): the app renders single-column with the bottom nav; browse the library →
  open a PDF (it scrolls) → THEORY tab shows the accordion → METHODS tab shows Details; resizing back to desktop
  restores the 3-pane grid. 0 console/page errors.
- Full suite; `ruff` + `format`; `build_frontend` (+ `test_frontend_assembly`); QA `check` 0-uncovered; help corpus
  "Reading on your phone"; commit (excl. `www/`), push, CI.

## Deferred (SP2)

**Read-only UI polish** — the app detects a read-only deployment (e.g. `GET /settings` 404s over the read-only
ingress) and hides the primary write controls (the "+ Add ▾" menu, scan/import/enrich, trash, bulk-write actions) +
makes the Details fields read-only, so the mobile companion reads clean instead of showing buttons that 404. SP1's
read-only *guarantee* holds without it (the tunnel blocks writes); this is UX. Also deferred: PDF citation
exact-highlights on mobile (the desktop pdf.js overlay path), a mobile-tuned reader.
