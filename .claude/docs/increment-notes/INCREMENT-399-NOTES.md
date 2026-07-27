# Increment 399 — WIP: remove watched locations + manuscript cards

**Date:** 2026-07-27
**Status:** Implemented and verified live (Playwright); backend tests green; security audit PASS.

## Context

Under WIP, there was no way to un-watch a folder once added, and no way to remove an individual
manuscript card. This mattered concretely: watching a parent folder in "children" mode while also
having an individually-tracked child folder creates overlap the user wants to clean up — and,
investigation found, a real latent bug meant that once cleaned up (by deleting the redundant
watch-root), any resulting orphaned manuscript could never be removed at all.

## Implemented

**Backend** — `DELETE /wip/manuscripts/{manuscript_id}` (`app/backend/api/routers/wip.py`), mirroring
the existing `DELETE /wip/watch-roots/{root_id}` exactly (`run_write` → boolean rowcount → 404 if
missing). `delete_manuscript` (`app/backend/persistence/wip_repo.py`) needed no schema change at
all: every one of the 8 child tables referencing `wip_manuscripts.id` (files, findings/checks,
sections, tasks, references, provenance/checkpoints) is already `ON DELETE CASCADE`, so a single
`DELETE FROM wip_manuscripts WHERE id = ?` is complete and safe.

**Frontend**:
- `useWipWorkspace` (`10h_wip_filters.jsx`) gained `deleteManuscript`/`deleteRoot`, mirroring the
  existing `updateManuscript`/`addRoot` shape; `deleteManuscript` also clears `selectedId` if the
  deleted manuscript was selected.
- `WipRootSetup` (`10f_wip.jsx`) now shows the actual watch-root list (path, discovery mode, a 🗑
  button) behind a click on the "N watched locations" summary — previously just a bare count with no
  way to inspect or manage the underlying roots.
- `WipContextMenu` (`10i_wip_context.jsx`) gained a destructive "Remove manuscript" action, visually
  separated by a divider and styled in `--danger` on hover (not the WIP teal used by the other
  actions), both gated behind `window.confirm` (the codebase's established destructive-action
  pattern) with wording that's explicit about what's deleted (tasks/notes/checks/activity) versus
  what's untouched (the manuscript's own files on disk).

## Key technical detail

The permanent-ghost bug this closes: `wip_manuscripts.watch_root_id` is `ON DELETE SET NULL`, so
deleting a watch-root correctly preserves its manuscripts — but `/wip/rescan` only iterates *enabled
watch-roots*, so an orphaned manuscript (`watch_root_id = NULL`) could never again be marked missing,
re-synced, or removed, with no manuscript-level delete existing anywhere. It would sit in the browser
forever. The new `DELETE /wip/manuscripts/{id}` is the only way to clear one — verified directly by
creating a watch-root, deleting it (orphaning its manuscript), then deleting the orphaned manuscript
itself and confirming both a 204 and a subsequent 404.

## Manual verification script

1. Add two watch-roots (a real folder + a disposable test one); confirm both list under "N watched
   locations."
2. Delete the disposable root via its 🗑 — confirm the `window.confirm` wording, Cancel leaves it
   untouched, Confirm removes it from the list while its already-discovered manuscript card survives.
3. Right-click that surviving manuscript card → "Remove manuscript" — confirm the wording, Cancel
   leaves the card untouched, Confirm removes it immediately; a subsequent Rescan does not resurrect
   it (proving deletion, not a hide).
4. Zero console errors throughout. (All verified live via Playwright this increment, using a
   disposable test folder — the real watch-root/manuscripts from prior sessions were left untouched.)

## Pytest

`pytest tests/test_wip_api.py -q` — 11 passed (extended
`test_watch_root_validation_pause_and_delete_preserves_manuscript` with the manuscript-delete +
cascade-to-a-task case, and `test_wip_routes_deny_remote_forwarded_and_read_only_access` with the new
route's 403 check). `pytest tests/test_frontend_assembly.py -q` — 53 passed (one assertion updated for
`WipContextMenu`'s new `onDelete` param). The full-suite run caught one more required update:
`tests/test_health.py::test_api_exposes_only_read_only_get_routes` is a comprehensive allowlist of
every mutating `(path, method)` pair in the entire API (the safety net behind the read-only-mode
gate) — it correctly failed until `("/wip/manuscripts/{manuscript_id}", frozenset({"DELETE"}))` was
added alongside the existing `PATCH` entry for that path. Full suite before merge: see `changes.md`.

## Files changed

- `app/backend/api/routers/wip.py`, `app/backend/persistence/wip_repo.py`
- `app/frontend/js/{10f_wip.jsx,10h_wip_filters.jsx,10i_wip_context.jsx}`
- `app/frontend/styles.css`
- `tests/test_wip_api.py`, `tests/test_frontend_assembly.py`
- `.claude/security-audits/2026-07-27_wip-manuscript-delete.md` (new — PASS)
- `.claude/qa-routes/route_75_wip_workspace.md` (extended)
- `callosum-app.html` (rebuilt)
