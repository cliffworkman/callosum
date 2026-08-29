# Increment 531 — Tauri packaged-app port stability + one-click LibreOffice wiring (backlog #33/#34 phase 1)

**Date:** 2026-08-29
**Scope:** Phase 1 of a three-phase plan to make the LibreOffice/Word/Google-Docs adapters work against the
packaged Tauri desktop app, not just a manually-launched dev server. Full plan:
`.claude/backups/plans/2026-08-29_tauri-word-libreoffice-googledocs-support.md`.

## Context

Everyone who currently uses callosum runs the packaged desktop app. But `app/desktop-shell/src-tauri/src/
backend.rs` spawns its backend on a fresh random free port every launch and serves plain HTTP only — a gap the
Word/Docs-parity handoff to Codex explicitly excluded ("a different shape of problem... do not start this
unless explicitly asked"). This increment is a **separate track from Codex's concurrent work** — confirmed zero
file overlap by reading Codex's own commits (`adapters/word/*`, `app/backend/api/routers/word.py`, and others)
via `git diff` before starting, and re-confirmed throughout via `git status`/`git diff` rather than assumed.

Of the three adapters, LibreOffice was found to already have full runtime port-configurability (a
`~/.callosum/libreoffice.json` sidecar file + a **Callosum → Server URL…** dialog in Writer) — the only real gap
was that the packaged app's port is never surfaced anywhere in its own UI, so there was nothing to copy into
that dialog. This increment closes that gap completely for LibreOffice. Word and Google Docs need materially
more work (a stable HTTPS listener + OS cert trust for Word; a tunnel-port-tracking convenience for Docs) —
scoped as Phase 2/3 in the plan doc, not attempted here.

## Implemented

- **`app/desktop-shell/src-tauri/src/backend.rs`**: a new `last-port.txt` file in the app's data directory
  remembers the port that worked last launch. `pick_port(preferred)` tries to bind that exact port first (same
  bind-then-drop-then-launch-uvicorn approach `pick_free_port()` already used); if something else has it, it
  falls back to a fresh OS-assigned port exactly as before. Only the spawn attempt's first try uses the
  preferred port — a retry (the port died immediately) falls back to random, unchanged from the prior behavior.
  The winning port is persisted every time a backend spawn succeeds.
- **`app/backend/api/routers/libreoffice.py`**: new `POST /integrations/libreoffice/set-server-url`. Derives the
  base URL from the request's own `Host` header (`request.base_url`) — exactly what the browser used to reach
  this endpoint, so it is always correct regardless of which port this launch picked — and writes it verbatim
  to `~/.callosum/libreoffice.json` in the exact `{"base": ...}` shape `adapters/libreoffice/callosum_cite.py`'s
  own `set_server_url` already writes. Rejects (422) any non-loopback `Host` (reusing the existing
  `is_loopback_url` helper from `app/backend/llm/providers.py`) so a call arriving through the Remote-Access
  tunnel can never repoint the adapter at a public tunnel hostname.
- **Settings UI** (`app/frontend/js/35_settings.jsx`, `35e_maintenance.jsx`): a new `ServerAddressSettings`
  component shows the current origin (`window.location.origin` — free, since the page is served from that same
  origin) with a Copy button, above the Integrations grid. `LibreOfficeSettings` gained a "Point LibreOffice at
  This Instance" button calling the new endpoint. `LibreOfficeSettings` itself moved from `35_settings.jsx` to
  `35e_maintenance.jsx` (which had headroom) to keep both files under the 600-line cap — a straight hoist, same
  shared-IIFE pattern the file's own header comment already documents for `GrobidSettings`.

## Key technical detail

The port-preference file is plain text, no secrets, and changes nothing about the actual access-control
boundary — CORS + `AccessControlMiddleware` already gate cross-origin access regardless of whether the port is
predictable, and the existing dev workflow already uses fixed, well-known ports by convention. This is purely a
convenience for external tools that need to remember a number across restarts, not a security posture change.

The new endpoint deliberately does **not** accept a client-supplied URL — it only ever writes back the exact
origin the request itself arrived on. This means a compromised/malicious frontend script could still only ever
point the adapter at wherever *this* callosum instance actually is, never at an arbitrary attacker URL.

## Concurrent-session handling (worth recording — a real collision occurred)

While this increment was in progress, Codex (working in the same repository, committing directly to `main`)
landed an uncommitted edit to `.claude/docs/INCREMENT-BACKLOG.md` in the *same paragraph region* I was editing
(Codex's own "Zotero field conversion closed inc 530" text), and separately claimed increment number 530 before
I could commit — I had drafted my own entry as "inc 530" and had to renumber to 531 after noticing the
collision live (`ls .claude/docs/increment-notes/` still showed 529 as the max on disk, but Codex's in-flight
backlog prose already claimed 530).

Rather than risk clobbering Codex's uncommitted work with a naive `git add .claude/docs/INCREMENT-BACKLOG.md`
(which would have swept both edits into one commit under the wrong attribution), the two edits were isolated
surgically: the clean HEAD version of the file was fetched (`git show HEAD:...`), my own known exact edit was
applied to that clean copy in isolation (Python exact-string replacement, not a hand-crafted diff — an earlier
attempt at a hand-written `-U0` patch failed to apply due to Unicode dash/quote fragility), the result was
written into the git object store (`git hash-object -w`), and staged directly into the index for that one path
(`git update-index --cacheinfo`) — **without ever touching the working-tree file**, so Codex's own uncommitted
Zotero-conversion paragraph remains exactly as Codex left it, untouched and ready for Codex's own commit.
Verified before proceeding: `git diff --cached` showed only my 16-line hunk; `git diff` (working tree vs. the
newly-staged index) showed only Codex's Zotero-conversion hunk, cleanly separated.

`.claude/CLAUDE.md` was found to have its own concurrent uncommitted Codex edit (the "Cross-editor adapters"
narrative, unrelated region) — deliberately **not** touched this increment to avoid repeating the same surgery
for a lower-value documentation update. A short CLAUDE.md paragraph about this packaged-app work is owed as a
follow-up once Codex's arc settles.

## Manual verification script

1. Launch the packaged desktop app. Open Settings → Integrations. Confirm a "Server address" line renders with
   the actual running origin and a working Copy button.
2. Click "Point LibreOffice at This Instance." Confirm a success message names the exact origin. Open
   `~/.callosum/libreoffice.json` and confirm it now contains `{"base": "<that origin>"}`.
3. Open LibreOffice Writer with the plugin installed; exercise a real citation action (Add citation/Suggest);
   confirm it reaches the packaged app with zero manual JSON editing.
4. Quit and relaunch the packaged app. Confirm the server address shown in Settings is the **same** port as
   before (port persistence working) and the LibreOffice plugin still reaches it without re-running step 2.
5. Direct API: `POST /integrations/libreoffice/set-server-url` from a client presenting a non-loopback `Host`
   header must return 422 and must not modify the sidecar file.

## Automated verification

- `cargo check` (desktop-shell crate): clean.
- `pytest tests/test_libreoffice_install.py tests/test_frontend_assembly.py -q` → **85 passed**.
- `python tools/build_frontend.py`: clean rebuild, no errors.
- `ruff format`/`ruff check` on every touched `.py` file: clean.
- `python tools/qa/build_surface_map.py check`: 432/432 API surfaces covered, 0 uncovered; pre-existing 6
  uncovered frontend items in `19b_synthesis_overview.jsx` are unrelated to this increment, left untouched.
- Full repository suite **not** re-run this increment (scoped, targeted verification only, per the project's own
  "targeted during dev, full before merge" convention) — owed before this branch is considered mergeable
  end-to-end alongside Codex's own concurrent commits.

## Next

Phase 2 (Word desktop add-in: a second, fixed-port HTTPS uvicorn child process + a per-machine self-signed
certificate installed into the OS user trust store, Windows/macOS only, needs its own security audit) and
Phase 3 (a Quick Tunnel convenience button for Google Docs/Word-web) remain — see the plan doc for the full
design and the reasoning for choosing a second uvicorn process over a Rust-side TLS proxy.
