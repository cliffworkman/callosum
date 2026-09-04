# Increment 576 Notes — reconnect missing PDFs without losing library work

## Trigger

After the separately managed Python-runtime release, an installed library still reported fully chunked papers but
the reader said their PDFs were metadata-only. The database rows and extracted chunks were intact; their managed
attachment paths pointed into a temporarily unavailable synced library folder. The old reader reduced every PDF 404
to the same generic message, and the existing folder scanner skipped an exact copy as an already-known checksum
instead of repairing the stale attachment location.

## Implemented

- PDF-serving failures now carry stable, path-free diagnostic codes distinguishing a URL-only record, absent path,
  missing managed-library folder, moved file, marked-missing attachment, non-PDF attachment, and temporarily
  unreadable synced file.
- The reader turns those codes into actionable copy, **Retry**, **Find or Reconnect PDF**, and privacy-safe
  **Copy diagnostics** controls.
- The watched-folders dialog now has a native folder browser and reports how many exact files were reconnected.
- A folder scan reconnects an unavailable attachment only when the scanned bytes have the exact stored SHA-256. It
  changes location/availability metadata in place and preserves the attachment id, paper, chunks, annotations,
  notes, checksum, and provenance.
- Removed-file reconciliation is scoped to the folder being scanned. Scanning folder B can no longer mark a
  scan-sourced attachment in folder A missing.
- No database migration, provider request, external egress, file copy, or destructive repair was added.

## Verification

- Focused backend/frontend/help tests: 183 passed before the final shared-tree integration.
- Real Chromium recovery smoke: passed; it opened the cause-specific reader state, copied the repair path into the
  watched-folders flow, and opened the native folder browser.
- Clean-worktree root suite: **2824 passed, 5 skipped** after mounting the repository's intentionally gitignored,
  already-generated `dist-demo/` deployment artifact. The first isolated run's sole failure was that missing test
  prerequisite; its exact three-case destination test then passed before the full green rerun.
- Ruff format/check, Bandit, Tach, line-budget, and `git diff --check`: passed before final receipt refresh.

## Manual recovery path

Open the affected paper, choose **Find or Reconnect PDF**, browse to the folder containing the original PDF (its name
may differ), and run **Add + Scan**. An exact checksum match reconnects the existing attachment without reprocessing
or discarding library work. If a sync provider was merely offline, reconnect it and choose **Retry** first.

## Revert

Revert the increment commit. No migration or destructive data rewrite requires rollback.
